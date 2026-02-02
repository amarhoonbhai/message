"""
Two-Factor Authentication handler for Login Bot.
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes
from telethon.errors import PasswordHashInvalidError, FloodWaitError

from login_bot.handlers.otp import _login_clients, save_session_and_complete
from login_bot.utils.keyboards import get_2fa_keyboard, get_cancel_keyboard

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
    
    try:
        # Sign in with password
        await client.sign_in(password=password)
        
        # Delete the password message for security
        try:
            await update.message.delete()
        except Exception:
            pass
        
        # Success! Save session
        await update.message.reply_text("🔄 Verifying password...")
        
        # Create a fake query object for compatibility
        class FakeQuery:
            async def answer(self, *args, **kwargs):
                pass
            async def edit_message_text(self, text, **kwargs):
                await update.message.reply_text(text, **kwargs)
        
        fake_update = type('obj', (object,), {'callback_query': FakeQuery()})()
        
        await save_session_and_complete(fake_update, context, client, phone, api_id, api_hash)
        
    except PasswordHashInvalidError:
        await update.message.reply_text(
            "❌ *Invalid Password*\n\n"
            "The 2FA password is incorrect. Please try again.",
            parse_mode="Markdown",
            reply_markup=get_2fa_keyboard(),
        )
        
    except FloodWaitError as e:
        await update.message.reply_text(
            f"⏳ *Too Many Attempts*\n\n"
            f"Please wait {e.seconds} seconds before trying again.",
            parse_mode="Markdown",
            reply_markup=get_cancel_keyboard(),
        )
        
    except Exception as e:
        logger.error(f"2FA error: {e}")
        await update.message.reply_text(
            f"❌ *Error*\n\n{str(e)}",
            parse_mode="Markdown",
            reply_markup=get_cancel_keyboard(),
        )
