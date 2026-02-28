"""
Start and welcome handler for Login Bot.
"""

from telegram import Update
from telegram.ext import ContextTypes

from db.models import create_user
from login_bot.utils.keyboards import get_login_welcome_keyboard


WELCOME_TEXT = """
🔐 *SECURE LOGIN PORTAL*
*★ V3.0 — PRO LOGIN ★*

Welcome to the standalone authentication bot for the Group Message Scheduler.

🛡️ *YOUR SECURITY IS OUR PRIORITY*
✅ Official Telegram API used
✅ Sessions encrypted using AES-256
✅ Complete control over your data

To connect your account, you need:
1️⃣ Your Phone Number
2️⃣ Your Telegram API Hash
3️⃣ Your Telegram API ID

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


async def help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help for login format."""
    query = update.callback_query
    await query.answer()
    
    help_text = """
ℹ️ *HOW TO GET API ID & HASH*
──────────────────────────────

1️⃣ Go to https://my.telegram.org in your browser
2️⃣ Log in with your Telegram number
3️⃣ Tap on **"API development tools"**
4️⃣ Fill out the basic form (any name/app)
5️⃣ Copy the **API ID** and **API HASH**

*Why do we need this?*
Telegram requires every automation app to
use its own unique API connection. This keeps
your account completely safe from mass bans.
"""
    
    await query.edit_message_text(
        help_text,
        parse_mode="Markdown",
        reply_markup=get_login_welcome_keyboard(),
    )
