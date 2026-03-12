"""
Core send logic — extracted from the existing worker/sender.py.

Contains the actual Telegram message-sending logic that workers execute:
  - Entity pre-validation
  - Human-like typing simulation
  - FloodWait / PeerFlood / permission error handling
  - Group auto-pause / auto-remove
"""

import asyncio
import random
import logging
from typing import Tuple

from telethon import TelegramClient
from telethon.tl.types import InputPeerSelf
from telethon.errors import (
    FloodWaitError,
    PeerFloodError,
    ChatWriteForbiddenError,
    ChannelPrivateError,
    ChatAdminRequiredError,
    UserBannedInChannelError,
    InputUserDeactivatedError,
    RPCError,
    ChannelInvalidError,
    UsernameNotOccupiedError,
    UsernameInvalidError,
    InviteHashExpiredError,
)

from models.group import remove_group, toggle_group
from models.job import log_job_event

logger = logging.getLogger(__name__)


async def send_message_to_group(
    client: TelegramClient,
    job_id: str,
    user_id: int,
    phone: str,
    message_id: int,
    group_id: int,
    copy_mode: bool = False,
) -> Tuple[str, int]:
    """
    Send a single message to a single group.

    Returns:
        (status, flood_wait_seconds)
        status is one of: "sent", "failed", "flood", "removed", "paused", "deactivated"
        flood_wait_seconds > 0 if a FloodWaitError was encountered.
    """
    try:
        # ── 1. Pre-validate entity ──────────────────────────────────────
        entity = None
        try:
            entity = await client.get_entity(group_id)
        except (ChannelInvalidError, UsernameNotOccupiedError,
                UsernameInvalidError, InviteHashExpiredError) as e:
            logger.warning(f"❌ Group {group_id} invalid ({type(e).__name__}). Removing.")
            asyncio.create_task(remove_group(user_id, group_id))
            await log_job_event(job_id, user_id, phone, group_id, message_id,
                                "removed", f"Pre-check: {type(e).__name__}")
            return ("removed", 0)

        except (ChatWriteForbiddenError, ChannelPrivateError,
                ChatAdminRequiredError, UserBannedInChannelError) as e:
            logger.warning(f"⚠️ Group {group_id} restricted ({type(e).__name__}). Pausing.")
            asyncio.create_task(toggle_group(user_id, group_id, enabled=False,
                                             reason=f"Pre-check: {type(e).__name__}"))
            await log_job_event(job_id, user_id, phone, group_id, message_id,
                                "paused", f"Pre-check: {type(e).__name__}")
            return ("paused", 0)

        except Exception as e:
            logger.warning(f"Entity resolve error for {group_id}: {e}")
            await log_job_event(job_id, user_id, phone, group_id, message_id,
                                "failed", f"Entity error: {e}")
            return ("failed", 0)

        # ── 2. Human-like typing ────────────────────────────────────────
        if random.random() > 0.1:
            try:
                typing_duration = random.uniform(3, 8)
                async with client.action(entity, "typing"):
                    await asyncio.sleep(typing_duration)
            except Exception:
                pass  # Typing failure is harmless

        # ── 3. Micro-delay ──────────────────────────────────────────────
        await asyncio.sleep(random.uniform(0.5, 2.5))

        # ── 4. Send the message ─────────────────────────────────────────
        # Load the message from Saved Messages
        saved_msg = await client.get_messages("me", ids=message_id)
        if not saved_msg:
            await log_job_event(job_id, user_id, phone, group_id, message_id,
                                "failed", "Message not found in Saved Messages")
            return ("failed", 0)

        if copy_mode:
            if not saved_msg.text and not saved_msg.media:
                await log_job_event(job_id, user_id, phone, group_id, message_id,
                                    "skipped", "Empty message")
                return ("failed", 0)

            await client.send_message(
                entity=entity,
                message=saved_msg.text or "",
                file=saved_msg.media,
                formatting_entities=saved_msg.entities,
            )
        else:
            await client.forward_messages(
                entity=entity,
                messages=message_id,
                from_peer=InputPeerSelf(),
            )

        await log_job_event(job_id, user_id, phone, group_id, message_id, "sent")
        return ("sent", 0)

    except FloodWaitError as e:
        logger.warning(f"FloodWait: {e.seconds}s on group {group_id}")
        await log_job_event(job_id, user_id, phone, group_id, message_id,
                            "flood", f"FloodWait {e.seconds}s")
        return ("flood", e.seconds)

    except PeerFloodError:
        logger.error(f"🚨 PeerFlood on group {group_id} — account restricted!")
        await log_job_event(job_id, user_id, phone, group_id, message_id,
                            "flood", "PeerFlood")
        return ("flood", 7200)  # 2-hour cooldown

    except (ChannelInvalidError, UsernameNotOccupiedError,
            UsernameInvalidError, InviteHashExpiredError) as e:
        logger.warning(f"❌ Removing group {group_id}: {type(e).__name__}")
        asyncio.create_task(remove_group(user_id, group_id))
        await log_job_event(job_id, user_id, phone, group_id, message_id,
                            "removed", f"{type(e).__name__}")
        return ("removed", 0)

    except (ChatWriteForbiddenError, ChannelPrivateError,
            ChatAdminRequiredError, UserBannedInChannelError) as e:
        reason = type(e).__name__
        logger.warning(f"⚠️ Pausing group {group_id}: {reason}")
        asyncio.create_task(toggle_group(user_id, group_id, enabled=False, reason=reason))
        await log_job_event(job_id, user_id, phone, group_id, message_id,
                            "paused", f"Auto-Paused: {reason}")
        return ("paused", 0)

    except InputUserDeactivatedError:
        logger.error(f"🛑 Account {phone} is deactivated!")
        from models.session import mark_session_disabled
        asyncio.create_task(
            mark_session_disabled(user_id, phone, reason="UserDeactivated")
        )
        await log_job_event(job_id, user_id, phone, group_id, message_id,
                            "failed", "UserDeactivated")
        return ("deactivated", 0)

    except RPCError as e:
        error_msg = str(e).upper()
        if any(x in error_msg for x in ["CHAT_ADMIN_REQUIRED", "CHAT_WRITE_FORBIDDEN",
                                          "USER_BANNED_IN_CHANNEL"]):
            asyncio.create_task(toggle_group(user_id, group_id, enabled=False,
                                             reason=f"RPC: {error_msg}"))
            await log_job_event(job_id, user_id, phone, group_id, message_id,
                                "paused", f"RPC: {error_msg}")
            return ("paused", 0)
        elif any(x in error_msg for x in ["CHANNEL_INVALID", "USERNAME_NOT_OCCUPIED",
                                            "USERNAME_INVALID", "INVITE_HASH_EXPIRED"]):
            asyncio.create_task(remove_group(user_id, group_id))
            await log_job_event(job_id, user_id, phone, group_id, message_id,
                                "removed", f"RPC: {error_msg}")
            return ("removed", 0)
        else:
            logger.error(f"RPCError on group {group_id}: {e}")
            await log_job_event(job_id, user_id, phone, group_id, message_id,
                                "failed", str(e))
            return ("failed", 0)

    except Exception as e:
        logger.error(f"Unexpected error on group {group_id}: {e}")
        await log_job_event(job_id, user_id, phone, group_id, message_id,
                            "failed", str(e))
        return ("failed", 0)
