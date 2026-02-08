"""
Account management handler for Main Bot.
"""

from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes

from db.models import get_all_user_sessions, get_session, disconnect_session
from main_bot.utils.keyboards import (
    get_account_selection_keyboard,
    get_manage_account_keyboard, 
    get_confirm_disconnect_keyboard,
    get_back_home_keyboard
)


async def accounts_list_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show list of connected accounts."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    sessions = await get_all_user_sessions(user_id)
    
    if not sessions:
        text = """
⚙️ *MANAGE ACCOUNTS*
━━━━━━━━━━━━━━━━━━━━━━━━

🔴 *STATUS:* No accounts connected

💡 *NEXT STEPS*

➳ Go to Dashboard
➳ Tap "Add Account"
➳ Connect via Login Bot
"""
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_back_home_keyboard(),
        )
        return
    
    text = """
⚙️ *MANAGE ACCOUNTS*
━━━━━━━━━━━━━━━━━━━━━━━━

Select an account to view details or disconnect:
"""
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_account_selection_keyboard(sessions),
    )


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
    status_text = "Connected" if connected else "Disconnected"
    
    if connected_at:
        connected_date = connected_at.strftime("%d %b %Y, %H:%M UTC")
    else:
        connected_date = "Unknown"
    
    text = f"""
⚙️ *MANAGE ACCOUNT*
━━━━━━━━━━━━━━━━━━━━━━━━

{status_icon} *STATUS:* {status_text}

📱 *ACCOUNT INFO*

❊ Phone: `{phone}`
❊ Since: {connected_date}

━━━━ ⚠️ *WARNING* ⚠️ ━━━━

❊ Stops forwarding for THIS account
❊ Removes this session
❊ You can reconnect later
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
    
    text = f"""
⚠️ *CONFIRM DISCONNECT*
━━━━━━━━━━━━━━━━━━━━━━━━

📱 *Account:* `{phone}`

❓ *ARE YOU SURE?*

This action will:
❌ Stop forwarding NOW for `{phone}`
🗑️ Remove this saved session

✅ You can reconnect later
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
    
    text = f"""
✅ *DISCONNECTED*
━━━━━━━━━━━━━━━━━━━━━━━━

📱 *Account:* `{phone}`

📋 *STATUS UPDATE*

✅ Session removed
✅ Forwarding stopped for this account

You can reconnect anytime
via the Login Bot.
"""
    
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_back_home_keyboard(),
    )
