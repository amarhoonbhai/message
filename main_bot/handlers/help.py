"""
Help handler for Main Bot.
"""

from telegram import Update
from telegram.ext import ContextTypes

from main_bot.utils.keyboards import get_back_home_keyboard


HELP_TEXT = """
❓ *HELP & COMMANDS*
━━━━━━━━━━━━━━━━━━━━━━━━

📖 *QUICK START*
➳ Connect your Telegram account
➳ Open *Saved Messages*
➳ Use dot commands below
➳ Send ads → Auto-forwarded! ⚡

━━━━ 🎮 *DOT COMMANDS* 🎮 ━━━━

❊ `.addgroup <url>` — Add group
❊ `.rmgroup <url>` — Remove group
❊ `.groups` — List all groups
❊ `.status` — Check status
❊ `.interval <min>` — Set delay
❊ `.help` — Show commands

━━━━ 🛡️ *SAFETY* 🛡️ ━━━━

❊ 60s between groups
❊ 5min between messages
❊ Night mode: 00:00–06:00
❊ Auto-remove bad groups

━━━━ 💬 *BOT COMMANDS* 💬 ━━━━

❊ /start — Home screen
❊ /dashboard — Dashboard
❊ /redeem <code> — Premium
❊ /help — This help

━━━━━━━━━━━━━━━━━━━━━━━━
📣 *SUPPORT:* @PHilobots
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
