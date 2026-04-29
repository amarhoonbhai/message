"""
Worker service entry point for Group Message Scheduler.

Runs continuously and manages sender tasks for all connected users.
"""

import logging
import asyncio
from typing import Dict
import signal
import random
from datetime import datetime, timedelta

from db.database import init_database
from db.models import get_all_connected_sessions
from worker.sender import UserSender

# ── Logging configuration ──────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Silence noisy third-party loggers — keeps logs clean in production
logging.getLogger("telethon").setLevel(logging.ERROR)
logging.getLogger("telethon.network").setLevel(logging.ERROR)
logging.getLogger("telethon.crypto").setLevel(logging.ERROR)
logging.getLogger("telethon.extensions").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)

class WorkerManager:
    """Manages all account sender tasks with graceful shutdown support."""
    
    MAX_RESTART_ATTEMPTS = 3
    # Max simultaneous Telethon connections — prevents CPU/RAM spikes on large pools
    MAX_CONCURRENT_CONNECTIONS = 50
    # How long to wait before retrying a recently-failed session (circuit breaker)
    AUTH_FAIL_COOLDOWN_HOURS = 6

    def __init__(self):
        # Keys are (user_id, phone) tuples
        self.senders: Dict[tuple, UserSender] = {}
        self.tasks: Dict[tuple, asyncio.Task] = {}
        self.restart_counts: Dict[tuple, int] = {}  # Track restart attempts
        self.running = False
        self._shutdown_event = asyncio.Event()
        # Semaphore caps simultaneous Telethon connects to avoid network/RAM spikes
        self._connection_semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_CONNECTIONS)
    
    async def start(self):
        """Start the worker manager."""
        self.running = True
        logger.info("Worker Manager starting...")
        
        # Initialize database and indexes
        await init_database()
        
        # Setup signal handlers for graceful shutdown
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, lambda: self.stop())
            except NotImplementedError:
                pass
        
        # Main loop - periodically check for new sessions
        while self.running:
            try:
                await self.sync_senders()
                
                # Sleep in a way that respects shutdown signal immediately
                try:
                    await asyncio.wait_for(self._shutdown_event.wait(), timeout=60)
                    break 
                except asyncio.TimeoutError:
                    continue 
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker Manager error: {e}")
                await asyncio.sleep(30)
        
        # Stop all senders
        await self.stop_all()
    
    async def sync_senders(self):
        """Sync sender tasks with connected sessions in database."""
        try:
            sessions = await get_all_connected_sessions()
            active_keys = {(s["user_id"], s["phone"]) for s in sessions}
            
            started_count = 0
            skipped_disabled = 0
            skipped_cooldown = 0

            for session in sessions:
                user_id = session["user_id"]
                phone = session["phone"]
                key = (user_id, phone)

                # ── Skip 1: Permanently disabled sessions ─────────────────
                if session.get("worker_disabled"):
                    skipped_disabled += 1
                    continue

                # ── Skip 2: Circuit breaker — failed recently ──────────────
                last_fail = session.get("last_auth_fail")
                if last_fail and isinstance(last_fail, datetime):
                    cooldown = timedelta(hours=self.AUTH_FAIL_COOLDOWN_HOURS)
                    if datetime.utcnow() - last_fail < cooldown:
                        remaining = cooldown - (datetime.utcnow() - last_fail)
                        remaining_h = int(remaining.total_seconds() // 3600)
                        logger.debug(
                            f"Skipping {phone} — auth cooldown ({remaining_h}h remaining)"
                        )
                        skipped_cooldown += 1
                        continue

                if key not in self.senders:
                    await self.start_sender(user_id, phone)
                    started_count += 1
            
            stopped_count = 0
            for key in list(self.senders.keys()):
                if key not in active_keys:
                    logger.info(f"Session disconnected: {key[1]} (User {key[0]})")
                    await self.stop_sender(key)
                    stopped_count += 1
            
            # V6: Reset restart counters for senders that have been running 5+ min
            for key in list(self.restart_counts.keys()):
                if key in self.senders:
                    sender = self.senders[key]
                    if sender.error_streak == 0 and sender._last_cycle_duration is not None:
                        self.restart_counts.pop(key, None)
            
            if started_count > 0 or stopped_count > 0 or skipped_disabled > 0:
                logger.info(
                    f"Sync: +{started_count} started | -{stopped_count} stopped "
                    f"| {skipped_disabled} disabled | {skipped_cooldown} in cooldown"
                )
            
        except Exception as e:
            logger.error(f"Error syncing senders: {e}")
    
    async def start_sender(self, user_id: int, phone: str):
        """Start a sender for a specific account with a random burst stagger delay."""
        key = (user_id, phone)
        if key in self.senders:
            return
        
        # Smart burst staggering: 1-15s delay to prevent simultaneous starts
        delay = random.uniform(1, 15)
        logger.info(f"Staggering start for {phone} (User {user_id}) by {delay:.1f}s...")
        
        # Pass semaphore so all senders share the same concurrency cap
        sender = UserSender(user_id, phone, semaphore=self._connection_semaphore)
        self.senders[key] = sender
        
        async def delayed_start():
            await asyncio.sleep(delay)
            await sender.start()

        task = asyncio.create_task(delayed_start())
        self.tasks[key] = task
        task.add_done_callback(lambda t: self._on_task_done(key, t))
    
    async def stop_sender(self, key: tuple):
        """Stop a sender for a specific account key."""
        if key not in self.senders:
            return
        
        sender = self.senders[key]
        await sender.stop()
        
        if key in self.tasks:
            self.tasks[key].cancel()
            try:
                await self.tasks[key]
            except (asyncio.CancelledError, Exception):
                pass
            del self.tasks[key]
        
        del self.senders[key]
    
    def _on_task_done(self, key: tuple, task: asyncio.Task):
        """Handle completed sender tasks — auto-restart on crash."""
        if task.cancelled():
            return
        
        try:
            exc = task.exception()
            if exc:
                logger.error(f"Account {key[1]} [User {key[0]}] crashed: {exc}")
                
                if self.running:
                    attempts = self.restart_counts.get(key, 0)
                    if attempts < self.MAX_RESTART_ATTEMPTS:
                        delay = 30 * (2 ** attempts)
                        self.restart_counts[key] = attempts + 1
                        logger.info(f"Scheduling restart #{attempts + 1} for {key[1]} in {delay}s...")
                        # V6: Fixed — replaced deprecated call_later with create_task
                        asyncio.create_task(self._restart_sender_with_delay(key, delay))
                    else:
                        logger.error(f"Account {key[1]} [User {key[0]}] exceeded max restarts ({self.MAX_RESTART_ATTEMPTS})")
        except asyncio.CancelledError:
            pass
        
        if key in self.senders:
            del self.senders[key]
        if key in self.tasks:
            del self.tasks[key]
    
    async def _restart_sender_with_delay(self, key: tuple, delay: int):
        """V6: Wait then restart — replaces deprecated call_later."""
        await asyncio.sleep(delay)
        await self._restart_sender(key)

    async def _restart_sender(self, key: tuple):
        """Restart a crashed sender after backoff delay."""
        if not self.running:
            return
        user_id, phone = key
        logger.info(f"Restarting sender for {phone} [User {user_id}]...")
        await self.start_sender(user_id, phone)
    
    async def stop_all(self):
        """Stop all senders."""
        if not self.senders:
            return
            
        logger.info(f"Stopping {len(self.senders)} active sender tasks...")
        stop_tasks = [self.stop_sender(key) for key in list(self.senders.keys())]
        if stop_tasks:
            await asyncio.gather(*stop_tasks, return_exceptions=True)
        logger.info("All senders stopped")
    
    def stop(self):
        """Signal the manager to stop."""
        if not self.running:
            return
        logger.info("Shutdown signal received...")
        self.running = False
        self._shutdown_event.set()

async def run_worker():
    """Run the worker manager."""
    logger.info("=" * 50)
    logger.info("Kurup Ads V6 Elite — Worker Service")
    logger.info("=" * 50)
    
    manager = WorkerManager()
    try:
        await manager.start()
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Worker interrupted...")
    finally:
        await manager.stop_all()

async def main():
    """Auto-restart wrapper."""
    
    # SYSTEM FIX: Increase file descriptor soft limits to prevent Errno 24
    try:
        import resource
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        # Increase the limit to max allowed or at least 65535 to handle many sockets
        target = hard if (hard > 65535 and hard != -1) else 65535
        if hard == -1: target = 65535
        # Ensure we don't attempt to set more than hard limit (if bounded)
        target = min(target, hard) if hard != -1 else target
        
        resource.setrlimit(resource.RLIMIT_NOFILE, (target, hard))
        logger.info(f"File descriptor limit optimized from {soft} to {target}")
    except Exception as e:
        logger.warning(f"OS Resource config skipped (Non-Linux or insufficient privileges): {e}")

    # START PLAN NOTIFIER BACKGROUND TASK
    try:
        from worker.notifier import PlanNotifier
        notifier = PlanNotifier()
        asyncio.create_task(notifier.start())
    except Exception as notify_err:
        logger.error(f"Could not start PlanNotifier: {notify_err}")

    restart_delay = 5
    max_delay = 60
    while True:
        try:
            await run_worker()
            break 
        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f"Worker crashed: {e}. Restarting in {restart_delay}s...")
            await asyncio.sleep(restart_delay)
            restart_delay = min(restart_delay * 2, max_delay)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
