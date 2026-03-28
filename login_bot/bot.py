"""
Login Bot entry point for Group Message Scheduler.
"""

import logging
import asyncio
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from config import LOGIN_BOT_TOKEN
from shared.bot_init import setup_logging, create_base_application, run_bot_gracefully
from shared.decorators import require_premium

# Import handlers
from login_bot.handlers.start import start_handler
from login_bot.handlers.phone import (
    add_account_callback,
    receive_phone_number,
    receive_api_id,
    receive_api_hash,
    edit_phone_callback,
    cancel_callback,
)
from login_bot.handlers.otp import (
    send_otp_callback,
    resend_otp_callback,
    otp_keypad_callback,
)
from login_bot.handlers.twofa import receive_2fa_password
from login_bot.handlers.manage import (
    manage_accounts_callback,
    manage_acc_details_callback,
    disconnect_acc_callback,
    confirm_disconnect_acc_callback,
    login_home_callback
)

# Configure logging
logger = setup_logging()

def create_application() -> Application:
    """Create and configure the bot application."""
    application = create_base_application(LOGIN_BOT_TOKEN)

    # ============== Command Handlers ==============
    # /start is always allowed
    application.add_handler(CommandHandler("start", start_handler))

    # ============== Callback Query Handlers ==============
    # Protected functional callbacks
    patterns = [
        ("^add_account$", require_premium(add_account_callback)),
        ("^edit_phone$", require_premium(edit_phone_callback)),
        ("^cancel$", cancel_callback), # Cancel should be allowed
        ("^send_otp$", require_premium(send_otp_callback)),
        ("^resend_otp$", require_premium(resend_otp_callback)),
        ("^otp:", require_premium(otp_keypad_callback)),
        ("^manage_accounts$", require_premium(manage_accounts_callback)),
        ("^manage_acc:", require_premium(manage_acc_details_callback)),
        ("^disconnect_acc:", require_premium(disconnect_acc_callback)),
        ("^confirm_disc_acc:", require_premium(confirm_disconnect_acc_callback)),
        ("^login_home$", login_home_callback),
    ]
    
    for pattern, callback in patterns:
        application.add_handler(CallbackQueryHandler(callback, pattern=pattern))

    # ============== Message Handlers ==============
    @require_premium
    async def handle_text_message(update, context):
        """Route text messages based on state. Protected by premium check."""
        if not update.message or not update.message.text:
            return

        state = context.user_data.get("state")

        if state == "waiting_api_id":
            await receive_api_id(update, context)
        elif state == "waiting_api_hash":
            await receive_api_hash(update, context)
        elif state == "waiting_phone":
            await receive_phone_number(update, context)
        elif state == "waiting_2fa":
            await receive_2fa_password(update, context)

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    return application

async def main():
    """Start the bot."""
    print("=" * 50)
    print("Group Message Scheduler - Login Bot V3.3")
    print("=" * 50)

    application = create_application()
    await run_bot_gracefully(application, "Login Bot")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
