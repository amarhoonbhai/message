"""
Per-user sender logic for the Worker service.
"""

import logging
import asyncio
from datetime import datetime
from typing import Optional

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import (
    FloodWaitError,
    PeerFloodError,
    ChatWriteForbiddenError,
    ChannelPrivateError,
    ChatAdminRequiredError,
    UserBannedInChannelError,
    InputUserDeactivatedError,
)
from telethon.tl.types import InputPeerSelf

from config import (
    API_ID, API_HASH,
    GROUP_GAP_SECONDS, MESSAGE_GAP_SECONDS, MIN_INTERVAL_MINUTES
)
from db.models import (
    get_session, get_plan, get_user_config, get_user_groups,
    update_last_saved_id, remove_group, log_send, is_plan_active
)
from worker.utils import is_night_mode, seconds_until_morning, format_time_remaining

logger = logging.getLogger(__name__)


class UserSender:
    """Handles message sending for a single user."""
    
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.client: Optional[TelegramClient] = None
        self.running = False
    
    async def start(self):
        """Start the sender loop."""
        self.running = True
        
        logger.info(f"[User {self.user_id}] Starting sender...")
        
        # Load session
        session_data = await get_session(self.user_id)
        
        if not session_data or not session_data.get("connected"):
            logger.warning(f"[User {self.user_id}] No connected session found")
            return
        
        session_string = session_data.get("session_string")
        
        if not session_string:
            logger.warning(f"[User {self.user_id}] No session string found")
            return
        
        # Create client
        self.client = TelegramClient(
            StringSession(session_string),
            API_ID,
            API_HASH,
            device_model="Group Message Scheduler Worker",
            system_version="1.0",
            app_version="1.0"
        )
        
        try:
            await self.client.connect()
            
            if not await self.client.is_user_authorized():
                logger.warning(f"[User {self.user_id}] Session not authorized")
                return
            
            # Run the main loop
            await self.run_loop()
            
        except Exception as e:
            logger.error(f"[User {self.user_id}] Error: {e}")
        finally:
            if self.client:
                await self.client.disconnect()
    
    async def stop(self):
        """Stop the sender."""
        self.running = False
        if self.client:
            await self.client.disconnect()
    
    async def run_loop(self):
        """Main sender loop."""
        while self.running:
            try:
                # 1. Check plan validity
                if not await is_plan_active(self.user_id):
                    logger.info(f"[User {self.user_id}] Plan expired or inactive, skipping...")
                    await asyncio.sleep(300)  # Check again in 5 minutes
                    continue
                
                # 2. Check night mode
                if is_night_mode():
                    wait_seconds = seconds_until_morning()
                    logger.info(f"[User {self.user_id}] Night mode active, sleeping for {format_time_remaining(wait_seconds)}")
                    await asyncio.sleep(min(wait_seconds, 3600))  # Max 1 hour, then recheck
                    continue
                
                # 3. Get user config
                config = await get_user_config(self.user_id)
                interval_min = max(config.get("interval_min", MIN_INTERVAL_MINUTES), MIN_INTERVAL_MINUTES)
                last_saved_id = config.get("last_saved_id", 0)
                
                # 4. Get user's groups
                groups = await get_user_groups(self.user_id, enabled_only=True)
                
                if not groups:
                    logger.info(f"[User {self.user_id}] No enabled groups, skipping...")
                    await asyncio.sleep(interval_min * 60)
                    continue
                
                # 5. Fetch NEW Saved Messages
                new_messages = await self.get_new_saved_messages(last_saved_id)
                
                if not new_messages:
                    logger.debug(f"[User {self.user_id}] No new messages")
                    await asyncio.sleep(interval_min * 60)
                    continue
                
                logger.info(f"[User {self.user_id}] Found {len(new_messages)} new message(s) to forward")
                
                # 6. Forward messages to groups
                for msg in new_messages:
                    await self.forward_message_to_groups(msg, groups)
                    
                    # Update last_saved_id after each message
                    if msg.id > last_saved_id:
                        last_saved_id = msg.id
                        await update_last_saved_id(self.user_id, last_saved_id)
                    
                    # Wait between messages
                    if msg != new_messages[-1]:
                        logger.debug(f"[User {self.user_id}] Waiting {MESSAGE_GAP_SECONDS}s before next message")
                        await asyncio.sleep(MESSAGE_GAP_SECONDS)
                
                # 7. Sleep for interval
                logger.info(f"[User {self.user_id}] Cycle complete, sleeping for {interval_min} minutes")
                await asyncio.sleep(interval_min * 60)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[User {self.user_id}] Loop error: {e}")
                await asyncio.sleep(60)  # Wait before retrying
    
    async def get_new_saved_messages(self, last_saved_id: int) -> list:
        """Fetch new Saved Messages after the given ID."""
        try:
            # Get Saved Messages (messages to self)
            messages = []
            
            async for msg in self.client.iter_messages(
                InputPeerSelf(),
                limit=50,
                min_id=last_saved_id
            ):
                messages.append(msg)
            
            # Reverse to process oldest first
            messages.reverse()
            
            return messages
            
        except Exception as e:
            logger.error(f"[User {self.user_id}] Error fetching saved messages: {e}")
            return []
    
    async def forward_message_to_groups(self, message, groups: list):
        """Forward a message to all enabled groups."""
        for i, group in enumerate(groups):
            chat_id = group.get("chat_id")
            chat_title = group.get("chat_title", "Unknown")
            
            try:
                # Forward the message
                await self.client.forward_messages(
                    entity=chat_id,
                    messages=message.id,
                    from_peer=InputPeerSelf()
                )
                
                logger.info(f"[User {self.user_id}] Forwarded message {message.id} to {chat_title}")
                
                # Log success
                await log_send(
                    user_id=self.user_id,
                    chat_id=chat_id,
                    saved_msg_id=message.id,
                    status="success"
                )
                
            except FloodWaitError as e:
                logger.warning(f"[User {self.user_id}] FloodWait: sleeping {e.seconds}s")
                await asyncio.sleep(e.seconds + 5)
                
                # Retry once after waiting
                try:
                    await self.client.forward_messages(
                        entity=chat_id,
                        messages=message.id,
                        from_peer=InputPeerSelf()
                    )
                    await log_send(self.user_id, chat_id, message.id, "success")
                except Exception as retry_e:
                    await log_send(self.user_id, chat_id, message.id, "failed", str(retry_e))
                
            except PeerFloodError:
                logger.error(f"[User {self.user_id}] PeerFlood error - pausing for 1 hour")
                await log_send(self.user_id, chat_id, message.id, "failed", "PeerFlood")
                await asyncio.sleep(3600)  # Pause for 1 hour
                return  # Exit this forwarding cycle
                
            except (ChatWriteForbiddenError, ChannelPrivateError, 
                    ChatAdminRequiredError, UserBannedInChannelError) as e:
                # Remove group - access revoked
                logger.warning(f"[User {self.user_id}] Removing group {chat_title}: {type(e).__name__}")
                await remove_group(self.user_id, chat_id)
                await log_send(self.user_id, chat_id, message.id, "removed", str(e))
                continue  # Skip to next group
                
            except InputUserDeactivatedError:
                logger.error(f"[User {self.user_id}] User account deactivated!")
                await log_send(self.user_id, chat_id, message.id, "failed", "UserDeactivated")
                return
                
            except Exception as e:
                logger.error(f"[User {self.user_id}] Error forwarding to {chat_title}: {e}")
                await log_send(self.user_id, chat_id, message.id, "failed", str(e))
            
            # Wait between groups (except for last one)
            if i < len(groups) - 1:
                logger.debug(f"[User {self.user_id}] Waiting {GROUP_GAP_SECONDS}s before next group")
                await asyncio.sleep(GROUP_GAP_SECONDS)
