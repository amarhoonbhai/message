"""
Start and welcome handler for Login Bot.
"""

from telegram import Update
from telegram.ext import ContextTypes

from login_bot.utils.keyboards import get_login_welcome_keyboard


WELCOME_TEXT = """
👋 *Welcome to Spinify Login*

Let's connect your Telegram account securely.

✅ Saved session
✅ Safe scheduling rules
✅ Manage everything from the main dashboard

Tap below to start.
"""


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    await update.message.reply_text(
        WELCOME_TEXT,
        parse_mode="Markdown",
        reply_markup=get_login_welcome_keyboard(),
    )


async def help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help for login process."""
    query = update.callback_query
    await query.answer()
    
    help_text = """
❓ *Login Help*

*How to connect your account:*
1️⃣ Tap "Add Account"
2️⃣ Enter your phone number with country code
3️⃣ Confirm and receive OTP
4️⃣ Enter OTP using the keypad
5️⃣ If 2FA is enabled, enter your password

*FAQ:*
• Your session is stored securely
• We never access your private chats
• You can disconnect anytime from the main bot

Need help? Join @PHilobots
"""
    
    await query.edit_message_text(
        help_text,
        parse_mode="Markdown",
        reply_markup=get_login_welcome_keyboard(),
    )
