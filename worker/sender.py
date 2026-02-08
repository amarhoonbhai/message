"""
Per-user sender logic for the Worker service.
Uses per-user API credentials stored in session.
"""

import logging
import asyncio
import random
from datetime import datetime
from typing import Optional, List

from telethon import TelegramClient, events, utils
from telethon.sessions import StringSession
from telethon.errors import (
    FloodWaitError,
    PeerFloodError,
    ChatWriteForbiddenError,
    ChannelPrivateError,
    ChatAdminRequiredError,
    UserBannedInChannelError,
    InputUserDeactivatedError,
    RPCError,
    MultiError
)
from telethon.tl.types import InputPeerSelf, InputUserSelf, MessageService
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.account import UpdateProfileRequest

from config import GROUP_GAP_SECONDS, MESSAGE_GAP_SECONDS, DEFAULT_INTERVAL_MINUTES, TRIAL_BIO_TEXT, BIO_CHECK_INTERVAL
from db.models import (
    get_session, get_user_groups, get_user_config,
    update_last_saved_id, update_current_msg_index,
    is_plan_active, log_send, remove_group, update_session_activity,
    is_trial_user
)
from worker.utils import (
    is_night_mode, seconds_until_morning, format_time_remaining,
    UserLogAdapter
)
from worker.commands import process_command  # Used by event handler

logger = logging.getLogger(__name__)


class UserSender:
    """Handles message sending for a single user using their own API credentials."""
    
    def __init__(self, user_id: int, phone: str):
        self.user_id = user_id
        self.phone = phone
        self.client = None
        self.running = False
        
        # Professional Logging with Adapter
        self.logger = UserLogAdapter(logger, {'user_id': user_id, 'phone': phone})
        self.wake_up_event = asyncio.Event()
        self.responder_cache = {}  # Cache: {sender_id: timestamp} to avoid double-replies
    
    async def start(self):
        """Start the sender loop."""
        self.running = True
        
        self.logger.info(f"[User {self.user_id}][{self.phone}] Starting sender...")
        
        # Load session with per-user API credentials
        session_data = await get_session(self.user_id, self.phone)
        
        if not session_data or not session_data.get("connected"):
            self.logger.warning(f"[User {self.user_id}][{self.phone}] No connected session found")
            return
        
        session_string = session_data.get("session_string")
        api_id = session_data.get("api_id")
        api_hash = session_data.get("api_hash")
        
        if not session_string:
            self.logger.warning(f"[User {self.user_id}] No session string found")
            return
        
        if not api_id or not api_hash:
            self.logger.warning(f"[User {self.user_id}] No API credentials found in session")
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
        self.client.phone = self.phone  # Attach phone for commands to access it
        
        try:
            await self.client.connect()
            
            if not await self.client.is_user_authorized():
                self.logger.warning(f"[User {self.user_id}] Session not authorized")
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
                        self.logger.info(f"[User {self.user_id}] Received command: {text.split()[0]}")
                        await process_command(self.client, self.user_id, event.message)
                        return

                    # 2. Handle New Ads (sent to Saved Messages)
                    # We check if the chat is 'me' (Saved Messages)
                    chat = await event.get_chat()
                    is_me = getattr(chat, 'is_self', False) or event.chat_id == (await self.client.get_me()).id
                    
                    if is_me:
                        self.logger.info(f"[User {self.user_id}][{self.phone}] New ad detected! Waking up worker...")
                        self.wake_up_event.set()
                        return

                    # 3. Handle Auto-Responder (Incoming PMs from others)
                    if event.is_private and not is_me:
                        await self.handle_auto_reply(event)

                except Exception as e:
                    self.logger.error(f"[User {self.user_id}][{self.phone}] Event handler error: {e}")
            
            # Check bio on startup (for trial users)
            await self.check_and_enforce_bio()
            
            # Start bio monitor as background task (doesn't block forwarding)
            bio_task = asyncio.create_task(self.bio_monitor_loop())
            
            # Run the main loop
            await self.run_loop()
            
            # Cancel bio task when main loop ends
            bio_task.cancel()
            
        except Exception as e:
            self.logger.error(f"[User {self.user_id}][{self.phone}] Error: {e}")
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
                self.logger.info(f"[User {self.user_id}] Enforcing trial bio...")
                await self.client(UpdateProfileRequest(about=TRIAL_BIO_TEXT))
                self.logger.info(f"[User {self.user_id}] Bio updated successfully")
            
        except Exception as e:
            self.logger.error(f"[User {self.user_id}] Bio enforcement error: {e}")
    
    async def bio_monitor_loop(self):
        """Background task to periodically check and enforce bio."""
        while self.running:
            try:
                await asyncio.sleep(BIO_CHECK_INTERVAL)  # Wait 10 minutes
                await self.check_and_enforce_bio()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"[User {self.user_id}] Bio monitor error: {e}")
    
    async def handle_auto_reply(self, event):
        """Send automated reply to incoming private messages."""
        try:
            sender = await event.get_sender()
            sender_id = event.sender_id
            
            # Skip bots and deleted users
            if not sender or getattr(sender, 'bot', False):
                return
            
            # 1. Check if responder is enabled
            config = await get_user_config(self.user_id)
            if not config.get("auto_reply_enabled", False):
                return
            
            # 2. Prevent spamming (reply once every 24h per user)
            now = datetime.utcnow().timestamp()
            last_reply = self.responder_cache.get(sender_id, 0)
            if now - last_reply < 86400:  # 24 hours
                return
            
            reply_text = config.get("auto_reply_text", "Hello! Thanks for your message.")
            
            self.logger.info(f"[User {self.user_id}] Sending auto-reply to {sender_id}")
            await event.reply(reply_text)
            
            # Update cache
            self.responder_cache[sender_id] = now
            
        except Exception as e:
            self.logger.error(f"[User {self.user_id}] Auto-reply error: {e}")

    async def run_loop(self):
        """Main sender loop - INFINITE LOOP that continuously forwards ALL saved messages."""
        while self.running:
            try:
                # 0. Log session status
                self.logger.info(f"[User {self.user_id}][{self.phone}] Current cycle starting...")
                await update_session_activity(self.user_id, self.phone)
                
                # 1. Check plan validity
                if not await is_plan_active(self.user_id):
                    self.logger.info(f"[User {self.user_id}][{self.phone}] Plan expired or inactive, sleeping 5 min...")
                    await asyncio.sleep(300)
                    continue  # Never exit, just continue checking
                
                # 2. Check night mode - pause during night hours
                if is_night_mode():
                    wait_seconds = seconds_until_morning()
                    self.logger.info(f"[User {self.user_id}][{self.phone}] Auto-Night mode, sleeping {format_time_remaining(wait_seconds)}...")
                    await asyncio.sleep(min(wait_seconds, 3600))
                    continue  # Never exit, resume after night
                
                # 3. Get user's groups FOR THIS ACCOUNT
                groups = await get_user_groups(self.user_id, enabled_only=True, phone=self.phone)
                
                if not groups:
                    self.logger.debug(f"[User {self.user_id}][{self.phone}] No groups yet for this account, waiting...")
                    await asyncio.sleep(300)
                    continue  # Never exit, keep waiting for groups
                
                # 3.5 Get user's config for modes
                config = await get_user_config(self.user_id)
                shuffle_mode = config.get("shuffle_mode", False)
                copy_mode = config.get("copy_mode", False)
                
                if shuffle_mode:
                    self.logger.debug(f"[User {self.user_id}][{self.phone}] Shuffle Mode enabled - randomizing groups")
                    random.shuffle(groups)
                
                # 4. Fetch ALL Saved Messages (non-command messages only)
                all_messages = await self.get_all_saved_messages()
                
                if not all_messages:
                    self.logger.debug(f"[User {self.user_id}][{self.phone}] No messages yet, waiting...")
                    await asyncio.sleep(300)
                    continue  # Never exit, keep waiting for messages
                
                # 5. Get current position in the message loop
                config = await get_user_config(self.user_id)
                current_msg_index = config.get("current_msg_index", 0)
                
                # Get user's configured interval (or default if not set)
                user_interval_minutes = config.get("interval_min", DEFAULT_INTERVAL_MINUTES)
                
                # 6. CRITICAL: Reset index if out of bounds (ensures infinite loop)
                # This handles: single message, message deletion, first run, etc.
                if current_msg_index >= len(all_messages) or current_msg_index < 0:
                    self.logger.info(f"[User {self.user_id}] 🔄 Loop cycle complete! Waiting {user_interval_minutes} minutes before restarting...")
                    
                    # Wait for the full cycle interval before restarting
                    # Sleep in chunks to respect Auto-Night pauses
                    cycle_wait_seconds = user_interval_minutes * 60
                    elapsed = 0
                    while elapsed < cycle_wait_seconds and self.running:
                        # Check for night mode during wait
                        if is_night_mode():
                            wait_seconds = seconds_until_morning()
                            self.logger.info(f"[User {self.user_id}] Auto-Night mode during cycle wait, sleeping {format_time_remaining(wait_seconds)}...")
                            await asyncio.sleep(min(wait_seconds, 3600))
                            continue  # Don't count night pause toward elapsed time
                        
                        # Sleep in 60s chunks for responsiveness
                        sleep_chunk = min(60, cycle_wait_seconds - elapsed)
                        await asyncio.sleep(sleep_chunk)
                        elapsed += sleep_chunk
                    
                    self.logger.info(f"[User {self.user_id}] ▶️ Cycle interval complete! Restarting from message 1...")
                    current_msg_index = 0
                    await update_current_msg_index(self.user_id, 0)
                
                # 7. Get current message to forward
                msg = all_messages[current_msg_index]
                total_msgs = len(all_messages)
                self.logger.info(f"[User {self.user_id}] 📤 Forwarding message {current_msg_index + 1}/{total_msgs} to {len(groups)} group(s)...")
                
                # 8. Forward message to ALL groups (with GROUP_GAP between each)
                # Returns (flood_triggered, flood_wait_seconds) - flood supersedes all logic
                flood_triggered, flood_wait = await self.forward_message_to_groups(msg, groups, copy_mode=copy_mode)
                
                if flood_triggered:
                    # Flood wait supersedes all other timing - sleep and restart loop
                    self.logger.warning(f"[User {self.user_id}] ⚠️ Flood detected, sleeping {flood_wait}s (supersedes all logic)...")
                    await asyncio.sleep(flood_wait)
                    continue  # Restart loop without incrementing message index
                
                # 9. Increment position for next iteration
                current_msg_index += 1
                await update_current_msg_index(self.user_id, current_msg_index)
                
                # 10. Wait MESSAGE_GAP only if more messages remain (state-driven)
                if current_msg_index < len(all_messages):
                    self.logger.info(f"[User {self.user_id}] ⏳ Waiting {MESSAGE_GAP_SECONDS}s before next message...")
                    
                    # Chunked sleep to respect night mode pauses
                    elapsed = 0
                    while elapsed < MESSAGE_GAP_SECONDS and self.running:
                        if is_night_mode():
                            wait_seconds = seconds_until_morning()
                            self.logger.info(f"[User {self.user_id}] 🌙 Night mode during message gap, pausing {format_time_remaining(wait_seconds)}...")
                            await asyncio.sleep(min(wait_seconds, 3600))
                            continue  # Don't count night pause toward elapsed time
                        
                        # Sleep in 30s chunks for responsiveness
                        sleep_chunk = min(30, MESSAGE_GAP_SECONDS - elapsed)
                        await asyncio.sleep(sleep_chunk)
                        elapsed += sleep_chunk
                else:
                    self.logger.info(f"[User {self.user_id}] ✅ Last message forwarded, cycle complete (no gap wait)")
                
                # Loop continues automatically - NEVER exits here
                
            except asyncio.CancelledError:
                self.logger.info(f"[User {self.user_id}] Loop cancelled (shutdown)")
                break  # Only exit on explicit cancellation
            except Exception as e:
                self.logger.error(f"[User {self.user_id}] Loop error: {e} - retrying in 60s...")
                await asyncio.sleep(60)
                # Continue the loop, never exit on errors
    
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
    
    async def forward_message_to_groups(self, message, groups: list, copy_mode: bool = False) -> tuple:
        """
        Forward or copy a message to all enabled groups.
        Returns: (flood_triggered: bool, flood_wait_seconds: int)
        """
        flood_triggered = False
        flood_wait_seconds = 0
        
        for i, group in enumerate(groups):
            chat_id = group.get("chat_id")
            chat_title = group.get("chat_title", "Unknown")
            
            try:
                # Decide between Forward and Copy
                if copy_mode:
                    # COPY MODE: Send as a new message to hide "Forwarded from" and bypass restrictions
                    await self.client.send_message(
                        entity=chat_id,
                        message=message.message,
                        file=message.media,
                        formatting_entities=message.entities
                    )
                    log_action = "Copied"
                else:
                    # FORWARD MODE: Standard forwarding
                    await self.client.forward_messages(
                        entity=chat_id,
                        messages=message.id,
                        from_peer=InputPeerSelf()
                    )
                    log_action = "Forwarded"
                
                logger.info(f"[User {self.user_id}] {log_action} message {message.id} to {chat_title}")
                
                # Log success
                await log_send(
                    user_id=self.user_id,
                    chat_id=chat_id,
                    saved_msg_id=message.id,
                    status="success",
                    phone=self.phone
                )
                
            except FloodWaitError as e:
                # Flood wait supersedes all logic - return immediately
                logger.warning(f"[User {self.user_id}] FloodWait: {e.seconds}s (superseding all logic)")
                await log_send(self.user_id, chat_id, message.id, "flood_wait", f"FloodWait {e.seconds}s", phone=self.phone)
                return (True, e.seconds + 10)  # Return flood state, let caller handle sleep
                
            except PeerFloodError:
                # PeerFlood is severe - return with 1 hour wait
                logger.error(f"[User {self.user_id}] PeerFlood error - signaling 1 hour pause")
                await log_send(self.user_id, chat_id, message.id, "peer_flood", "PeerFlood", phone=self.phone)
                return (True, 3600)  # 1 hour pause
                
            except (ChatWriteForbiddenError, ChannelPrivateError, 
                    ChatAdminRequiredError, UserBannedInChannelError) as e:
                # Remove group - access revoked
                logger.warning(f"[User {self.user_id}] Removing group {chat_title}: {type(e).__name__}")
                await remove_group(self.user_id, chat_id)
                await log_send(self.user_id, chat_id, message.id, "removed", str(e), phone=self.phone)
                continue  # Skip to next group
                
            except InputUserDeactivatedError:
                logger.error(f"[User {self.user_id}] User account deactivated!")
                await log_send(self.user_id, chat_id, message.id, "failed", "UserDeactivated", phone=self.phone)
                return (False, 0)
                
            except MultiError as e:
                # Handle MultiError - extract the first real error
                real_error = e.exceptions[0] if e.exceptions else e
                logger.error(f"[User {self.user_id}] MultiError forwarding to {chat_title}: {real_error}")
                await log_send(self.user_id, chat_id, message.id, "failed", f"MultiError: {real_error}", phone=self.phone)
                
            except RPCError as e:
                # Catch specific RPC errors that mean "forbidden" but aren't typed exceptions
                error_msg = str(e).upper()
                if any(x in error_msg for x in ["CHAT_ADMIN_REQUIRED", "CHAT_WRITE_FORBIDDEN", "USER_BANNED_IN_CHANNEL"]):
                    logger.warning(f"[User {self.user_id}] Removing group {chat_title} due to RPC error: {e}")
                    await remove_group(self.user_id, chat_id)
                    await log_send(self.user_id, chat_id, message.id, "removed", str(e), phone=self.phone)
                else:
                    logger.error(f"[User {self.user_id}] RPC Error forwarding to {chat_title}: {e}")
                    await log_send(self.user_id, chat_id, message.id, "failed", str(e), phone=self.phone)
                
            except Exception as e:
                logger.error(f"[User {self.user_id}] Error forwarding to {chat_title}: {e}")
                await log_send(self.user_id, chat_id, message.id, "failed", str(e), phone=self.phone)
            
            # Wait between groups (except for last one) - with JITTER
            if i < len(groups) - 1:
                # ANTI-SPAM JITTER: Randomize delay between 80% and 120% of config
                jitter_min = int(GROUP_GAP_SECONDS * 0.8)
                jitter_max = int(GROUP_GAP_SECONDS * 1.5)
                wait_time = random.randint(max(5, jitter_min), jitter_max)
                
                logger.debug(f"[User {self.user_id}] Waiting {wait_time}s (Jitter) before next group")
                await asyncio.sleep(wait_time)
        
        # No flood occurred, return success state
        return (False, 0)
