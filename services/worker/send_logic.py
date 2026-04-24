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
            # Try getting from cache/ID first
            entity = await client.get_entity(group_id)
        except (ChannelInvalidError, UsernameNotOccupiedError,
                UsernameInvalidError, InviteHashExpiredError) as e:
            logger.warning(f"❌ Group {group_id} invalid ({type(e).__name__}). Removing.")
            asyncio.create_task(remove_group(user_id, group_id))
            await log_job_event(job_id, user_id, phone, group_id, message_id,
                                "removed", f"Link dead: {type(e).__name__}")
            return ("removed", 0)

        except (ChatWriteForbiddenError, ChannelPrivateError,
                ChatAdminRequiredError, UserBannedInChannelError) as e:
            logger.warning(f"⚠️ Group {group_id} restricted ({type(e).__name__}). Marking as failing.")
            asyncio.create_task(mark_group_failing(user_id, group_id, f"Locked: {type(e).__name__}"))
            await log_job_event(job_id, user_id, phone, group_id, message_id,
                                "failing", f"Restricted: {type(e).__name__}")
            return ("failing", 0)

        except ValueError:
            # Not in cache! Try resolving raw ID or via recent dialogs
            logger.info(f"Entity not in cache for {group_id}, attempt recovery...")
            try:
                # 1. Try resolving numerical ID if it's not already an entity
                entity = await client.get_entity(int(group_id))
            except Exception:
                try:
                    # 2. Try fetching from dialogs summary (faster than full scan)
                    async for dialog in client.iter_dialogs(limit=100):
                        if dialog.id == int(group_id):
                            entity = dialog.entity
                            break
                except Exception: pass
            
            if not entity:
                logger.warning(f"🚨 Entity {group_id} not found after recovery attempts.")
                asyncio.create_task(mark_group_failing(user_id, group_id, "Entity Not Found"))
                await log_job_event(job_id, user_id, phone, group_id, message_id,
                                    "failing", "Entity Not Found (Membership Required)")
                return ("failing", 0)

        except Exception as e:
            logger.warning(f"Unexpected entity resolve error for {group_id}: {e}")
            # If it's a generic connection error, don't mark as failing, just fail this attempt
            return ("failed", 0)

        # ── 2. Stealth: Read History Simulation (Level Up) ──────────
        # Mimics a user opening the group before posting.
        if random.random() > 0.4:
            try:
                from telethon.tl.functions.messages import ReadHistoryRequest
                await client(ReadHistoryRequest(peer=entity, max_id=0))
                await asyncio.sleep(random.uniform(2.0, 5.0))
            except Exception: pass

        # ── 3. SlowMode & Permission Pre-Check (Level Up) ────────────
        try:
            if hasattr(entity, 'broadcast') or getattr(entity, 'megagroup', False):
                from telethon.tl.functions.channels import GetFullChannelRequest
                full_chat_info = await client(GetFullChannelRequest(entity))
                slowmode = getattr(full_chat_info.full_chat, 'slowmode_seconds', 0)
                if slowmode and slowmode > 300: # If > 5 mins, skip for now
                    logger.info(f"⏳ Group {group_id} has high slowmode ({slowmode}s). Skipping.")
                    return ("failing", 0)
        except Exception: pass

        # ── 4. Human-like typing ────────────────────────────────────
        if random.random() > 0.1:
            try:
                typing_duration = random.uniform(4, 9)
                async with client.action(entity, "typing"):
                    await asyncio.sleep(typing_duration)
            except Exception:
                pass  # Typing failure is harmless

        # ── 5. Micro-delay ──────────────────────────────────────────
        await asyncio.sleep(random.uniform(1.0, 3.0))

        # ── 6. Topic Awareness ──────────────────────────────────────
        group_doc = await db.groups.find_one({"user_id": user_id, "chat_id": group_id})
        topic_id = group_doc.get("topic_id") if group_doc else None

        # ── 7. Send the message ─────────────────────────────────────────
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
                reply_to=topic_id
            )
        else:
            # Use 'me' instead of InputPeerSelf() for better cross-session compatibility
            await client.forward_messages(
                entity=entity,
                messages=message_id,
                from_peer='me',
                reply_to=topic_id
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
                            "flood", "PeerFlood Restriction")
        return ("flood", 7200)  # 2-hour cooldown

    except (ChannelInvalidError, UsernameNotOccupiedError,
            UsernameInvalidError, InviteHashExpiredError) as e:
        reason = type(e).__name__
        logger.warning(f"❌ Removing group {group_id}: {reason}")
        asyncio.create_task(remove_group(user_id, group_id))
        await log_job_event(job_id, user_id, phone, group_id, message_id,
                            "removed", f"Dead link: {reason}")
        return ("removed", 0)

    except (ChatWriteForbiddenError, ChannelPrivateError,
            ChatAdminRequiredError, UserBannedInChannelError) as e:
        reason = type(e).__name__
        logger.warning(f"⚠️ Group {group_id} failing: {reason}")
        asyncio.create_task(mark_group_failing(user_id, group_id, reason))
        await log_job_event(job_id, user_id, phone, group_id, message_id,
                            "failing", f"Permission: {reason}")
        return ("failing", 0)

    except InputUserDeactivatedError:
        logger.error(f"🛑 Account {phone} is deactivated!")
        from models.session import mark_session_disabled
        asyncio.create_task(
            mark_session_disabled(user_id, phone, reason="UserDeactivated")
        )
        await log_job_event(job_id, user_id, phone, group_id, message_id,
                            "failed", "Account Banned/Deactivated")
        return ("deactivated", 0)

    except RPCError as e:
        # Extract the most meaningful part of the RPC error
        raw_error = str(e).upper()
        if "(" in raw_error:
            # e.g. "FILE_REFERENCE_EXPIRED (400)" -> "FILE_REFERENCE_EXPIRED"
            error_code = raw_error.split("(")[0].strip()
        else:
            error_code = raw_error[:30]

        # 1. MESSAGE_ID_INVALID: The ad message was deleted from Saved Messages
        if any(x in error_code for x in ["MESSAGE_ID_INVALID", "OPERATION ON SUCH MESSAGE"]):
            await log_job_event(job_id, user_id, phone, group_id, message_id,
                                "skipped", "Ad Deleted from Saved Messages")
            return ("failed", 0)

        # 2. Permission issues
        elif any(x in error_code for x in ["CHAT_ADMIN_REQUIRED", "CHAT_WRITE_FORBIDDEN",
                                           "USER_BANNED_IN_CHANNEL", "TOPIC_CLOSED", "SEND_MESSAGES_FORBIDDEN"]):
            asyncio.create_task(mark_group_failing(user_id, group_id, error_code))
            await log_job_event(job_id, user_id, phone, group_id, message_id,
                                "failing", error_code)
            return ("failing", 0)
            
        else:
            logger.error(f"RPCError on group {group_id}: {e}")
            await log_job_event(job_id, user_id, phone, group_id, message_id,
                                "failed", error_code)
            return ("failed", 0)

    except Exception as e:
        logger.error(f"Unexpected error on group {group_id}: {e}")
        await log_job_event(job_id, user_id, phone, group_id, message_id,
                            "failed", str(e)[:50])
        return ("failed", 0)
