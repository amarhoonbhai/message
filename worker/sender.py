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
            # Retry connection up to 3 times with exponential backoff
            max_retries = 3
            for attempt in range(1, max_retries + 1):
                try:
                    await self.client.connect()
                    if await self.client.is_user_authorized():
                        break
                    else:
                        self.logger.warning(f"[User {self.user_id}] Session not authorized (attempt {attempt}/{max_retries})")
                        if attempt < max_retries:
                            await asyncio.sleep(5 * (2 ** (attempt - 1)))  # 5s, 10s, 20s
                            continue
                        return
                except (ConnectionError, OSError) as conn_err:
                    self.logger.warning(f"[User {self.user_id}] Connection failed (attempt {attempt}/{max_retries}): {conn_err}")
                    if attempt < max_retries:
                        await asyncio.sleep(5 * (2 ** (attempt - 1)))
                        continue
                    return
            
            # Handler 1: Outgoing messages from self (commands + new ads in Saved Messages)
            @self.client.on(events.NewMessage(outgoing=True))
            async def outgoing_handler(event):
                """Handle outgoing messages: dot commands and new ads."""
                try:
                    if not event.message:
                        return
                    
                    text = (event.message.text or "").strip()
                    
                    # 1. Handle Commands (dot commands)
                    if text.startswith("."):
                        self.logger.info(f"[User {self.user_id}] Received command: {text.split()[0]}")
                        await process_command(self.client, self.user_id, event.message)
                        return

                    # 2. Handle New Ads (sent to Saved Messages)
                    chat = await event.get_chat()
                    is_saved = getattr(chat, 'is_self', False)
                    if not is_saved:
                        try:
                            me = await self.client.get_me()
                            is_saved = event.chat_id == me.id
                        except Exception:
                            pass
                    
                    if is_saved:
                        self.logger.info(f"[User {self.user_id}][{self.phone}] New ad detected! Waking up worker...")
                        self.wake_up_event.set()
                        await asyncio.sleep(0.1)
                        self.wake_up_event.clear()

                except Exception as e:
                    self.logger.error(f"[User {self.user_id}][{self.phone}] Outgoing handler error: {e}")

            # Handler 2: Incoming private messages from others (auto-responder)
            @self.client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
            async def incoming_handler(event):
                """Handle incoming private messages for auto-responder."""
                try:
                    await self.handle_auto_reply(event)
                except Exception as e:
                    self.logger.error(f"[User {self.user_id}][{self.phone}] Incoming handler error: {e}")
            
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
        """Main sender loop - INFINITE LOOP with Smart Proper Rotation."""
        while self.running:
            try:
                # 0. Log session status
                self.logger.info(f"[User {self.user_id}][{self.phone}] Current cycle checking config...")
                await update_session_activity(self.user_id, self.phone)
                
                # 1. Check plan validity
                if not await is_plan_active(self.user_id):
                    self.logger.info(f"[User {self.user_id}][{self.phone}] Plan expired or inactive, sleeping 5 min...")
                    await asyncio.sleep(300)
                    continue
                
                # 2. Check night mode
                if is_night_mode():
                    wait_seconds = seconds_until_morning()
                    self.logger.info(f"[User {self.user_id}][{self.phone}] Auto-Night mode, sleeping {format_time_remaining(wait_seconds)}...")
                    await asyncio.sleep(min(wait_seconds, 3600))
                    continue
                
                # 3. Get groups and messages
                groups = await get_user_groups(self.user_id, enabled_only=True, phone=self.phone)
                if not groups:
                    self.logger.debug(f"[User {self.user_id}][{self.phone}] No groups yet, waiting...")
                    await asyncio.sleep(300)
                    continue
                
                all_messages = await self.get_all_saved_messages()
                if not all_messages:
                    self.logger.debug(f"[User {self.user_id}][{self.phone}] No messages yet, waiting...")
                    await asyncio.sleep(300)
                    continue
                
                # 4. Build proper smart rotation pairs
                config = await get_user_config(self.user_id)
                shuffle_mode = config.get("shuffle_mode", False)
                copy_mode = config.get("copy_mode", False)
                
                pairs = []
                for j in range(len(groups)):
                    for i in range(len(all_messages)):
                        # Proper rotation: group index shifts so we don't spam same group continuously
                        grp_idx = (j + i) % len(groups)
                        pairs.append((all_messages[i], groups[grp_idx]))
                
                if shuffle_mode:
                    random.shuffle(pairs)
                
                # 5. Get current step (resilient state saving)
                current_step = config.get("current_msg_index", 0)
                
                if current_step >= len(pairs) or current_step < 0:
                    # CYCLE COMPLETE
                    user_interval_minutes = config.get("interval_min", DEFAULT_INTERVAL_MINUTES)
                    self.logger.info(f"[User {self.user_id}] 🔄 Loop cycle complete! Waiting {user_interval_minutes} minutes before restarting...")
                    
                    cycle_wait_seconds = user_interval_minutes * 60
                    elapsed = 0
                    while elapsed < cycle_wait_seconds and self.running:
                        if is_night_mode():
                            wait_seconds = seconds_until_morning()
                            await asyncio.sleep(min(wait_seconds, 3600))
                            continue
                        sleep_chunk = min(60, cycle_wait_seconds - elapsed)
                        await asyncio.sleep(sleep_chunk)
                        elapsed += sleep_chunk
                    
                    self.logger.info(f"[User {self.user_id}] ▶️ Cycle interval complete! Restarting...")
                    current_step = 0
                    await update_current_msg_index(self.user_id, 0)
                    continue # Re-fetch groups and messages for the new cycle
                
                # 6. Get the pair to send
                msg, group = pairs[current_step]
                total_steps = len(pairs)
                
                self.logger.info(f"[User {self.user_id}] 📤 (Step {current_step + 1}/{total_steps}) Forwarding msg {msg.id} to {group.get('chat_title')}...")
                
                # 7. Send the single message
                flood_triggered, flood_wait = await self.forward_single_message(msg, group, copy_mode=copy_mode)
                
                if flood_triggered:
                    self.logger.warning(f"[User {self.user_id}] ⚠️ Flood detected, sleeping {flood_wait}s (supersedes all logic)...")
                    await asyncio.sleep(flood_wait)
                    continue # Do not increment step, retry same message later!
                
                # 8. Increment and save state! Resilient crash-proof state!
                current_step += 1
                await update_current_msg_index(self.user_id, current_step)
                
                # 9. Smart Interval Delay!
                if current_step < len(pairs):
                    # Every time we complete `len(groups)` amount of sends, we apply the MESSAGE_GAP.
                    # Otherwise, use the GROUP_GAP.
                    is_batch_end = (current_step % len(groups) == 0)
                    
                    if is_batch_end:
                        base_gap = MESSAGE_GAP_SECONDS
                        gap_type = "MESSAGE_GAP"
                    else:
                        base_gap = GROUP_GAP_SECONDS
                        gap_type = "GROUP_GAP"
                    
                    # Apply anti-spam jitter
                    jitter_min = int(base_gap * 0.8)
                    jitter_max = int(base_gap * 1.5)
                    wait_time = random.randint(max(5, jitter_min), jitter_max)
                    
                    self.logger.info(f"[User {self.user_id}] ⏳ Waiting {wait_time}s ({gap_type} + Jitter) before next step...")
                    
                    elapsed = 0
                    while elapsed < wait_time and self.running:
                        if is_night_mode():
                            wait_seconds = seconds_until_morning()
                            self.logger.info(f"[User {self.user_id}] 🌙 Night mode forced, pausing {format_time_remaining(wait_seconds)}...")
                            await asyncio.sleep(min(wait_seconds, 3600))
                            continue
                        sleep_chunk = min(30, wait_time - elapsed)
                        await asyncio.sleep(sleep_chunk)
                        elapsed += sleep_chunk
                else:
                    self.logger.info(f"[User {self.user_id}] ✅ Last step in cycle forwarded (no gap wait)")
                
            except asyncio.CancelledError:
                self.logger.info(f"[User {self.user_id}] Loop cancelled (shutdown)")
                break
            except Exception as e:
                self.logger.error(f"[User {self.user_id}] Loop error: {e} - retrying in 60s...")
                await asyncio.sleep(60)
    
    async def get_all_saved_messages(self) -> list:
        """Fetch ALL Saved Messages (excluding command messages)."""
        try:
            messages = []
            async for msg in self.client.iter_messages('me', limit=100):
                if msg.text and msg.text.strip().startswith("."):
                    continue
                messages.append(msg)
            messages.reverse()
            return messages
        except Exception as e:
            logger.error(f"[User {self.user_id}] Error fetching saved messages: {e}")
            return []
    
    async def forward_single_message(self, message, group: dict, copy_mode: bool = False) -> tuple:
        """
        Forward or copy a single message to a single group.
        Returns: (flood_triggered: bool, flood_wait_seconds: int)
        """
        chat_id = group.get("chat_id")
        chat_title = group.get("chat_title", "Unknown")
        
        try:
            if copy_mode:
                await self.client.send_message(
                    entity=chat_id,
                    message=message.message,
                    file=message.media,
                    formatting_entities=message.entities
                )
                log_action = "Copied"
            else:
                await self.client.forward_messages(
                    entity=chat_id,
                    messages=message.id,
                    from_peer=InputPeerSelf()
                )
                log_action = "Forwarded"
            
            logger.info(f"[User {self.user_id}] {log_action} message {message.id} to {chat_title}")
            
            await log_send(
                user_id=self.user_id,
                chat_id=chat_id,
                saved_msg_id=message.id,
                status="success",
                phone=self.phone
            )
            return (False, 0)
            
        except FloodWaitError as e:
            logger.warning(f"[User {self.user_id}] FloodWait: {e.seconds}s on {chat_title} (superseding logic)")
            await log_send(self.user_id, chat_id, message.id, "flood_wait", f"FloodWait {e.seconds}s", phone=self.phone)
            return (True, int(e.seconds * 1.5) + 10)
            
        except PeerFloodError:
            logger.error(f"[User {self.user_id}] PeerFlood error on {chat_title} - signaling 1 hour pause")
            await log_send(self.user_id, chat_id, message.id, "peer_flood", "PeerFlood", phone=self.phone)
            return (True, 3600)
            
        except (ChatWriteForbiddenError, ChannelPrivateError, ChatAdminRequiredError, UserBannedInChannelError) as e:
            logger.warning(f"[User {self.user_id}] Removing group {chat_title}: {type(e).__name__}")
            await remove_group(self.user_id, chat_id)
            await log_send(self.user_id, chat_id, message.id, "removed", str(e), phone=self.phone)
            return (False, 0)
            
        except InputUserDeactivatedError:
            logger.error(f"[User {self.user_id}] User account deactivated!")
            await log_send(self.user_id, chat_id, message.id, "failed", "UserDeactivated", phone=self.phone)
            self.running = False
            return (False, 0)
            
        except MultiError as e:
            real_error = e.exceptions[0] if e.exceptions else e
            logger.error(f"[User {self.user_id}] MultiError forwarding to {chat_title}: {real_error}")
            await log_send(self.user_id, chat_id, message.id, "failed", f"MultiError: {real_error}", phone=self.phone)
            return (False, 0)
            
        except RPCError as e:
            error_msg = str(e).upper()
            if any(x in error_msg for x in ["CHAT_ADMIN_REQUIRED", "CHAT_WRITE_FORBIDDEN", "USER_BANNED_IN_CHANNEL"]):
                logger.warning(f"[User {self.user_id}] Removing group {chat_title} due to RPC error: {e}")
                await remove_group(self.user_id, chat_id)
                await log_send(self.user_id, chat_id, message.id, "removed", str(e), phone=self.phone)
            else:
                logger.error(f"[User {self.user_id}] RPC Error forwarding to {chat_title}: {e}")
                await log_send(self.user_id, chat_id, message.id, "failed", str(e), phone=self.phone)
            return (False, 0)
            
        except Exception as e:
            logger.error(f"[User {self.user_id}] Error forwarding to {chat_title}: {e}")
            await log_send(self.user_id, chat_id, message.id, "failed", str(e), phone=self.phone)
            return (False, 0)
