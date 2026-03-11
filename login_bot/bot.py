"""
Login Bot entry point for Group Message Scheduler.
"""

import logging
import asyncio
import signal
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
from telegram.request import HTTPXRequest

from config import LOGIN_BOT_TOKEN
from db.database import init_database

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
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)

def create_application() -> Application:
    """Create and configure the bot application."""
    if not LOGIN_BOT_TOKEN:
        raise ValueError("LOGIN_BOT_TOKEN is not set in environment")

    # Hardened timeouts for stability
    request = HTTPXRequest(
        connect_timeout=30,
        read_timeout=60,
        write_timeout=60,
        pool_timeout=60,
    )

    application = (
        Application.builder()
        .token(LOGIN_BOT_TOKEN)
        .request(request)
        .build()
    )

    # ============== Command Handlers ==============
    application.add_handler(CommandHandler("start", start_handler))

    # ============== Callback Query Handlers ==============
    patterns = [
        ("^add_account$", add_account_callback),
        ("^edit_phone$", edit_phone_callback),
        ("^cancel$", cancel_callback),
        ("^send_otp$", send_otp_callback),
        ("^resend_otp$", resend_otp_callback),
        ("^otp:", otp_keypad_callback),
        ("^manage_accounts$", manage_accounts_callback),
        ("^manage_acc:", manage_acc_details_callback),
        ("^disconnect_acc:", disconnect_acc_callback),
        ("^confirm_disc_acc:", confirm_disconnect_acc_callback),
        ("^login_home$", login_home_callback),
    ]
    
    for pattern, callback in patterns:
        application.add_handler(CallbackQueryHandler(callback, pattern=pattern))

    # ============== Message Handlers ==============
    async def handle_text_message(update, context):
        """Route text messages based on state."""
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
    logger.info("=" * 50)
    logger.info("Group Message Scheduler - Login Bot V3.3")
    logger.info("=" * 50)

    # Initialize database within the same loop
    await init_database()

    # Build application
    application = create_application()
    
    # Setup stop event for graceful shutdown
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: stop_event.set())
        except NotImplementedError:
            pass

    async with application:
        await application.initialize()
        await application.start()
        await application.updater.start_polling(drop_pending_updates=True)
        
        logger.info("Login Bot is running (Async Polling)...")
        
        # Wait for shutdown signal
        await stop_event.wait()
        
        logger.info("Login Bot is stopping...")
        await application.updater.stop()
        await application.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
