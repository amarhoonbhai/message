"""
Two-Factor Authentication handler for Login Bot.
Uses per-user API credentials collected during login.
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes
from telethon.errors import PasswordHashInvalidError, FloodWaitError

from config import MAIN_BOT_USERNAME
from login_bot.handlers.otp import _login_clients
from login_bot.utils.keyboards import get_2fa_keyboard, get_cancel_keyboard, get_success_keyboard
from shared.utils import escape_markdown, build_connection_success_text
from db.models import create_session, create_user

logger = logging.getLogger(__name__)


async def receive_2fa_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process 2FA password input."""
    state = context.user_data.get("state")
    
    if state != "waiting_2fa":
        return
    
    user_id = update.effective_user.id
    password = update.message.text.strip()
    
    login_data = _login_clients.get(user_id)
    
    if not login_data:
        await update.message.reply_text(
            "❌ Session expired. Please start over.",
            reply_markup=get_cancel_keyboard(),
        )
        return
    
    client = login_data["client"]
    phone = login_data["phone"]
    
    # Delete the password message for security
    try:
        await update.message.delete()
    except Exception:
        pass
    
    # Send verifying message
    verifying_msg = await update.effective_chat.send_message("🔄 Verifying password...")
    
    try:
        # Sign in with password
        await client.sign_in(password=password)
        
        # Success! Get session string
        session_string = client.session.save()
        
        # Get API credentials from context
        api_id = context.user_data.get("api_id")
        api_hash = context.user_data.get("api_hash")
        
        # Save to database WITH per-user API credentials
        await create_user(user_id)
        await create_session(user_id, phone, session_string, api_id, api_hash)
        
        # Disconnect client
        await client.disconnect()
        
        # Clean up
        if user_id in _login_clients:
            del _login_clients[user_id]
        
        context.user_data.clear()
        
        # Fetch the user's current plan and build success text
        from db.models import get_plan
        from shared.utils import build_connection_success_text
        plan = await get_plan(user_id)
        text = build_connection_success_text(phone, plan)
        
        await verifying_msg.edit_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_success_keyboard(),
        )
        
    except PasswordHashInvalidError:
        await verifying_msg.edit_text(
            "❌ *Invalid Password*\n\n"
            "The 2FA password is incorrect. Please try again.",
            parse_mode="Markdown",
            reply_markup=get_2fa_keyboard(),
        )
        
    except FloodWaitError as e:
        await verifying_msg.edit_text(
            f"⏳ *Too Many Attempts*\n\n"
            f"Please wait {e.seconds} seconds before trying again.",
            parse_mode="Markdown",
            reply_markup=get_cancel_keyboard(),
        )
        
    except Exception as e:
        logger.error(f"2FA error: {e}")
        escaped_e = escape_markdown(str(e))
        await verifying_msg.edit_text(
            f"❌ *Error*\n\n{escaped_e}",
            parse_mode="Markdown",
            reply_markup=get_cancel_keyboard(),
        )
