"""
SpamBot Appeal Module.
Automatically sends /start to @SpamBot on behalf of restricted Telethon accounts
to request spam limit removal from Telegram.

How it works:
- When an account hits PeerFlood or a long FloodWait (>5min), the worker
  automatically triggers this module.
- The account's own Telethon client sends /start to @SpamBot.
- A cooldown prevents spamming the appeal (once per 6 hours per account).
- The owner gets notified in the central log channel about the appeal.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from telethon import TelegramClient

logger = logging.getLogger(__name__)

# In-memory cooldown tracker: {phone: last_appeal_datetime}
_appeal_cooldowns: dict[str, datetime] = {}
APPEAL_COOLDOWN_HOURS = 6   # Only send appeal once every 6 hours per account


def _is_on_cooldown(phone: str) -> bool:
    """Check if this account has already sent an appeal recently."""
    last = _appeal_cooldowns.get(phone)
    if not last:
        return False
    return datetime.utcnow() - last < timedelta(hours=APPEAL_COOLDOWN_HOURS)


def _set_cooldown(phone: str):
    """Mark appeal as sent for this account."""
    _appeal_cooldowns[phone] = datetime.utcnow()


async def appeal_to_spambot(
    client: TelegramClient,
    phone: str,
    user_id: int,
    reason: str = "PeerFlood"
) -> bool:
    """
    Send /start to @SpamBot using the restricted account's own Telethon session
    to request spam limit removal.

    Args:
        client: The Telethon TelegramClient of the restricted account.
        phone: Phone number of the account (for logging and cooldown tracking).
        user_id: Bot user ID (for notification).
        reason: The error reason that triggered the appeal.

    Returns:
        True if appeal was sent successfully, False otherwise.
    """
    if _is_on_cooldown(phone):
        logger.info(f"[SpamBot Appeal] Skipping {phone} — already appealed within {APPEAL_COOLDOWN_HOURS}h cooldown.")
        return False

    try:
        logger.info(f"[SpamBot Appeal] Sending /start to @SpamBot for {phone} ({reason})")

        # Resolve SpamBot entity
        spambot = await client.get_entity("SpamBot")

        # Send /start to SpamBot
        await client.send_message(spambot, "/start")
        await asyncio.sleep(2)  # Give SpamBot a moment to respond

        _set_cooldown(phone)

        logger.info(f"[SpamBot Appeal] ✅ Appeal sent for {phone}")

        # Notify owner in central log channel
        try:
            from worker.utils import send_central_log
            from html import escape

            masked_phone = phone[:4] + "****" + phone[-2:] if len(phone) > 6 else phone

            msg = (
                f"<b>🆘 SpamBot Appeal Auto-Triggered</b>\n\n"
                f"📞 <b>Account:</b> <code>{escape(masked_phone)}</code>\n"
                f"👤 <b>User ID:</b> <code>{user_id}</code>\n"
                f"⚠️ <b>Trigger Reason:</b> {escape(reason)}\n"
                f"🤖 <b>Action:</b> /start sent to @SpamBot\n"
                f"🕐 <b>Next Appeal In:</b> {APPEAL_COOLDOWN_HOURS} hours\n\n"
                f"<i>Telegram will review and lift restrictions automatically.</i>"
            )
            asyncio.create_task(send_central_log(msg))
        except Exception as log_err:
            logger.error(f"[SpamBot Appeal] Failed to send central log: {log_err}")

        return True

    except Exception as e:
        logger.error(f"[SpamBot Appeal] ❌ Failed to send appeal for {phone}: {e}")
        return False


async def appeal_to_spambot_from_session(
    user_id: int,
    phone: str,
    reason: str = "PeerFlood"
) -> bool:
    """
    Build a fresh Telethon client from DB session and appeal to SpamBot.
    Use this when the original client is not available.
    """
    if _is_on_cooldown(phone):
        return False

    try:
        from models.session import get_session
        from shared.utils import get_telegram_client_kwargs
        from telethon.sessions import StringSession

        session_data = await get_session(user_id, phone)
        if not session_data or not session_data.get("session_string"):
            logger.warning(f"[SpamBot Appeal] No session found for {phone}")
            return False

        from config import API_ID, API_HASH
        api_id = session_data.get("api_id") or API_ID
        api_hash = session_data.get("api_hash") or API_HASH

        client = TelegramClient(
            StringSession(session_data["session_string"]),
            api_id,
            api_hash,
            device_model="SpamBot Appeal",
            system_version="2.0",
            app_version="2.0",
            **get_telegram_client_kwargs()
        )

        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            return False

        result = await appeal_to_spambot(client, phone, user_id, reason)
        await client.disconnect()
        return result

    except Exception as e:
        logger.error(f"[SpamBot Appeal] Session-based appeal failed for {phone}: {e}")
        return False
