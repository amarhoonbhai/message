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
from shared.bot_init import setup_logging, create_base_application, run_bot_gracefully
from shared.decorators import require_premium

# Import handlers
from main_bot.handlers.start import start_handler, home_callback
from main_bot.handlers.dashboard import (
    dashboard_callback,
    add_account_callback,
    toggle_send_mode_callback,
)
from main_bot.handlers.plans import my_plan_callback, buy_plan_callback
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
    admin_nightmode_callback,
    set_nightmode_callback,
    nightmode_command,
    admin_health_callback,
    WAITING_BROADCAST_MESSAGE,
    admin_upgrade_init_callback,
    receive_upgrade_user_id,
    admin_upgrade_perform_callback,
    upgrade_command,
    WAITING_UPGRADE_USER_ID,
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
logger = setup_logging()

def create_application() -> Application:
    """Create and configure the bot application."""
    application = create_base_application(MAIN_BOT_TOKEN)

    # ============== Command Handlers ==============
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("redeem", redeem_command))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CommandHandler("generate", generate_command))
    application.add_handler(CommandHandler("nightmode", nightmode_command))
    application.add_handler(CommandHandler("upgrade", upgrade_command))

    # ============== Conversation Handlers ==============
    redeem_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(redeem_code_callback, pattern="^redeem_code$")],
        states={
            WAITING_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_redeem_code)],
        },
        fallbacks=[
            CallbackQueryHandler(home_callback, pattern="^home$"),
            CallbackQueryHandler(require_premium(dashboard_callback), pattern="^dashboard$"),
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

    upgrade_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_upgrade_init_callback, pattern="^admin_upgrade_init$")],
        states={
            WAITING_UPGRADE_USER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_upgrade_user_id)],
        },
        fallbacks=[
            CallbackQueryHandler(home_callback, pattern="^home$"),
            CallbackQueryHandler(admin_callback, pattern="^admin$"),
        ],
        per_user=True,
        per_chat=True,
    )
    application.add_handler(upgrade_conv)

    # ============== Callback Query Handlers ==============
    # (pattern, callback, needs_premium)
    handlers_config = [
        ("^home$", home_callback, False),
        ("^dashboard$", dashboard_callback, True),
        ("^toggle_send_mode$", toggle_send_mode_callback, True),
        ("^add_account$", add_account_callback, True),
        ("^help$", help_callback, False),
        ("^my_plan$", my_plan_callback, False),
        ("^profile$", profile_callback, True),
        ("^admin$", admin_callback, False),
        ("^admin_stats$", admin_stats_callback, False),
        ("^admin_broadcast$", admin_broadcast_callback, False),
        ("^gen_code:", gen_code_callback, False),
        ("^admin_users$", admin_users_callback, False),
        ("^accounts_list$", accounts_list_callback, True),
        ("^manage_account:", manage_account_callback, True),
        ("^disconnect_account:", disconnect_account_callback, True),
        ("^confirm_disconnect:", confirm_disconnect_callback, True),
        ("^admin_nightmode$", admin_nightmode_callback, False),
        ("^set_nightmode:", set_nightmode_callback, False),
        ("^admin_health$", admin_health_callback, False),
        ("^adm_upgr:", admin_upgrade_perform_callback, False),
        ("^buy_plan:", buy_plan_callback, False),
    ]
    
    for pattern, callback, needs_premium in handlers_config:
        final_callback = require_premium(callback) if needs_premium else callback
        application.add_handler(CallbackQueryHandler(final_callback, pattern=pattern))

    return application

async def main():
    """Start the bot."""
    print("=" * 50)
    print("Group Message Scheduler - Main Bot V3.3")
    print("=" * 50)

    application = create_application()
    await run_bot_gracefully(application, "Main Bot")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
