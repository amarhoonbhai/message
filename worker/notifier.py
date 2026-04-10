"""
Background task for sending plan expiration notifications securely
using the main bot token.
"""

import sys
import logging
import asyncio
from datetime import datetime, timedelta

from telegram import Bot
from telegram.error import TelegramError

from config import MAIN_BOT_TOKEN
from models.plan import get_expiring_plans, get_newly_expired_plans, update_plan_notification

logger = logging.getLogger(__name__)

# Fallback print if logger isn't visible
def log_info(msg):
    logger.info(msg)
    print(f"[Notifier] {msg}", flush=True)

class PlanNotifier:
    def __init__(self):
        self.bot = Bot(token=MAIN_BOT_TOKEN)
        self.running = False

    async def start(self):
        """Starts the periodic background notifier."""
        self.running = True
        log_info("Started plan expiration notifier task.")
        
        while self.running:
            try:
                await self.check_expirations()
            except Exception as e:
                logger.error(f"Error in plan notifier loop: {e}")
            
            # Check every 1 hour
            await asyncio.sleep(3600)

    async def stop(self):
        """Stops the background notifier."""
        self.running = False

    async def check_expirations(self):
        now = datetime.utcnow()
        
        # 1. Process active plans that are expiring soon
        expiring_plans = await get_expiring_plans()
        for plan in expiring_plans:
            user_id = plan["user_id"]
            expires_at = plan.get("expires_at")
            warnings_sent = plan.get("expiration_warnings_sent", 0)
            
            if not expires_at:
                continue
                
            time_left = expires_at - now
            hours_left = time_left.total_seconds() / 3600.0

            should_notify = False
            new_warning_level = warnings_sent
            
            # Warning 1: at < 24h
            if hours_left <= 24 and warnings_sent == 0:
                should_notify = True
                new_warning_level = 1
            # Warning 2: at < 16h
            elif hours_left <= 16 and warnings_sent == 1:
                should_notify = True
                new_warning_level = 2
            # Warning 3: at < 8h
            elif hours_left <= 8 and warnings_sent == 2:
                should_notify = True
                new_warning_level = 3

            if should_notify:
                message = (
                    f"⚠️ <b>Plan Expiring Soon</b>\n\n"
                    f"Your Spinify premium plan will expire in <b>{int(hours_left)} hours</b>.\n"
                    f"Please renew your plan to ensure your automated campaigns continue running smoothly without interruption."
                )
                success = await self.send_message(user_id, message)
                if success:
                    await update_plan_notification(user_id, {"expiration_warnings_sent": new_warning_level})

        # 2. Process newly expired plans
        newly_expired = await get_newly_expired_plans()
        for plan in newly_expired:
            user_id = plan["user_id"]
            
            message = (
                f"🛑 <b>Plan Expired</b>\n\n"
                f"Your Spinify premium plan has officially expired! Your scheduled campaigns have been paused.\n"
                f"Please purchase a new plan from the dashboard to continue using the service."
            )
            success = await self.send_message(user_id, message)
            if success:
                # Set so we don't spam them again
                await update_plan_notification(user_id, {"notified_expired": True, "status": "expired"})

    async def send_message(self, user_id: int, text: str) -> bool:
        """Sends a message via the bot, returns True on success."""
        try:
            await self.bot.send_message(chat_id=user_id, text=text, parse_mode="HTML")
            return True
        except TelegramError as e:
            logger.warning(f"Could not send notification to user {user_id}: {e}")
            if "bot was blocked" in str(e).lower() or "not found" in str(e).lower():
                # Don't try again if blocked
                return True 
            return False
        except Exception as e:
            logger.error(f"Unexpected error notifying user {user_id}: {e}")
            return False
