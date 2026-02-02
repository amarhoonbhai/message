"""
Help handler for Main Bot.
"""

from telegram import Update
from telegram.ext import ContextTypes

from main_bot.utils.keyboards import get_back_home_keyboard


HELP_TEXT = """
❓ *Help & FAQ*

*How to use?*
1️⃣ Connect your Telegram account.
2️⃣ Open your **Saved Messages** in any Telegram app.
3️⃣ Use **Dot Commands** to manage groups:
    • `.addgroup <url>` - Add a group
    • `.rmgroup <url>` - Remove a group
    • `.groups` - List your groups
    • `.status` - Check your status
    • `.interval <min>` - Set interval (min 20)
4️⃣ Simply send or forward your Ads to **Saved Messages**. We'll forward them instantly!

*Safety Features:*
• 90 seconds gap between groups
• 300 seconds (5 min) gap between ads
• Night mode (00:00-06:00 IST) - no sending
• Auto-remove invalid groups

*Main Bot Commands:*
• /start - Welcome screen
• /dashboard - Open dashboard
• /redeem <code> - Redeem premium
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
