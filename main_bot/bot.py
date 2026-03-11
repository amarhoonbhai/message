"""
Main Bot entry point for Group Message Scheduler.
"""

import logging
import asyncio
import signal
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    filters,
)
from telegram.request import HTTPXRequest

from config import MAIN_BOT_TOKEN
from db.database import init_database

# Import handlers
from main_bot.handlers.start import start_handler, home_callback
from main_bot.handlers.dashboard import (
    dashboard_callback,
    add_account_callback,
    toggle_send_mode_callback,
)
from main_bot.handlers.plans import my_plan_callback
from main_bot.handlers.referral import referral_callback
from main_bot.handlers.redeem import (
    redeem_code_callback,
    receive_redeem_code,
    redeem_command,
    WAITING_CODE,
)
from main_bot.handlers.admin import (
    admin_callback,
    admin_command,
    stats_command,
    broadcast_command,
    admin_stats_callback,
    admin_broadcast_callback,
    broadcast_target_callback,
    receive_broadcast_message,
    gen_code_callback,
    generate_command,
    admin_users_callback,
    set_nightmode_callback,
    nightmode_command,
    admin_health_callback,
    WAITING_BROADCAST_MESSAGE,
)
from main_bot.handlers.help import help_callback, help_command
from main_bot.handlers.account import (
    accounts_list_callback,
    manage_account_callback,
    disconnect_account_callback,
    confirm_disconnect_callback,
)
from main_bot.handlers.profile import profile_callback

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)

def create_application() -> Application:
    """Create and configure the bot application."""
    if not MAIN_BOT_TOKEN:
        raise ValueError("MAIN_BOT_TOKEN is not set in environment")

    # Hardened timeouts for stability
    request = HTTPXRequest(
        connect_timeout=30,
        read_timeout=60,
        write_timeout=60,
        pool_timeout=60,
    )

    application = (
        Application.builder()
        .token(MAIN_BOT_TOKEN)
        .request(request)
        .build()
    )

    # ============== Command Handlers ==============
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("redeem", redeem_command))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CommandHandler("generate", generate_command))
    application.add_handler(CommandHandler("nightmode", nightmode_command))

    # ============== Conversation Handlers ==============
    redeem_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(redeem_code_callback, pattern="^redeem_code$")],
        states={
            WAITING_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_redeem_code)],
        },
        fallbacks=[
            CallbackQueryHandler(home_callback, pattern="^home$"),
            CallbackQueryHandler(dashboard_callback, pattern="^dashboard$"),
        ],
        per_user=True,
        per_chat=True,
    )
    application.add_handler(redeem_conv)

    broadcast_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(broadcast_target_callback, pattern="^broadcast:")],
        states={
            WAITING_BROADCAST_MESSAGE: [
                MessageHandler(filters.TEXT | filters.PHOTO | filters.Document.ALL, receive_broadcast_message)
            ],
        },
        fallbacks=[
            CallbackQueryHandler(home_callback, pattern="^home$"),
            CallbackQueryHandler(admin_callback, pattern="^admin$"),
        ],
        per_user=True,
        per_chat=True,
    )
    application.add_handler(broadcast_conv)

    # ============== Callback Query Handlers ==============
    patterns = [
        ("^home$", home_callback),
        ("^dashboard$", dashboard_callback),
        ("^toggle_send_mode$", toggle_send_mode_callback),
        ("^add_account$", add_account_callback),
        ("^help$", help_callback),
        ("^my_plan$", my_plan_callback),
        ("^referral$", referral_callback),
        ("^profile$", profile_callback),
        ("^admin$", admin_callback),
        ("^admin_stats$", admin_stats_callback),
        ("^admin_broadcast$", admin_broadcast_callback),
        ("^gen_code:", gen_code_callback),
        ("^admin_users$", admin_users_callback),
        ("^accounts_list$", accounts_list_callback),
        ("^manage_account:", manage_account_callback),
        ("^disconnect_account:", disconnect_account_callback),
        ("^confirm_disconnect:", confirm_disconnect_callback),
        ("^admin_nightmode$", admin_nightmode_callback),
        ("^set_nightmode:", set_nightmode_callback),
        ("^admin_health$", admin_health_callback),
    ]
    
    for pattern, callback in patterns:
        application.add_handler(CallbackQueryHandler(callback, pattern=pattern))

    return application

async def main():
    """Start the bot."""
    logger.info("=" * 50)
    logger.info("Group Message Scheduler - Main Bot V3.3")
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
        
        logger.info("Main Bot is running (Async Polling)...")
        
        # Wait for shutdown signal
        await stop_event.wait()
        
        logger.info("Main Bot is stopping...")
        await application.updater.stop()
        await application.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
