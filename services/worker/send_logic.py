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
from shared.telegram_error_mapper import map_telegram_error
from core.database import get_database

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
            logger.warning(f"❌ Group {group_id} restricted ({type(e).__name__}). Removing.")
            asyncio.create_task(remove_group(user_id, group_id))
            await log_job_event(job_id, user_id, phone, group_id, message_id,
                                "removed", f"Restricted: {type(e).__name__}")
            return ("removed", 0)

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
                logger.warning(f"🚨 Entity {group_id} not found after recovery attempts. Removing.")
                asyncio.create_task(remove_group(user_id, group_id))
                await log_job_event(job_id, user_id, phone, group_id, message_id,
                                    "removed", "Entity Not Found (Membership Required)")
                return ("removed", 0)

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
        db = get_database()
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

        if copy_mode or topic_id:
            # Use send_message as it reliably supports reply_to (for forums) and media
            await client.send_message(
                entity=entity,
                message=saved_msg.text or None,
                file=saved_msg.media,
                formatting_entities=saved_msg.entities if saved_msg.text else None,
                reply_to=topic_id
            )
        else:
            # Standard forward (shows "Forwarded from")
            await client.forward_messages(
                entity=entity,
                messages=message_id,
                from_peer='me'
            )

        await log_job_event(job_id, user_id, phone, group_id, message_id, "sent")
        # Clear any previous failing status on success
        asyncio.create_task(clear_group_fail(user_id, group_id))
        return ("sent", 0)

    except Exception as e:
        mapped = map_telegram_error(e)
        err_code = mapped["error_code"]
        disp_msg = mapped["display_message"]
        
        if err_code == "FLOOD_WAIT":
            seconds = getattr(e, 'seconds', 30)
            logger.warning(f"FloodWait: {seconds}s on group {group_id}")
            await log_job_event(job_id, user_id, phone, group_id, message_id, "flood", disp_msg)
            return ("flood", seconds)
            
        elif err_code == "PEER_FLOOD":
            logger.error(f"🚨 PeerFlood on group {group_id} — account restricted!")
            await log_job_event(job_id, user_id, phone, group_id, message_id, "flood", disp_msg)
            return ("flood", 7200)  # 2-hour cooldown
            
        elif err_code == "ACCOUNT_DEACTIVATED":
            logger.error(f"🛑 Account {phone} is deactivated!")
            from models.session import mark_session_disabled
            asyncio.create_task(mark_session_disabled(user_id, phone, reason="User Deactivated"))
            await log_job_event(job_id, user_id, phone, group_id, message_id, "failed", disp_msg)
            return ("deactivated", 0)
            
        elif isinstance(e, RPCError) and err_code not in ("FLOOD_WAIT", "PEER_FLOOD", "ACCOUNT_DEACTIVATED", "MESSAGE_DELETED", "EMPTY_MESSAGE", "SLOWMODE"):
            logger.warning(f"❌ Removing group {group_id} due to RPC error: {disp_msg} ({err_code})")
            asyncio.create_task(remove_group(user_id, group_id))
            await log_job_event(job_id, user_id, phone, group_id, message_id, "removed", disp_msg)
            return ("removed", 0)
            
        elif err_code in ["MESSAGE_DELETED", "EMPTY_MESSAGE", "SLOWMODE"]:
            logger.warning(f"⚠️ {disp_msg} — skipping group {group_id}")
            await log_job_event(job_id, user_id, phone, group_id, message_id, "skipped", disp_msg)
            return ("failed", 0) # Return failed to task_worker to ensure stats track it as non-success
            
        else:
            logger.error(f"Error on group {group_id}: {disp_msg} ({type(e).__name__})")
            await log_job_event(job_id, user_id, phone, group_id, message_id, "failed", disp_msg)
            return ("failed", 0)
