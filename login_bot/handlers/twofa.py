"""
Two-Factor Authentication handler for Login Bot.
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes
from telethon.errors import PasswordHashInvalidError, FloodWaitError

from login_bot.handlers.otp import _login_clients
from login_bot.utils.keyboards import get_2fa_keyboard, get_cancel_keyboard, get_success_keyboard
from db.models import create_session, create_user
from config import MAIN_BOT_USERNAME

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
    api_id = login_data.get("api_id")
    api_hash = login_data.get("api_hash")
    
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
        
        # Save to database WITH API credentials
        await create_user(user_id)
        await create_session(user_id, phone, session_string, api_id, api_hash)
        
        # Disconnect client
        await client.disconnect()
        
        # Clean up
        if user_id in _login_clients:
            del _login_clients[user_id]
        
        context.user_data.clear()
        
        # Edit the verifying message to show success
        success_text = """
✅ *Connected Successfully!*

Your account is linked with your own API credentials.
Open the main dashboard to manage groups, interval and plans.

🎁 You have a *7-day free trial*.
Invite 3 friends to get +7 days more!
"""
        
        await verifying_msg.edit_text(
            success_text,
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
        await verifying_msg.edit_text(
            f"❌ *Error*\n\n{str(e)}",
            parse_mode="Markdown",
            reply_markup=get_cancel_keyboard(),
        )
