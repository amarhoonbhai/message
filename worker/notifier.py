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
from models.plan import get_expiring_plans, get_plans_needing_expiry_reminder, update_plan_notification

logger = logging.getLogger(__name__)

# Fallback print if logger isn't visible
def log_info(msg):
    logger.info(msg)
    print(f"[Notifier] {msg}", flush=True)

class PlanNotifier:
    def __init__(self):
        self.running = False
        self._last_cleanup_date = None

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

    async def clean_database_logs(self):
        """Automatically clean up logs and records older than 15 days to keep MongoDB fast."""
        try:
            from db.database import get_database
            from datetime import datetime, timedelta
            from worker.utils import send_central_log
            
            db = get_database()
            now = datetime.utcnow()
            
            # 1. Clean old send logs (older than 15 days)
            logs_cutoff = now - timedelta(days=15)
            log_result = await db.send_logs.delete_many({"sent_at": {"$lt": logs_cutoff}})
            
            # 2. Clean used redeem codes (older than 30 days)
            codes_cutoff = now - timedelta(days=30)
            code_result = await db.redeem_codes.delete_many({
                "used": True,
                "used_at": {"$lt": codes_cutoff}
            })
            
            total_deleted = log_result.deleted_count + code_result.deleted_count
            if total_deleted > 0:
                log_info(f"Database Auto-Cleanup: Removed {log_result.deleted_count} logs and {code_result.deleted_count} codes.")
                
                # Send premium styled log to central logs channel
                msg = (
                    f"<b>🧹 DATABASE AUTO-CLEANUP</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🗑 <b>Removed Send Logs:</b> <code>{log_result.deleted_count}</code>\n"
                    f"🎟 <b>Removed Promo Codes:</b> <code>{code_result.deleted_count}</code>\n"
                    f"⚡ <b>Status:</b> Database optimized and clean!"
                )
                await send_central_log(msg)
                
        except Exception as e:
            logger.error(f"Error during database auto-cleanup: {e}")

    async def check_expirations(self):
        now = datetime.utcnow()
        
        # 0. Clean database logs once a day
        today = now.date()
        if self._last_cleanup_date != today:
            await self.clean_database_logs()
            self._last_cleanup_date = today
        
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
                if plan.get("plan_type") == "free_trial":
                    message = (
                        f"⚠️ <b>Trial Expiring Soon</b>\n\n"
                        f"Your 2-day free trial will expire in <b>{int(hours_left)} hours</b>.\n"
                        f"If you want to continue, contact @spinify to buy the access."
                    )
                else:
                    message = (
                        f"⚠️ <b>Plan Expiring Soon</b>\n\n"
                        f"Your Spinify premium plan will expire in <b>{int(hours_left)} hours</b>.\n"
                        f"Please renew your plan to ensure your automated campaigns continue running smoothly without interruption."
                    )
                success = await self.send_message(user_id, message)
                if success:
                    await update_plan_notification(user_id, {"expiration_warnings_sent": new_warning_level})

        # 2. Process expired plans (recurring reminders)
        plans_needing_reminders = await get_plans_needing_expiry_reminder()
        for plan in plans_needing_reminders:
            user_id = plan["user_id"]
            is_reminder = plan.get("notified_expired", False)
            expires_at = plan.get("expires_at", now)
            
            # Formatting for expiry date
            expiry_str = expires_at.strftime("%Y-%m-%d %H:%M UTC")
            
            if plan.get("plan_type") == "free_trial":
                if is_reminder:
                    title = "⏰ <b>TRIAL RENEWAL REMINDER</b>"
                    body = "Your 2-day free trial remains expired. If you want to continue, contact @spinify to buy the access."
                else:
                    title = "🛑 <b>TRIAL EXPIRED</b>"
                    body = "Your 2-day free trial has expired! If you want to continue, contact @spinify to buy the access."
                
                message = (
                    f"{title}\n\n"
                    f"{body}"
                )
            else:
                if is_reminder:
                    title = "⏰ <b>RENEWAL REMINDER</b>"
                    body = f"Your Spinify premium plan remains expired (since {expiry_str}). Your campaigns are currently paused."
                else:
                    title = "🛑 <b>PLAN EXPIRED</b>"
                    body = f"Your Spinify premium plan has officially expired as of {expiry_str}! Your scheduled campaigns have been paused."

                message = (
                    f"{title}\n\n"
                    f"{body}\n\n"
                    f"Please purchase a new plan from the dashboard to resume your automated service immediately."
                )
            
            success = await self.send_message(user_id, message)
            if success:
                # Update status and set last notification time to throttle the next one for 24h
                await update_plan_notification(user_id, {
                    "notified_expired": True, 
                    "status": "expired",
                    "last_expiry_notification_at": datetime.utcnow()
                })
                # Wipe sessions, groups and config to remove expired user from the bot
                db = get_database()
                await db.sessions.delete_many({"user_id": user_id})
                await db.groups.delete_many({"user_id": user_id})
                await db.config.delete_many({"user_id": user_id})

    async def send_message(self, user_id: int, text: str) -> bool:
        """Sends a message via the bot, returns True on success."""
        try:
            async with Bot(token=MAIN_BOT_TOKEN) as bot:
                await bot.send_message(chat_id=user_id, text=text, parse_mode="HTML")
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
