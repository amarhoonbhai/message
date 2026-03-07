"""
Account management handlers for Login Bot.
"""

from telegram import Update
from telegram.ext import ContextTypes
from db.models import get_all_user_sessions, disconnect_session
from login_bot.utils.keyboards import (
    get_manage_accounts_keyboard, 
    get_account_options_keyboard,
    get_disconnect_confirm_keyboard,
    get_login_welcome_keyboard
)

async def manage_accounts_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all accounts for the user."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    accounts = await get_all_user_sessions(user_id)
    
    if not accounts:
        await query.edit_message_text(
            "📭 *No accounts connected yet.*\n\nTap below to add your first account!",
            parse_mode="Markdown",
            reply_markup=get_manage_accounts_keyboard([])
        )
        return
    
    text = f"📱 *Your Connected Accounts ({len(accounts)})*\n\n"
    text += "Select an account to manage or disconnect it."
    
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_manage_accounts_keyboard(accounts)
    )

async def manage_acc_details_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show options for a specific account."""
    query = update.callback_query
    await query.answer()
    
    phone = query.data.split(":")[1]
    
    text = f"""
🔧 *Manage Account:* `{phone}`

What would you like to do with this account?
"""
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_account_options_keyboard(phone)
    )

async def disconnect_acc_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask for confirmation to disconnect."""
    query = update.callback_query
    await query.answer()
    
    phone = query.data.split(":")[1]
    
    text = f"⚠️ *Confirm Disconnection*\n\nAre you sure you want to disconnect `{phone}`? This will stop all forwarding tasks for this account."
    
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_disconnect_confirm_keyboard(phone)
    )

async def confirm_disconnect_acc_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Execute disconnection."""
    query = update.callback_query
    user_id = update.effective_user.id
    phone = query.data.split(":")[1]
    
    await disconnect_session(user_id, phone)
    await query.answer("✅ Account Disconnected")
    
    # Go back to account list
    await manage_accounts_callback(update, context)

async def login_home_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Back to home screen."""
    from login_bot.handlers.start import WELCOME_TEXT
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    first_name = user.first_name or "User"
    greeting = f"👋 *Greeting {first_name},*\n\n"
    
    await query.edit_message_text(
        greeting + WELCOME_TEXT,
        parse_mode="Markdown",
        reply_markup=get_login_welcome_keyboard()
    )
