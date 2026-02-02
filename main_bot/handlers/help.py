"""
Help handler for Main Bot.
"""

from telegram import Update
from telegram.ext import ContextTypes

from main_bot.utils.keyboards import get_back_home_keyboard


HELP_TEXT = """
❓ *Help & FAQ*

*What is Group Message Scheduler?*
A tool to auto-forward your Saved Messages to up to 15 groups with safe timing.

*How does it work?*
1️⃣ Connect your Telegram account
2️⃣ Add groups where you want to send
3️⃣ Save messages to your Saved Messages
4️⃣ We auto-forward them to your groups!

*Safety Features:*
• 90 seconds gap between groups
• 500 seconds gap between messages
• Night mode (00:00-06:00 IST) - no sending
• Auto-remove invalid groups

*Commands:*
• /start - Welcome screen
• /dashboard - Open dashboard
• /redeem <code> - Redeem a code
• /help - This help message

*Need more help?*
Join @PHilobots for support and updates.
"""


async def help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help screen."""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        HELP_TEXT,
        parse_mode="Markdown",
        reply_markup=get_back_home_keyboard(),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    await update.message.reply_text(
        HELP_TEXT,
        parse_mode="Markdown",
        reply_markup=get_back_home_keyboard(),
    )
