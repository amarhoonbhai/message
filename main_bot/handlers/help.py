"""
Help handler for Main Bot.
"""

from telegram import Update
from telegram.ext import ContextTypes

from main_bot.utils.keyboards import get_back_home_keyboard


HELP_TEXT = """
📖 *HELP & COMMANDS*
╔══════════════════════════╗
║     ★ V3.0 — COMMAND GUIDE ★    ║
╚══════════════════════════╝

━━━━ 🚀 *QUICK START* ━━━━

  1️⃣ Connect your Telegram account
  2️⃣ Open *Saved Messages*
  3️⃣ Use dot commands below
  4️⃣ Send ads → Auto-forwarded! 🎯

━━━━ 📋 *GROUP COMMANDS* ━━━━

  ▸ `.addgroup <url>` — Add group
  ▸ `.rmgroup <url|#>` — Remove group
  ▸ `.groups` — List all groups

━━━━ ⚙️ *SETTINGS* ━━━━

  ▸ `.interval <min>` — Set delay
  ▸ `.shuffle on/off` — Shuffle groups
  ▸ `.copymode on/off` — Send as copy
  ▸ `.responder on/off` — Toggle DM reply
  ▸ `.responder <msg>` — Set reply text

━━━━ 📊 *INFO* ━━━━

  ▸ `.status` — Account status card
  ▸ `.help` — This help screen

━━━━ 🛡️ *SAFETY RULES* ━━━━

  ┌─────────────────────────┐
  │  ⏱️ 10s gap between groups      │
  │  ⏱️ 2min gap between messages   │
  │  🌙 Night pause: 00:00–06:00    │
  │  🗑️ Auto-remove bad groups      │
  └─────────────────────────┘

━━━━ 🤖 *BOT COMMANDS* ━━━━

  ▸ /start — Home screen
  ▸ /help — This help
  ▸ /redeem `<code>` — Activate plan

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💬 *SUPPORT:* @PHilobots
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
