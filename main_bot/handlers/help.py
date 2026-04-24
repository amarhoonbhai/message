"""
Help handler for Main Bot.
"""

from telegram import Update
from telegram.ext import ContextTypes

from main_bot.utils.keyboards import get_back_home_keyboard


HELP_TEXT = """
📘 *HELP & DOCUMENTATION*

🚀 *QUICK START GUIDE*
1️⃣ Go to Dashboard > Add Account
2️⃣ Login securely via Login Bot
3️⃣ Go to your *Saved Messages*
4️⃣ Add target groups using `.addgroup`
5️⃣ Send any message to Saved Messages!

📝 *WORKER COMMANDS* (Use in Saved Messages)

*Group Management:*
🔸 `.addgroup <url>` — Add a new group
🔸 `.rmgroup <url/number>` — Remove a group
🔸 `.groups` — List your active groups

*Settings & Controls:*
🔸 `.interval <min>` — Set delay between loops
🔸 `.shuffle on/off` — Randomize group sending order
🔸 `.copymode on/off` — Send as new message (hides "Forwarded from")
🔸 `.sendmode <seq/rot/rand>` — Change message distribution pattern
🔸 `.responder <msg>` — Set auto-reply for incoming DMs
🔸 `.status` — Check your live worker status

*General:*
🔸 `.help` — Show worker commands list

🛡️ *SAFETY & LIMITS*

✅ *Group Gap:* 10s between each group
✅ *Message Gap:* 2m between different messages
✅ *Night Mode:* Pauses automatically (12AM-6AM IST)
✅ *Auto-Clean:* Invalid groups are removed automatically

🤖 *BOT MANAGER COMMANDS*
🔹 `/start` — Return home
🔹 `/dashboard` — View live stats
🔹 `/redeem <code>` — Apply premium code
🔹 `/help` — Show this menu

👨‍💻 *SUPPORT & UPDATES:* @PHilobots
"""


async def help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help screen."""
    query = update.callback_query
    await query.answer()
    
    from shared.utils import safe_reply
    await safe_reply(update, HELP_TEXT, reply_markup=get_back_home_keyboard())


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    await update.message.reply_text(
        HELP_TEXT,
        parse_mode="Markdown",
        reply_markup=get_back_home_keyboard(),
    )
