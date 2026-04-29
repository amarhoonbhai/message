"""
Scheduler Service — the heartbeat of the distributed pipeline.

Runs a tight async loop that:
  1. Polls scheduled_jobs for pending work (every 1-2 seconds)
  2. Atomically transitions jobs pending → queued
  3. Pushes queued jobs into Redis for ARQ workers
  4. Detects dead workers and recovers stuck jobs

Usage:
  python -m services.scheduler.scheduler
"""

import asyncio
import logging
import signal
from datetime import datetime

from core.logger import setup_service_logging
from core.database import init_database, close_connection
from core.redis_client import get_redis_pool, close_redis
from core.queue import enqueue_send_job
from core.config import SCHEDULER_POLL_INTERVAL, DEAD_WORKER_THRESHOLD_SECONDS
from models.job import get_pending_jobs, mark_job_queued, find_dead_workers, reset_stuck_jobs

logger = logging.getLogger(__name__)


class Scheduler:
    """
    Pulls pending jobs from MongoDB and pushes them into the Redis queue.

    Designed to run as a single instance (leader). If you need HA, run
    two instances — the atomic findOneAndUpdate ensures no double-queueing.
    """

    def __init__(self):
        self.running = False
        self._shutdown_event = asyncio.Event()
        self._cycle_count = 0

    async def start(self):
        """Initialize connections and enter the main loop."""
        setup_service_logging("scheduler")
        logger.info("=" * 50)
        logger.info("Scheduler Service Starting")
        logger.info("=" * 50)

        self.running = True

        # Initialize DB + indexes
        await init_database()

        # Get Redis pool
        redis = await get_redis_pool()
        logger.info(f"Connected to Redis — poll interval: {SCHEDULER_POLL_INTERVAL}s")

        # Signal handlers
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, lambda: self.stop())
            except NotImplementedError:
                pass

        try:
            while self.running:
                self._cycle_count += 1

                # ── 1. Poll pending jobs ────────────────────────────────
                try:
                    jobs = await get_pending_jobs(limit=200)

                    if jobs:
                        queued_count = 0
                        for job in jobs:
                            job_id = job["job_id"]

                            # Atomic pending → queued
                            ok = await mark_job_queued(job_id)
                            if ok:
                                await enqueue_send_job(redis, job_id)
                                queued_count += 1

                        if queued_count > 0:
                            logger.info(f"📤 Queued {queued_count} jobs → Redis")

                except Exception as e:
                    logger.error(f"Error in poll cycle: {e}")

                # ── 2. Plan Expiry Reminders (Level Up) ──────────────
                # Runs every 6 hours (approx 21600 seconds)
                if self._cycle_count % 3600 == 0:  # Assuming 1s poll
                    try:
                        await self._process_plan_reminders()
                    except Exception as e:
                        logger.error(f"Expiry reminder error: {e}")

                # ── 3. Dead worker recovery ────────────────────────────
                if self._cycle_count % 30 == 0:
                    try:
                        dead = await find_dead_workers(DEAD_WORKER_THRESHOLD_SECONDS)
                        if dead:
                            dead_ids = [w["worker_id"] for w in dead]
                            recovered = await reset_stuck_jobs(dead_ids)
                            if recovered:
                                logger.warning(
                                    f"🔧 Recovered {recovered} stuck jobs "
                                    f"from {len(dead_ids)} dead workers"
                                )
                    except Exception as e:
                        logger.error(f"Dead worker recovery error: {e}")

                # ── 4. Sleep (interruptible) ────────────────────────────
                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(),
                        timeout=SCHEDULER_POLL_INTERVAL,
                    )
                    break  # Shutdown signal received
                except asyncio.TimeoutError:
                    continue

        except asyncio.CancelledError:
            pass
        finally:
            await self.cleanup()

    async def _process_plan_reminders(self):
        """Analyze plans and send notifications for expiring/expired users."""
        from models.plan import get_expiring_plans, get_plans_needing_expiry_reminder, update_plan_notification
        from telegram import Bot
        from core.config import MAIN_BOT_TOKEN
        
        async with Bot(MAIN_BOT_TOKEN) as bot:
            now = datetime.utcnow()
            
            # 1. Expiring Soon (Warning)
            expiring = await get_expiring_plans()
            for p in expiring:
                uid = p["user_id"]
                expires = p["expires_at"]
                hours = int((expires - now).total_seconds() // 3600)
                
                msg = (
                    "⚠️ *SUBSCRIPTION EXPIRING SOON*\n\n"
                    f"Your premium plan expires in **{hours} hours**.\n"
                    "To ensure uninterrupted messaging, please renew your plan now!"
                )
                try:
                    await bot.send_message(uid, msg, parse_mode="Markdown")
                    await update_plan_notification(uid, {"expiration_warnings_sent": p.get("expiration_warnings_sent", 0) + 1})
                except Exception: pass

            # 2. Just Expired
            expired = await get_plans_needing_expiry_reminder()
            for p in expired:
                uid = p["user_id"]
                msg = (
                    "🔴 *SUBSCRIPTION EXPIRED*\n\n"
                    "Your premium plan has ended. Your workers have been paused.\n"
                    "Renew now to resume your automated advertising campaign!"
                )
                try:
                    await bot.send_message(uid, msg, parse_mode="Markdown")
                    await update_plan_notification(uid, {
                        "notified_expired": True,
                        "last_expiry_notification_at": now
                    })
                except Exception: pass

    def stop(self):
        """Signal the scheduler to shut down."""
        if not self.running:
            return
        logger.info("Shutdown signal received")
        self.running = False
        self._shutdown_event.set()

    async def cleanup(self):
        """Graceful cleanup of connections."""
        logger.info("Cleaning up...")
        await close_redis()
        await close_connection()
        logger.info("Scheduler stopped")


async def main():
    """Entry point for the scheduler service."""
    scheduler = Scheduler()
    await scheduler.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
