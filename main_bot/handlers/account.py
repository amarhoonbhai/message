"""
Account management handler for Main Bot.
"""

from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes

from db.models import get_all_user_sessions, get_session, disconnect_session, get_account_stats
from main_bot.utils.keyboards import (
    get_account_selection_keyboard,
    get_manage_account_keyboard, 
    get_confirm_disconnect_keyboard,
    get_back_home_keyboard
)
from shared.utils import escape_markdown

def format_date(dt: datetime) -> str:
    if not dt:
        return "Unknown"
    return dt.strftime("%d %b %Y, %H:%M UTC")

async def accounts_list_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show list of connected accounts."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    sessions = await get_all_user_sessions(user_id)
    
    if not sessions:
        text = """
⚙️ *ACCOUNT MANAGER*

🔴 *STATUS:* No accounts connected

🚀 *GET STARTED NOW!*
1️⃣ Go back to home
2️⃣ Tap "➕ Add Account"
3️⃣ Link your account securely

*Your API credentials are safe and encrypted.*
"""
        from shared.utils import safe_reply
        await safe_reply(update, text, reply_markup=get_back_home_keyboard())
        return
    
    text = """
⚙️ *ACCOUNT MANAGER*

Select a connected account below to view its live stats or to disconnect it:
"""
    from shared.utils import safe_reply
    await safe_reply(update, text, reply_markup=get_account_selection_keyboard(sessions))


async def manage_account_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show specific account details."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    phone = query.data.split(":")[1]
    
    session = await get_session(user_id, phone)
    
    if not session:
        await query.answer("❌ Account not found", show_alert=True)
        return
    
    # Build account details
    connected = session.get("connected", False)
    connected_at = session.get("connected_at")
    
    status_icon = "🟢" if connected else "🔴"
    status_text = "CONNECTED" if connected else "DISCONNECTED"
    
    connected_date = format_date(connected_at)
    
    stats = await get_account_stats(user_id, phone)
    total_sent = stats.get("total_sent", 0)
    success_rate = stats.get("success_rate", 0)
    last_active = format_date(stats.get("last_active"))
    
    escaped_phone = escape_markdown(phone)
    text = f"""
📱 *ACCOUNT PROFILE*

{status_icon} *STATUS:* {status_text}

👤 *DETAILS*
📞 *Phone:* `{escaped_phone}`
🔗 *Linked On:* {connected_date}

📊 *LIFETIME STATS*
📤 *Messages Sent:* {total_sent}
🎯 *Success Rate:* {success_rate}%
⏱️ *Last Active:* {last_active}

⚠️ *DANGER ZONE* ⚠️
Disconnecting removes your session forever and immediately stops all forwarding.
"""
    
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_manage_account_keyboard(phone),
    )


async def disconnect_account_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show disconnect confirmation screen."""
    query = update.callback_query
    await query.answer()
    
    phone = query.data.split(":")[1]
    
    escaped_phone = escape_markdown(phone)
    text = f"""
⚠️ *CRITICAL ACTION*

📱 *Target:* `{escaped_phone}`

❗ *Are you absolutely sure you want to disconnect?*

*This will immediately:*
❌ Stop all message forwarding
🗑️ Delete your stored sessions
🔴 Require re-login via OTP to reconnect

👇 *Please confirm your choice below*
"""
    
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_confirm_disconnect_keyboard(phone),
    )


async def confirm_disconnect_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Actually disconnect the account."""
    query = update.callback_query
    await query.answer("🔄 Disconnecting...")
    
    user_id = update.effective_user.id
    phone = query.data.split(":")[1]
    
    # Disconnect session in database for specific phone
    await disconnect_session(user_id, phone)
    
    escaped_phone = escape_markdown(phone)
    text = f"""
✅ *SUCCESSFULLY DISCONNECTED*

📱 *Account:* `{escaped_phone}`

Your session has been securely wiped and forwarding has immediately halted.

You can reconnect anytime via the **Add Account** button.
"""
    
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_back_home_keyboard(),
    )
