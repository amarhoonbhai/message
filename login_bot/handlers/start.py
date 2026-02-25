"""
Start and welcome handler for Login Bot.
"""

from telegram import Update
from telegram.ext import ContextTypes

from login_bot.utils.keyboards import get_login_welcome_keyboard


WELCOME_TEXT = """
🔐 *SECURE LOGIN*
╔══════════════════════════╗
║    ★ V3.0 — ACCOUNT LINK ★     ║
╚══════════════════════════╝

Connect your Telegram account
securely to start auto-forwarding.

  ┌─────────────────────────┐
  │  ✅ Encrypted session storage   │
  │  ✅ Safe scheduling rules       │
  │  ✅ Manage from main dashboard  │
  │  ✅ Disconnect anytime          │
  └─────────────────────────┘

  👇 *Tap below to begin*
"""


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    user = update.effective_user
    first_name = user.first_name or "User"
    greeting = f"👋 *Hey {first_name}!*\n"
    
    await update.message.reply_text(
        greeting + WELCOME_TEXT,
        parse_mode="Markdown",
        reply_markup=get_login_welcome_keyboard(),
    )


async def help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help for login process."""
    query = update.callback_query
    await query.answer()
    
    help_text = """
📖 *LOGIN HELP*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

*How to connect your account:*

  1️⃣ Tap \"📱 Add Account\"
  2️⃣ Enter phone with country code
  3️⃣ Confirm & receive OTP
  4️⃣ Enter OTP via secure keypad
  5️⃣ Enter 2FA password (if enabled)

━━━━ ❓ *FAQ* ━━━━

  ▸ Session stored with encryption 🔐
  ▸ We never access private chats 🛡️
  ▸ Disconnect anytime from main bot ✅

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💬 Need help? Join @PHilobots
"""
    
    await query.edit_message_text(
        help_text,
        parse_mode="Markdown",
        reply_markup=get_login_welcome_keyboard(),
    )
