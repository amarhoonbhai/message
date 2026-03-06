"""
Start and welcome handler for Login Bot.
"""

from telegram import Update
from telegram.ext import ContextTypes

from db.models import create_user
from login_bot.utils.keyboards import get_login_welcome_keyboard


WELCOME_TEXT = """
🔐 *SECURE LOGIN PORTAL*
*★ V3.3 — PRO LOGIN ★*

Welcome to the standalone authentication bot for the Group Message Scheduler.

🛡️ *YOUR SECURITY IS OUR PRIORITY*
✅ Official Telegram API used
✅ Sessions encrypted using AES-256
✅ Complete control over your data

To connect your account, you just need:
1️⃣ Your Phone Number
2️⃣ The OTP sent to your Telegram

👇 *Tap below to start the connection process*
"""


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    user = update.effective_user
    
    # Ensure user exists in db
    await create_user(user.id)
    
    first_name = user.first_name or "User"
    greeting = f"👋 *Greeting {first_name},*\n\n"
    
    await update.message.reply_text(
        greeting + WELCOME_TEXT,
        parse_mode="Markdown",
        reply_markup=get_login_welcome_keyboard(),
    )
