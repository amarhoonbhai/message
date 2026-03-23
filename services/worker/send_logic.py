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

from models.group import remove_group, toggle_group, mark_group_failing, clear_group_fail
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
            logger.warning(f"⚠️ Group {group_id} restricted ({type(e).__name__}). Marking as failing.")
            asyncio.create_task(mark_group_failing(user_id, group_id, f"Pre-check: {type(e).__name__}"))
            await log_job_event(job_id, user_id, phone, group_id, message_id,
                                "failing", f"Pre-check: {type(e).__name__}")
            return ("failing", 0)

        except ValueError as e:
            logger.info(f"Entity not in cache for {group_id}, trying to fetch from dialogs...")
            try:
                # Fetch recent dialogs to populate cache
                async for dialog in client.iter_dialogs(limit=200):
                    if dialog.id == group_id:
                        entity = dialog.entity
                        break
                if not entity:
                    raise ValueError(f"Could not find entity {group_id} in dialogs either.")
            except Exception as dialog_e:
                logger.warning(f"Entity not found for {group_id} despite dialogs fallback: {dialog_e}")
                asyncio.create_task(mark_group_failing(user_id, group_id, "Entity Not Found"))
                await log_job_event(job_id, user_id, phone, group_id, message_id,
                                    "failing", "Entity Not Found")
                return ("failing", 0)

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
                message=saved_msg.text or None,
                file=saved_msg.media,
                formatting_entities=saved_msg.entities if saved_msg.text else None,
            )
        else:
            await client.forward_messages(
                entity=entity,
                messages=message_id,
                from_peer=InputPeerSelf(),
            )

        await log_job_event(job_id, user_id, phone, group_id, message_id, "sent")
        # Clear any previous failing status on success
        asyncio.create_task(clear_group_fail(user_id, group_id))
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
        logger.warning(f"⚠️ Group {group_id} failing: {reason}")
        asyncio.create_task(mark_group_failing(user_id, group_id, reason))
        await log_job_event(job_id, user_id, phone, group_id, message_id,
                            "failing", f"Failing: {reason}")
        return ("failing", 0)

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
        
        # 1. MESSAGE_ID_INVALID: The ad message was deleted from Saved Messages
        if "MESSAGE_ID_INVALID" in error_msg or "OPERATION ON SUCH MESSAGE" in error_msg:
            logger.warning(f"Message ID invalid or deleted (msg {message_id})")
            await log_job_event(job_id, user_id, phone, group_id, message_id,
                                "skipped", "Message deleted/invalid")
            # Don't pause the group, just skip this message
            return ("failed", 0)

        # 2. TOPIC_CLOSED or Join Required: Mark as failing (delayed removal)
        elif any(x in error_msg for x in ["CHAT_ADMIN_REQUIRED", "CHAT_WRITE_FORBIDDEN",
                                          "USER_BANNED_IN_CHANNEL", "TOPIC_CLOSED", "JOIN THE DISCUSSION GROUP",
                                          "SEND_MESSAGES_FORBIDDEN"]):
            asyncio.create_task(mark_group_failing(user_id, group_id, f"Restricted: {error_msg[:40]}"))
            await log_job_event(job_id, user_id, phone, group_id, message_id,
                                "failing", f"Restricted: {error_msg[:40]}")
            return ("failing", 0)
            
        # 3. CHANNEL_INVALID or Not Occupied: Remove the group
        elif any(x in error_msg for x in ["CHANNEL_INVALID", "USERNAME_NOT_OCCUPIED",
                                            "USERNAME_INVALID", "INVITE_HASH_EXPIRED"]):
            asyncio.create_task(remove_group(user_id, group_id))
            await log_job_event(job_id, user_id, phone, group_id, message_id,
                                "removed", f"Invalid: {error_msg[:20]}")
            return ("removed", 0)
            
        # 4. Message Empty: User tried to copy a totally empty URL preview or similar unsupported media
        elif "MESSAGE CANNOT BE EMPTY" in error_msg:
            logger.warning(f"Empty message content for copying (msg {message_id})")
            await log_job_event(job_id, user_id, phone, group_id, message_id,
                                "skipped", "Empty message or unsupported media")
            return ("failed", 0)
            
        else:
            logger.error(f"RPCError on group {group_id}: {e}")
            await log_job_event(job_id, user_id, phone, group_id, message_id,
                                "failed", error_msg[:50])
            return ("failed", 0)

    except Exception as e:
        logger.error(f"Unexpected error on group {group_id}: {e}")
        await log_job_event(job_id, user_id, phone, group_id, message_id,
                            "failed", str(e)[:50])
        return ("failed", 0)
