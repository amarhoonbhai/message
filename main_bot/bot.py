"""
Main Bot entry point for Group Message Scheduler.
"""

import logging
import asyncio
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    filters,
)

from config import MAIN_BOT_TOKEN
from db.database import init_indexes

# Import handlers
from main_bot.handlers.start import start_handler, home_callback
from main_bot.handlers.dashboard import dashboard_callback, add_account_callback
from main_bot.handlers.plans import my_plan_callback
from main_bot.handlers.referral import referral_callback
from main_bot.handlers.redeem import redeem_code_callback, receive_redeem_code, redeem_command, WAITING_CODE
from main_bot.handlers.admin import (
    admin_callback, admin_command, stats_command, broadcast_command,
    admin_stats_callback, admin_broadcast_callback,
    broadcast_target_callback, receive_broadcast_message, gen_code_callback,
    generate_command, admin_users_callback, WAITING_BROADCAST_MESSAGE
)
from main_bot.handlers.help import help_callback, help_command

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def create_application() -> Application:
    """Create and configure the bot application."""
    
    if not MAIN_BOT_TOKEN:
        raise ValueError("MAIN_BOT_TOKEN is not set in environment")
    
    application = Application.builder().token(MAIN_BOT_TOKEN).build()
    
    # ============== Command Handlers ==============
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("redeem", redeem_command))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("generate", generate_command))
    
    # ============== Conversation Handlers ==============
    
    # Redeem code conversation
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
    
    # Broadcast conversation
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
    
    # Navigation
    application.add_handler(CallbackQueryHandler(home_callback, pattern="^home$"))
    application.add_handler(CallbackQueryHandler(dashboard_callback, pattern="^dashboard$"))
    application.add_handler(CallbackQueryHandler(add_account_callback, pattern="^add_account$"))
    application.add_handler(CallbackQueryHandler(help_callback, pattern="^help$"))
    
    # Plans & Referral
    application.add_handler(CallbackQueryHandler(my_plan_callback, pattern="^my_plan$"))
    application.add_handler(CallbackQueryHandler(referral_callback, pattern="^referral$"))
    
    # Admin
    application.add_handler(CallbackQueryHandler(admin_callback, pattern="^admin$"))
    application.add_handler(CallbackQueryHandler(admin_stats_callback, pattern="^admin_stats$"))
    application.add_handler(CallbackQueryHandler(admin_broadcast_callback, pattern="^admin_broadcast$"))
    application.add_handler(CallbackQueryHandler(gen_code_callback, pattern="^gen_code:"))
    application.add_handler(CallbackQueryHandler(admin_users_callback, pattern="^admin_users$"))
    
    return application


async def main():
    """Main entry point."""
    logger.info("Starting Main Bot...")
    
    # Initialize database indexes
    await init_indexes()
    
    # Create and run application
    application = create_application()
    
    # Start polling
    await application.initialize()
    await application.start()
    await application.updater.start_polling(drop_pending_updates=True)
    
    logger.info("Main Bot is running! Press Ctrl+C to stop.")
    
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
