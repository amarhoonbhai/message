"""
Main Bot entry point for Group Message Scheduler.
Includes timeout hardening, network readiness check, and auto-restart.
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
from telegram.error import TimedOut, NetworkError
from telegram.request import HTTPXRequest

from config import MAIN_BOT_TOKEN
from db.database import init_database

# Import handlers
from main_bot.handlers.start import start_handler, home_callback
from main_bot.handlers.dashboard import (
    dashboard_callback,
    add_account_callback,
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

# ============== Timeout Configuration ==============
CONNECT_TIMEOUT = 30
READ_TIMEOUT = 60
WRITE_TIMEOUT = 60
POOL_TIMEOUT = 60


async def wait_for_network():
    """Wait until Telegram API is reachable before starting."""
    import httpx

    url = "https://api.telegram.org"
    attempt = 0
    while True:
        attempt += 1
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                resp = await client.get(url, timeout=10)
                if resp.status_code in (200, 301, 302, 404):
                    logger.info("Network is ready (Telegram API reachable).")
                    return
        except Exception as e:
            logger.warning(
                f"Network not ready (attempt {attempt}): {e}. "
                "Retrying in 5s..."
            )
            await asyncio.sleep(5)


def create_application() -> Application:
    """Create and configure the bot application with hardened timeouts."""
    if not MAIN_BOT_TOKEN:
        raise ValueError("MAIN_BOT_TOKEN is not set in environment")

    # Build with custom timeouts
    request = HTTPXRequest(
        connect_timeout=CONNECT_TIMEOUT,
        read_timeout=READ_TIMEOUT,
        write_timeout=WRITE_TIMEOUT,
        pool_timeout=POOL_TIMEOUT,
    )

    application = (
        Application.builder()
        .token(MAIN_BOT_TOKEN)
        .request(request)
        .connect_timeout(CONNECT_TIMEOUT)
        .read_timeout(READ_TIMEOUT)
        .write_timeout(WRITE_TIMEOUT)
        .pool_timeout(POOL_TIMEOUT)
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

    # ============== Conversation Handlers ==============
    redeem_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(
                redeem_code_callback, pattern="^redeem_code$"
            )
        ],
        states={
            WAITING_CODE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, receive_redeem_code
                )
            ],
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
        entry_points=[
            CallbackQueryHandler(
                broadcast_target_callback, pattern="^broadcast:"
            )
        ],
        states={
            WAITING_BROADCAST_MESSAGE: [
                MessageHandler(
                    filters.TEXT | filters.PHOTO | filters.Document.ALL,
                    receive_broadcast_message,
                )
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
    application.add_handler(
        CallbackQueryHandler(home_callback, pattern="^home$")
    )
    application.add_handler(
        CallbackQueryHandler(dashboard_callback, pattern="^dashboard$")
    )
    application.add_handler(
        CallbackQueryHandler(add_account_callback, pattern="^add_account$")
    )
    application.add_handler(
        CallbackQueryHandler(help_callback, pattern="^help$")
    )

    application.add_handler(
        CallbackQueryHandler(my_plan_callback, pattern="^my_plan$")
    )
    application.add_handler(
        CallbackQueryHandler(referral_callback, pattern="^referral$")
    )
    application.add_handler(
        CallbackQueryHandler(profile_callback, pattern="^profile$")
    )

    application.add_handler(
        CallbackQueryHandler(admin_callback, pattern="^admin$")
    )
    application.add_handler(
        CallbackQueryHandler(admin_stats_callback, pattern="^admin_stats$")
    )
    application.add_handler(
        CallbackQueryHandler(
            admin_broadcast_callback, pattern="^admin_broadcast$"
        )
    )
    application.add_handler(
        CallbackQueryHandler(gen_code_callback, pattern="^gen_code:")
    )
    application.add_handler(
        CallbackQueryHandler(admin_users_callback, pattern="^admin_users$")
    )

    application.add_handler(
        CallbackQueryHandler(
            accounts_list_callback, pattern="^accounts_list$"
        )
    )
    application.add_handler(
        CallbackQueryHandler(
            manage_account_callback, pattern="^manage_account:"
        )
    )
    application.add_handler(
        CallbackQueryHandler(
            disconnect_account_callback, pattern="^disconnect_account:"
        )
    )
    application.add_handler(
        CallbackQueryHandler(
            confirm_disconnect_callback, pattern="^confirm_disconnect:"
        )
    )

    return application


async def run_bot():
    """Run the bot with graceful shutdown."""
    logger.info("=" * 50)
    logger.info("Group Message Scheduler - Main Bot V3.1")
    logger.info("=" * 50)

    # Wait for network
    await wait_for_network()

    # Initialize database
    await init_database()

    # Create application
    application = create_application()

    # Setup shutdown event
    stop_event = asyncio.Event()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: stop_event.set())
        except NotImplementedError:
            pass

    try:
        await application.initialize()
        await application.start()
        await application.updater.start_polling(
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query"],
        )

        logger.info("Main Bot is running!")
        await stop_event.wait()

    except (asyncio.CancelledError, KeyboardInterrupt):
        logger.info("Shutdown signal received...")
    finally:
        logger.info("Cleaning up...")
        try:
            if application.updater and application.updater.running:
                await application.updater.stop()
            if application.running:
                await application.stop()
            await application.shutdown()
        except Exception as e:
            logger.error(f"Cleanup error (ignored): {e}")
        logger.info("Main Bot stopped.")


async def main():
    """Auto-restart wrapper: keeps the bot alive on crashes."""
    restart_delay = 5
    max_delay = 60

    while True:
        try:
            await run_bot()
            break  # Clean exit (signal received)
        except KeyboardInterrupt:
            break
        except (TimedOut, NetworkError) as e:
            logger.error(
                f"Bot crashed (network): {e}. "
                f"Restarting in {restart_delay}s..."
            )
            await asyncio.sleep(restart_delay)
            restart_delay = min(restart_delay * 2, max_delay)
        except Exception as e:
            logger.error(
                f"Bot crashed (unexpected): {e}. "
                f"Restarting in {restart_delay}s..."
            )
            await asyncio.sleep(restart_delay)
            restart_delay = min(restart_delay * 2, max_delay)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
