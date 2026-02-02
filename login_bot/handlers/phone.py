"""
Phone input handler for Login Bot.
"""

import re
from telegram import Update
from telegram.ext import ContextTypes

from login_bot.utils.keyboards import get_phone_input_keyboard, get_confirm_phone_keyboard, get_cancel_keyboard


async def add_account_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start add account flow - ask for phone number."""
    query = update.callback_query
    await query.answer()
    
    text = """
📱 *Enter your phone number with country code:*

Example: `+91XXXXXXXXXX`

Make sure to include the + sign and country code.
"""
    
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_phone_input_keyboard(),
    )
    
    # Set state
    context.user_data["state"] = "waiting_phone"


async def receive_phone_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process received phone number."""
    state = context.user_data.get("state")
    
    if state != "waiting_phone":
        return
    
    phone = update.message.text.strip()
    
    # Validate phone number
    if not phone.startswith("+"):
        await update.message.reply_text(
            "❌ Phone number must start with + (country code)\n\n"
            "Example: `+91XXXXXXXXXX`",
            parse_mode="Markdown",
            reply_markup=get_phone_input_keyboard(),
        )
        return
    
    # Remove spaces and dashes
    phone = re.sub(r"[\s\-]", "", phone)
    
    # Check if it contains only digits after +
    if not re.match(r"^\+\d{10,15}$", phone):
        await update.message.reply_text(
            "❌ Invalid phone number format.\n\n"
            "Please enter a valid phone number with country code.\n"
            "Example: `+91XXXXXXXXXX`",
            parse_mode="Markdown",
            reply_markup=get_phone_input_keyboard(),
        )
        return
    
    # Store phone and ask for confirmation
    context.user_data["phone"] = phone
    context.user_data["state"] = "confirm_phone"
    
    text = f"""
✅ *Confirm your number:*

📱 `{phone}`

Send OTP now?
"""
    
    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_confirm_phone_keyboard(),
    )


async def edit_phone_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Go back to phone input."""
    query = update.callback_query
    await query.answer()
    
    text = """
📱 *Enter your phone number with country code:*

Example: `+91XXXXXXXXXX`

Make sure to include the + sign and country code.
"""
    
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_phone_input_keyboard(),
    )
    
    context.user_data["state"] = "waiting_phone"


async def cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel the login process."""
    query = update.callback_query
    await query.answer()
    
    # Clear user data
    context.user_data.clear()
    
    text = """
❌ *Login Cancelled*

You can try again anytime.
"""
    
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_cancel_keyboard(),
    )
