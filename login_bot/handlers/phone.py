"""
Phone and API credentials input handler for Login Bot.
"""

import re
from telegram import Update
from telegram.ext import ContextTypes

from login_bot.utils.keyboards import get_phone_input_keyboard, get_confirm_phone_keyboard, get_cancel_keyboard, get_api_input_keyboard


async def add_account_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start add account flow - ask for API ID first."""
    query = update.callback_query
    await query.answer()
    
    text = """
🔑 *Step 1: Enter Your API ID*

Get your API ID from: https://my.telegram.org

1️⃣ Go to my.telegram.org
2️⃣ Log in with your phone number
3️⃣ Click "API development tools"
4️⃣ Create an app (any name) or use existing
5️⃣ Copy your *API ID* (numbers only)

Send your API ID below:
"""
    
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_api_input_keyboard(),
        disable_web_page_preview=True,
    )
    
    # Set state
    context.user_data["state"] = "waiting_api_id"


async def receive_api_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process received API ID."""
    api_id = update.message.text.strip()
    
    # Validate API ID (should be numbers only)
    if not api_id.isdigit():
        await update.message.reply_text(
            "❌ *Invalid API ID*\n\n"
            "API ID should contain only numbers.\n"
            "Example: `12345678`",
            parse_mode="Markdown",
            reply_markup=get_api_input_keyboard(),
        )
        return
    
    # Store API ID
    context.user_data["api_id"] = int(api_id)
    context.user_data["state"] = "waiting_api_hash"
    
    text = """
🔐 *Step 2: Enter Your API Hash*

Now send your *API Hash* from the same page.

It's a long string of letters and numbers.
Example: `a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6`
"""
    
    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_api_input_keyboard(),
    )


async def receive_api_hash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process received API Hash."""
    api_hash = update.message.text.strip()
    
    # Validate API Hash (should be alphanumeric, typically 32 chars)
    if len(api_hash) < 20 or not api_hash.isalnum():
        await update.message.reply_text(
            "❌ *Invalid API Hash*\n\n"
            "API Hash should be a long alphanumeric string (32 characters).\n"
            "Example: `a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6`",
            parse_mode="Markdown",
            reply_markup=get_api_input_keyboard(),
        )
        return
    
    # Store API Hash
    context.user_data["api_hash"] = api_hash
    context.user_data["state"] = "waiting_phone"
    
    text = """
📱 *Step 3: Enter Your Phone Number*

Enter your phone number with country code.
Example: `+91XXXXXXXXXX`

Make sure to include the + sign.
"""
    
    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_phone_input_keyboard(),
    )


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
    
    api_id = context.user_data.get("api_id", "Not set")
    
    text = f"""
✅ *Confirm Your Details:*

🔑 API ID: `{api_id}`
🔐 API Hash: `{context.user_data.get("api_hash", "")[:8]}...`
📱 Phone: `{phone}`

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
