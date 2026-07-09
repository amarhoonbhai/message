"""
Start and welcome handler for Login Bot.
"""

from telegram import Update
from telegram.ext import ContextTypes

from db.models import create_user
from login_bot.utils.keyboards import get_login_welcome_keyboard
from shared.utils import escape_markdown


WELCOME_TEXT = """
🔐 *SECURE LOGIN PORTAL*

To connect your account, you will need:
1️⃣ Your **API ID** & **API Hash** (from [my.telegram.org](https://my.telegram.org))
2️⃣ Your **Phone Number**
3️⃣ The **OTP** sent to your Telegram

👇 *Tap below to start the connection process*
"""


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command - shows welcome and account status."""
    user = update.effective_user
    user_id = user.id
    
    # 1. Enforce channel join check first
    from config import CHANNEL_USERNAME, OWNER_ID
    if CHANNEL_USERNAME and user_id != OWNER_ID:
        channel = CHANNEL_USERNAME.strip()
        if not channel.startswith("@"):
            channel = f"@{channel}"
            
        is_joined = False
        try:
            member = await context.bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status in ["member", "creator", "administrator", "restricted"]:
                is_joined = True
        except Exception:
            is_joined = False
            
        if not is_joined:
            text = f"""
⚠️ *MEMBERSHIP REQUIRED*

To connect your accounts, you must be a member of our official channel: **{channel}**.

📢 *Join to receive updates, guides, and support!*

👇 *Please join the channel and send /start again:*
"""
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{CHANNEL_USERNAME}")]
            ])
            await update.message.reply_text(
                text,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
            return
            
    # Ensure user exists in db
    await create_user(user_id)
    
    # Get account stats
    from db.models import get_all_user_sessions
    accounts = await get_all_user_sessions(user_id)
    acc_count = len(accounts)
    
    first_name = user.first_name or "User"
    greeting = f"👋 *Greeting {escape_markdown(first_name)},*\n\n"
    
    # Dynamic status line
    if acc_count > 0:
        status_line = f"📱 *STATUS:* You have `{acc_count}` account(s) connected.\n\n"
    else:
        status_line = "⚪ *STATUS:* No accounts connected yet.\n\n"
    
    await update.message.reply_text(
        greeting + status_line + WELCOME_TEXT,
        parse_mode="Markdown",
        reply_markup=get_login_welcome_keyboard(),
    )

