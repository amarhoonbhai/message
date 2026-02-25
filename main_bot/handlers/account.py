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


async def accounts_list_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show list of connected accounts."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    sessions = await get_all_user_sessions(user_id)
    
    if not sessions:
        text = """
⚙️ *MANAGE ACCOUNTS*
╔══════════════════════════╗

🔴 *No accounts connected*

╚══════════════════════════╝

💡 *NEXT STEPS*

  1️⃣ Go to Dashboard
  2️⃣ Tap \"➕ Add Account\"
  3️⃣ Connect via Login Bot
"""
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_back_home_keyboard(),
        )
        return
    
    # Build account list with stats
    accounts_text = ""
    for idx, s in enumerate(sessions, 1):
        phone = s.get("phone", "Unknown")
        status_icon = "🟢" if s.get("connected") else "🔴"
        connected_at = s.get("connected_at")
        
        if connected_at:
            since = connected_at.strftime("%d %b %Y")
        else:
            since = "Unknown"
        
        accounts_text += f"  {status_icon} `{phone}` — Since {since}\n"
    
    text = f"""
⚙️ *MANAGE ACCOUNTS*
╔══════════════════════════╗

📱 *Connected:* {len(sessions)} account(s)

{accounts_text}
╚══════════════════════════╝

👇 _Select an account to manage:_
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
    
    # Get account stats
    try:
        stats = await get_account_stats(user_id, phone)
        total_sent = stats.get("total_sent", 0)
        success_rate = stats.get("success_rate", 0)
        stats_line = f"  ▸ Total Sent: *{total_sent}* msgs\n  ▸ Success Rate: *{success_rate}%*\n"
    except Exception:
        stats_line = ""
    
    text = f"""
⚙️ *ACCOUNT DETAILS*
╔══════════════════════════╗

{status_icon} *{status_text}*

╚══════════════════════════╝

📱 *INFO*

  ▸ Phone: `{phone}`
  ▸ Connected: _{connected_date}_
{stats_line}
━━━━ ⚠️ *DISCONNECT* ⚠️ ━━━━

  ┌─────────────────────────┐
  │  ❌ Stops forwarding for THIS acct  │
  │  🗑️ Removes this session            │
  │  ✅ You can reconnect later         │
  └─────────────────────────┘
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
╔══════════════════════════╗

📱 Account: `{phone}`

❓ *ARE YOU SURE?*

  ❌ Stop forwarding NOW
  🗑️ Remove saved session
  ✅ Reconnect anytime later

╚══════════════════════════╝
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
╔══════════════════════════╗

📱 `{phone}` removed

╚══════════════════════════╝

📋 *STATUS UPDATE*

  ✅ Session removed
  ✅ Forwarding stopped
  🔄 Reconnect anytime via Login Bot
"""
    
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_back_home_keyboard(),
    )
