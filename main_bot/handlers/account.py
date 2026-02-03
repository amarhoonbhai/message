"""
Account management handler for Main Bot.
"""

from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes

from db.models import get_session, disconnect_session
from main_bot.utils.keyboards import (
    get_manage_account_keyboard, 
    get_confirm_disconnect_keyboard,
    get_back_home_keyboard
)


async def manage_account_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show account management screen with details."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    session = await get_session(user_id)
    
    if not session:
        text = """
⚙️ *Manage Account*

❌ *No account connected*

You haven't linked a Telegram account yet.
Go to Dashboard → Add Account to connect.
"""
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_back_home_keyboard(),
        )
        return
    
    # Build account details
    phone = session.get("phone", "Unknown")
    connected = session.get("connected", False)
    connected_at = session.get("connected_at")
    
    status_emoji = "✅" if connected else "❌"
    status_text = "Connected" if connected else "Disconnected"
    
    if connected_at:
        connected_date = connected_at.strftime("%d %b %Y, %H:%M UTC")
    else:
        connected_date = "Unknown"
    
    text = f"""
⚙️ *Manage Account*

📱 *Phone:* `{phone}`
{status_emoji} *Status:* {status_text}
📅 *Connected:* {connected_date}

━━━━━━━━━━━━━━━━
⚠️ *Disconnecting will:*
• Stop all message forwarding
• Remove your session

You can reconnect anytime via Login Bot.
"""
    
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_manage_account_keyboard(),
    )


async def disconnect_account_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show disconnect confirmation screen."""
    query = update.callback_query
    await query.answer()
    
    text = """
⚠️ *Confirm Disconnect*

Are you sure you want to disconnect your Telegram account?

This will:
• Stop all message forwarding immediately
• Remove your saved session

You can reconnect anytime through the Login Bot.
"""
    
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_confirm_disconnect_keyboard(),
    )


async def confirm_disconnect_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Actually disconnect the account."""
    query = update.callback_query
    await query.answer("🔄 Disconnecting...")
    
    user_id = update.effective_user.id
    
    # Disconnect session in database
    await disconnect_session(user_id)
    
    text = """
✅ *Account Disconnected*

Your Telegram account has been disconnected.
Message forwarding has stopped.

You can reconnect anytime via the Login Bot.
"""
    
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_back_home_keyboard(),
    )
