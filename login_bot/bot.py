"""
Login Bot entry point for Group Message Scheduler.
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
    filters,
)
from telegram.error import TimedOut, NetworkError
from telegram.request import HTTPXRequest

from config import LOGIN_BOT_TOKEN
from db.database import init_database

# Import handlers
from login_bot.handlers.start import start_handler, help_callback
from login_bot.handlers.phone import (
    add_account_callback,
    receive_phone_number,
    edit_phone_callback,
    cancel_callback,
    receive_api_id,
    receive_api_hash,
)
from login_bot.handlers.otp import (
    send_otp_callback,
    resend_otp_callback,
    otp_keypad_callback,
)
from login_bot.handlers.twofa import receive_2fa_password

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)

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
    if not LOGIN_BOT_TOKEN:
        raise ValueError("LOGIN_BOT_TOKEN is not set in environment")

    # Build with custom timeouts
    request = HTTPXRequest(
        connect_timeout=CONNECT_TIMEOUT,
        read_timeout=READ_TIMEOUT,
        write_timeout=WRITE_TIMEOUT,
        pool_timeout=POOL_TIMEOUT,
    )

    return (
        Application.builder()
        .token(LOGIN_BOT_TOKEN)
        .request(request)
        .build()
    )

    # ============== Command Handlers ==============
    application.add_handler(CommandHandler("start", start_handler))

    # ============== Callback Query Handlers ==============
    application.add_handler(
        CallbackQueryHandler(add_account_callback, pattern="^add_account$")
    )
    application.add_handler(
        CallbackQueryHandler(edit_phone_callback, pattern="^edit_phone$")
    )
    application.add_handler(
        CallbackQueryHandler(cancel_callback, pattern="^cancel$")
    )

    application.add_handler(
        CallbackQueryHandler(send_otp_callback, pattern="^send_otp$")
    )
    application.add_handler(
        CallbackQueryHandler(resend_otp_callback, pattern="^resend_otp$")
    )
    application.add_handler(
        CallbackQueryHandler(otp_keypad_callback, pattern="^otp:")
    )

    application.add_handler(
        CallbackQueryHandler(help_callback, pattern="^help$")
    )

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

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND, handle_text_message
        )
    )

    return application


async def run_bot():
    """Run the bot with graceful shutdown."""
    logger.info("=" * 50)
    logger.info("Group Message Scheduler - Login Bot V3.1")
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

        logger.info("Login Bot is running!")
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
        logger.info("Login Bot stopped.")


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
