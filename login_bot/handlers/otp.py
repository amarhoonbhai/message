"""
OTP handling with inline keypad for Login Bot.
Uses per-user API credentials collected during login.
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import (
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
    FloodWaitError,
    SessionPasswordNeededError,
)


from db.models import create_session, create_user
from login_bot.utils.keyboards import (
    get_otp_keypad, get_resend_otp_keyboard, get_2fa_keyboard, get_success_keyboard
)

logger = logging.getLogger(__name__)

# Store Telethon clients temporarily during login
_login_clients = {}


def get_otp_display(otp: str) -> str:
    """Generate OTP display string."""
    display = ""
    for i in range(5):
        if i < len(otp):
            display += f"{otp[i]} "
        else:
            display += "_ "
    return display.strip()


async def send_otp_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send OTP to user's phone using global API credentials."""
    query = update.callback_query
    user_id = update.effective_user.id
    
    phone = context.user_data.get("phone")
    
    if not phone:
        await query.answer("❌ Phone number not found. Start over.", show_alert=True)
        return
    
    await query.answer("📤 Sending OTP...")
    
    api_id = context.user_data.get("api_id")
    api_hash = context.user_data.get("api_hash")
    
    if not api_id or not api_hash:
        await query.answer("❌ API Credentials not found. Start over.", show_alert=True)
        return

    try:
        # Create Telethon client with PER-USER API credentials
        client = TelegramClient(
            StringSession(),
            api_id,
            api_hash,
            device_model="Group Message Scheduler",
            system_version="1.0",
            app_version="1.0"
        )
        
        await client.connect()
        
        # Send code
        result = await client.send_code_request(phone)
        
        # Store client and code hash
        _login_clients[user_id] = {
            "client": client,
            "phone": phone,
            "phone_code_hash": result.phone_code_hash,
        }
        
        # Initialize OTP buffer
        context.user_data["otp_buffer"] = ""
        context.user_data["state"] = "waiting_otp"
        
        text = f"""
🔑 *Enter OTP Code*

📱 Phone: `{phone}`
🔢 OTP:  `{get_otp_display("")}`

Tap digits below 👇
"""
        
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_otp_keypad(""),
        )
        
    except FloodWaitError as e:
        await query.edit_message_text(
            f"⏳ *Too Many Attempts*\n\n"
            f"Please wait {e.seconds} seconds before trying again.",
            parse_mode="Markdown",
            reply_markup=get_resend_otp_keyboard(),
        )
    except Exception as e:
        logger.error(f"Error sending OTP: {e}")
        await query.edit_message_text(
            f"❌ *Error Sending OTP*\n\n{str(e)}",
            parse_mode="Markdown",
            reply_markup=get_resend_otp_keyboard(),
        )


async def resend_otp_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Resend OTP."""
    await send_otp_callback(update, context)


async def otp_keypad_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle OTP keypad button presses."""
    query = update.callback_query
    user_id = update.effective_user.id
    data = query.data
    
    if not data.startswith("otp:"):
        return
    
    action = data.split(":")[1]
    otp_buffer = context.user_data.get("otp_buffer", "")
    phone = context.user_data.get("phone", "Unknown")
    
    # Handle actions
    if action == "back":
        # Remove last digit
        otp_buffer = otp_buffer[:-1]
        await query.answer()
        
    elif action == "clear":
        # Clear all
        otp_buffer = ""
        await query.answer("Cleared")
        
    elif action == "submit":
        # Submit OTP
        if len(otp_buffer) < 5:
            await query.answer("❌ OTP too short", show_alert=True)
            return
        
        await verify_otp(update, context, otp_buffer)
        return
        
    elif action.isdigit():
        # Add digit (max 6 digits)
        if len(otp_buffer) < 6:
            otp_buffer += action
            await query.answer()
        else:
            await query.answer("Max digits reached")
    
    # Update buffer
    context.user_data["otp_buffer"] = otp_buffer
    
    # Update display
    text = f"""
🔑 *Enter OTP Code*

📱 Phone: `{phone}`
🔢 OTP:  `{get_otp_display(otp_buffer)}`

Tap digits below 👇
"""
    
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_otp_keypad(otp_buffer),
    )


async def verify_otp(update: Update, context: ContextTypes.DEFAULT_TYPE, otp: str):
    """Verify OTP and sign in."""
    query = update.callback_query
    user_id = update.effective_user.id
    
    login_data = _login_clients.get(user_id)
    
    if not login_data:
        await query.answer("❌ Session expired. Start over.", show_alert=True)
        return
    
    client = login_data["client"]
    phone = login_data["phone"]
    phone_code_hash = login_data["phone_code_hash"]
    
    await query.answer("🔄 Verifying...")
    
    try:
        # Attempt sign in
        await client.sign_in(
            phone=phone,
            code=otp,
            phone_code_hash=phone_code_hash
        )
        
        # Success! Save session
        await save_session_and_complete(update, context, client, phone)
        
    except SessionPasswordNeededError:
        # 2FA required
        context.user_data["state"] = "waiting_2fa"
        
        text = """
🔒 *Two-Step Verification Required*

Your account has 2FA enabled.
Please enter your Telegram 2FA password:
"""
        
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_2fa_keyboard(),
        )
        
    except PhoneCodeInvalidError:
        await query.edit_message_text(
            "❌ *Invalid OTP*\n\nThe code you entered is incorrect. Try again.",
            parse_mode="Markdown",
            reply_markup=get_otp_keypad(context.user_data.get("otp_buffer", "")),
        )
        
    except PhoneCodeExpiredError:
        await query.edit_message_text(
            "⏰ *OTP Expired*\n\nThe code has expired. Please request a new one.",
            parse_mode="Markdown",
            reply_markup=get_resend_otp_keyboard(),
        )
        
    except FloodWaitError as e:
        await query.edit_message_text(
            f"⏳ *Too Many Attempts*\n\nPlease wait {e.seconds} seconds.",
            parse_mode="Markdown",
            reply_markup=get_resend_otp_keyboard(),
        )
        
    except Exception as e:
        logger.error(f"OTP verification error: {e}")
        await query.edit_message_text(
            f"❌ *Error*\n\n{str(e)}",
            parse_mode="Markdown",
            reply_markup=get_resend_otp_keyboard(),
        )


async def save_session_and_complete(
    update: Update, 
    context: ContextTypes.DEFAULT_TYPE, 
    client: TelegramClient, 
    phone: str,
):
    """Save session with global API credentials and show success screen."""
    query = update.callback_query
    user_id = update.effective_user.id
    
    try:
        # Get session string
        session_string = client.session.save()
        
        # Get API credentials from context
        api_id = context.user_data.get("api_id")
        api_hash = context.user_data.get("api_hash")
        
        # Save to database WITH per-user API credentials
        await create_user(user_id)
        await create_session(user_id, phone, session_string, api_id, api_hash)
        
        # Disconnect client
        await client.disconnect()
        
        # Clean up
        if user_id in _login_clients:
            del _login_clients[user_id]
        
        context.user_data.clear()

        # Fetch the user's current plan and build success text
        from db.models import get_plan
        from shared.utils import build_connection_success_text
        plan = await get_plan(user_id)
        text = build_connection_success_text(phone, plan)
        
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_success_keyboard(),
        )
        
    except Exception as e:
        logger.error(f"Error saving session: {e}")
        await query.edit_message_text(
            f"❌ *Error Saving Session*\n\n{str(e)}",
            parse_mode="Markdown",
        )
