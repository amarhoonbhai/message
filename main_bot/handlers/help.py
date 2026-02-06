"""
Help handler for Main Bot.
"""

from telegram import Update
from telegram.ext import ContextTypes

from main_bot.utils.keyboards import get_back_home_keyboard


HELP_TEXT = """
```
╔══════════════════════════════╗
║     ❓ HELP & COMMANDS ❓     ║
╚══════════════════════════════╝
```

〔 📖 *QUICK START GUIDE* 〕

① Connect your Telegram account
② Open *Saved Messages*
③ Use dot commands below
④ Send ads → Auto-forwarded! ⚡

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎮 *DOT COMMANDS*
╭─────────────────────────────╮
│ `.addgroup <url>` ─ Add     │
│ `.rmgroup <url>` ─ Remove   │
│ `.groups` ─ List all        │
│ `.status` ─ Check status    │
│ `.interval <min>` ─ Delay   │
│ `.help` ─ Show commands     │
╰─────────────────────────────╯

🛡️ *SAFETY SYSTEM*
╭─────────────────────────────╮
│  ⏱️ 60s between groups      │
│  ⏱️ 5min between messages   │
│  🌙 Night: 00:00–06:00 IST  │
│  🔄 Auto-remove bad groups  │
╰─────────────────────────────╯

💬 *BOT COMMANDS*
╭─────────────────────────────╮
│  /start ─ Home screen       │
│  /dashboard ─ Dashboard     │
│  /redeem <code> ─ Premium   │
│  /help ─ This help          │
╰─────────────────────────────╯

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
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
