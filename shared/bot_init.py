"""
Centralized Telegram Application initialization logic.
"""

import logging
import signal
import asyncio
from telegram.ext import Application
from telegram.request import HTTPXRequest
from db.database import init_database

# Configure logging
def setup_logging():
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    return logging.getLogger("bot")

def create_base_application(token: str) -> Application:
    """Create and configure the bot application with standard timeouts."""
    if not token:
        raise ValueError("Bot token is not set")

    # Hardened timeouts for stability
    request = HTTPXRequest(
        connect_timeout=30,
        read_timeout=60,
        write_timeout=60,
        pool_timeout=60,
    )

    return (
        Application.builder()
        .token(token)
        .request(request)
        .build()
    )

async def run_bot_gracefully(application: Application, bot_name: str):
    """Run the bot with graceful shutdown support."""
    logger = logging.getLogger(bot_name)
    
    # Initialize database
    await init_database()

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
        
        logger.info(f"{bot_name} is running (Async Polling)...")
        
        # Wait for shutdown signal
        await stop_event.wait()
        
        logger.info(f"{bot_name} is stopping...")
        await application.updater.stop()
        await application.stop()
