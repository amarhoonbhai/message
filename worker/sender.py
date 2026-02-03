"""
Per-user sender logic for the Worker service.
Uses per-user API credentials stored in session.
"""

import logging
import asyncio
from datetime import datetime
from typing import Optional

from telethon import TelegramClient, events
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
from telethon.tl.types import InputPeerSelf, InputUserSelf
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.account import UpdateProfileRequest

from config import GROUP_GAP_SECONDS, MESSAGE_GAP_SECONDS, MIN_INTERVAL_MINUTES, TRIAL_BIO_TEXT, BIO_CHECK_INTERVAL
from db.models import (
    get_session, get_plan, get_user_config, get_user_groups,
    update_last_saved_id, update_current_msg_index, remove_group, log_send, is_plan_active, is_trial_user
)
from worker.utils import is_night_mode, seconds_until_morning, format_time_remaining
from worker.commands import process_command  # Used by event handler

logger = logging.getLogger(__name__)


class UserSender:
    """Handles message sending for a single user using their own API credentials."""
    
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.client: Optional[TelegramClient] = None
        self.running = False
        self.wake_up_event = asyncio.Event()
    
    async def start(self):
        """Start the sender loop."""
        self.running = True
        
        logger.info(f"[User {self.user_id}] Starting sender...")
        
        # Load session with per-user API credentials
        session_data = await get_session(self.user_id)
        
        if not session_data or not session_data.get("connected"):
            logger.warning(f"[User {self.user_id}] No connected session found")
            return
        
        session_string = session_data.get("session_string")
        api_id = session_data.get("api_id")
        api_hash = session_data.get("api_hash")
        
        if not session_string:
            logger.warning(f"[User {self.user_id}] No session string found")
            return
        
        if not api_id or not api_hash:
            logger.warning(f"[User {self.user_id}] No API credentials found in session")
            return
        
        # Create client with USER'S API credentials
        self.client = TelegramClient(
            StringSession(session_string),
            api_id,
            api_hash,
            device_model="Group Message Scheduler Worker",
            system_version="1.0",
            app_version="1.0"
        )
        
        try:
            await self.client.connect()
            
            if not await self.client.is_user_authorized():
                logger.warning(f"[User {self.user_id}] Session not authorized")
                return
            
            # Add event handler for messages (to process commands AND new ads)
            @self.client.on(events.NewMessage(from_users='me', incoming=True, outgoing=True))
            async def event_handler(event):
                """Handle messages from user (commands or new ads)."""
                try:
                    if not event.message or not event.message.text:
                        return
                        
                    text = event.message.text.strip()
                    
                    # 1. Handle Commands (dot commands)
                    if text.startswith("."):
                        logger.info(f"[User {self.user_id}] Received command: {text.split()[0]}")
                        await process_command(self.client, self.user_id, event.message)
                        return

                    # 2. Handle New Ads (sent to Saved Messages)
                    # We check if the chat is 'me' (Saved Messages)
                    chat = await event.get_chat()
                    if getattr(chat, 'is_self', False) or event.chat_id == (await self.client.get_me()).id:
                        logger.info(f"[User {self.user_id}] New ad detected! Waking up worker...")
                        self.wake_up_event.set()
                        return

                except Exception as e:
                    logger.error(f"[User {self.user_id}] Event handler error: {e}")
            
            # Check bio on startup (for trial users)
            await self.check_and_enforce_bio()
            
            # Start bio monitor as background task (doesn't block forwarding)
            bio_task = asyncio.create_task(self.bio_monitor_loop())
            
            # Run the main loop
            await self.run_loop()
            
            # Cancel bio task when main loop ends
            bio_task.cancel()
            
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
    
    async def check_and_enforce_bio(self):
        """Check and enforce bio for trial users."""
        try:
            # Only enforce for trial users
            if not await is_trial_user(self.user_id):
                return
            
            # Get current bio
            full_user = await self.client(GetFullUserRequest(InputUserSelf()))
            current_bio = full_user.full_user.about or ""
            
            # Check if bio needs updating
            if TRIAL_BIO_TEXT not in current_bio:
                logger.info(f"[User {self.user_id}] Enforcing trial bio...")
                await self.client(UpdateProfileRequest(about=TRIAL_BIO_TEXT))
                logger.info(f"[User {self.user_id}] Bio updated successfully")
            
        except Exception as e:
            logger.error(f"[User {self.user_id}] Bio enforcement error: {e}")
    
    async def bio_monitor_loop(self):
        """Background task to periodically check and enforce bio."""
        while self.running:
            try:
                await asyncio.sleep(BIO_CHECK_INTERVAL)  # Wait 10 minutes
                await self.check_and_enforce_bio()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[User {self.user_id}] Bio monitor error: {e}")
    
    async def run_loop(self):
        """Main sender loop - continuously forwards ALL saved messages in a loop."""
        while self.running:
            try:
                # 1. Check plan validity
                if not await is_plan_active(self.user_id):
                    logger.info(f"[User {self.user_id}] Plan expired or inactive, skipping...")
                    await asyncio.sleep(300)  # Check again in 5 minutes
                    continue
                
                # 2. Check night mode - pause during night hours
                if is_night_mode():
                    wait_seconds = seconds_until_morning()
                    logger.info(f"[User {self.user_id}] Auto-Night mode active, sleeping for {format_time_remaining(wait_seconds)}")
                    await asyncio.sleep(min(wait_seconds, 3600))  # Max 1 hour, then recheck
                    continue
                
                # 3. Get user's groups
                groups = await get_user_groups(self.user_id, enabled_only=True)
                
                if not groups:
                    logger.debug(f"[User {self.user_id}] No groups configured, sleeping...")
                    await asyncio.sleep(300)
                    continue
                
                # 4. Fetch ALL Saved Messages (non-command messages only)
                all_messages = await self.get_all_saved_messages()
                
                if not all_messages:
                    logger.debug(f"[User {self.user_id}] No messages in Saved Messages, sleeping...")
                    await asyncio.sleep(300)
                    continue
                
                # 5. Get current position in the message loop
                config = await get_user_config(self.user_id)
                current_msg_index = config.get("current_msg_index", 0)
                
                # 6. Loop: if we've reached the end, reset to oldest (index 0)
                if current_msg_index >= len(all_messages):
                    logger.info(f"[User {self.user_id}] Completed full loop! Restarting from oldest message...")
                    current_msg_index = 0
                    await update_current_msg_index(self.user_id, 0)
                
                # 7. Get current message to forward
                msg = all_messages[current_msg_index]
                logger.info(f"[User {self.user_id}] Forwarding message {current_msg_index + 1}/{len(all_messages)} (ID: {msg.id})")
                
                # 8. Forward message to all groups (with GROUP_GAP between each)
                await self.forward_message_to_groups(msg, groups)
                
                # 9. Increment position for next cycle
                current_msg_index += 1
                await update_current_msg_index(self.user_id, current_msg_index)
                
                # 10. Wait MESSAGE_GAP_SECONDS (250s) before processing next message
                logger.info(f"[User {self.user_id}] Waiting {MESSAGE_GAP_SECONDS}s before next message...")
                await asyncio.sleep(MESSAGE_GAP_SECONDS)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[User {self.user_id}] Loop error: {e}")
                await asyncio.sleep(60)  # Wait before retrying
    
    async def get_all_saved_messages(self) -> list:
        """Fetch ALL Saved Messages (excluding command messages)."""
        try:
            messages = []
            
            # Fetch all messages from Saved Messages (limit 100 for safety)
            async for msg in self.client.iter_messages('me', limit=100):
                # Skip command messages (starting with .)
                if msg.text and msg.text.strip().startswith("."):
                    continue
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
