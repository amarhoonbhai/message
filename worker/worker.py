"""
Worker service entry point for Group Message Scheduler.

Runs continuously and manages sender tasks for all connected users.
"""

import logging
import asyncio
from typing import Dict

from db.database import init_indexes
from db.models import get_all_connected_sessions
from worker.sender import UserSender

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class WorkerManager:
    """Manages all user sender tasks."""
    
    def __init__(self):
        self.senders: Dict[int, UserSender] = {}
        self.tasks: Dict[int, asyncio.Task] = {}
        self.running = False
    
    async def start(self):
        """Start the worker manager."""
        self.running = True
        logger.info("Worker Manager starting...")
        
        # Initialize database indexes
        await init_indexes()
        
        # Main loop - periodically check for new sessions
        while self.running:
            try:
                await self.sync_senders()
                await asyncio.sleep(60)  # Check for changes every minute
                
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
            connected_user_ids = {s["user_id"] for s in sessions}
            
            # Start new senders
            for session in sessions:
                user_id = session["user_id"]
                
                if user_id not in self.senders:
                    logger.info(f"Starting sender for user {user_id}")
                    await self.start_sender(user_id)
            
            # Stop senders for disconnected users
            for user_id in list(self.senders.keys()):
                if user_id not in connected_user_ids:
                    logger.info(f"Stopping sender for user {user_id}")
                    await self.stop_sender(user_id)
            
            logger.debug(f"Active senders: {len(self.senders)}")
            
        except Exception as e:
            logger.error(f"Error syncing senders: {e}")
    
    async def start_sender(self, user_id: int):
        """Start a sender for a user."""
        if user_id in self.senders:
            return
        
        sender = UserSender(user_id)
        self.senders[user_id] = sender
        
        # Create task
        task = asyncio.create_task(sender.start())
        self.tasks[user_id] = task
        
        # Handle task completion
        task.add_done_callback(lambda t: self._on_task_done(user_id, t))
    
    async def stop_sender(self, user_id: int):
        """Stop a sender for a user."""
        if user_id not in self.senders:
            return
        
        sender = self.senders[user_id]
        await sender.stop()
        
        # Cancel task
        if user_id in self.tasks:
            self.tasks[user_id].cancel()
            try:
                await self.tasks[user_id]
            except asyncio.CancelledError:
                pass
            del self.tasks[user_id]
        
        del self.senders[user_id]
    
    def _on_task_done(self, user_id: int, task: asyncio.Task):
        """Handle completed sender tasks."""
        if task.cancelled():
            return
        
        exc = task.exception()
        if exc:
            logger.error(f"Sender task for user {user_id} failed: {exc}")
        
        # Clean up
        if user_id in self.senders:
            del self.senders[user_id]
        if user_id in self.tasks:
            del self.tasks[user_id]
    
    async def stop_all(self):
        """Stop all senders."""
        logger.info("Stopping all senders...")
        
        for user_id in list(self.senders.keys()):
            await self.stop_sender(user_id)
        
        logger.info("All senders stopped")
    
    def stop(self):
        """Signal the manager to stop."""
        self.running = False


async def main():
    """Main entry point."""
    logger.info("=" * 50)
    logger.info("Group Message Scheduler - Worker Service")
    logger.info("=" * 50)
    
    manager = WorkerManager()
    
    try:
        await manager.start()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        manager.stop()
    finally:
        await manager.stop_all()


if __name__ == "__main__":
    asyncio.run(main())
