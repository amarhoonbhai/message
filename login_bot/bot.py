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
from db.database import init_indexes

# Import handlers
from login_bot.handlers.start import start_handler, help_callback
from login_bot.handlers.phone import (
    add_account_callback, receive_phone_number,
    edit_phone_callback, cancel_callback,
    receive_api_id, receive_api_hash
)
from login_bot.handlers.otp import (
    send_otp_callback, resend_otp_callback, otp_keypad_callback
)
from login_bot.handlers.twofa import receive_2fa_password

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def create_application() -> Application:
    """Create and configure the bot application."""
    
    if not LOGIN_BOT_TOKEN:
        raise ValueError("LOGIN_BOT_TOKEN is not set in environment")
    
    application = Application.builder().token(LOGIN_BOT_TOKEN).build()
    
    # ============== Command Handlers ==============
    application.add_handler(CommandHandler("start", start_handler))
    
    # ============== Callback Query Handlers ==============
    
    # Login flow
    application.add_handler(CallbackQueryHandler(add_account_callback, pattern="^add_account$"))
    application.add_handler(CallbackQueryHandler(edit_phone_callback, pattern="^edit_phone$"))
    application.add_handler(CallbackQueryHandler(cancel_callback, pattern="^cancel$"))
    
    # OTP flow
    application.add_handler(CallbackQueryHandler(send_otp_callback, pattern="^send_otp$"))
    application.add_handler(CallbackQueryHandler(resend_otp_callback, pattern="^resend_otp$"))
    application.add_handler(CallbackQueryHandler(otp_keypad_callback, pattern="^otp:"))
    
    # Help
    application.add_handler(CallbackQueryHandler(help_callback, pattern="^help$"))
    
    # ============== Message Handlers ==============
    
    # Phone number, API credentials, and 2FA input
    async def handle_text_message(update, context):
        """Route text messages based on state."""
        state = context.user_data.get("state")
        
        if state == "waiting_api_id":
            await receive_api_id(update, context)
        elif state == "waiting_api_hash":
            await receive_api_hash(update, context)
        elif state == "waiting_phone":
            await receive_phone_number(update, context)
        elif state == "waiting_2fa":
            await receive_2fa_password(update, context)
        # Ignore other messages
    
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    
    return application


async def main():
    """Main entry point."""
    logger.info("Starting Login Bot...")
    
    # Initialize database indexes
    await init_indexes()
    
    # Create and run application
    application = create_application()
    
    # Start polling
    await application.initialize()
    await application.start()
    await application.updater.start_polling(drop_pending_updates=True)
    
    logger.info("Login Bot is running! Press Ctrl+C to stop.")
    
    # Keep running
    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
    finally:
        await application.updater.stop()
        await application.stop()
        await application.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
