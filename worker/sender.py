"""
Per-user sender logic for the Worker service.
Uses per-user API credentials stored in session.
"""

import logging
import asyncio
import random
from datetime import datetime, timedelta
from typing import Optional, List, Any, Dict

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
    MultiError,
    ChannelInvalidError,
    UsernameNotOccupiedError,
    UsernameInvalidError,
    InviteHashExpiredError
)
from telethon.tl.types import InputPeerSelf, InputUserSelf, MessageService
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.account import UpdateProfileRequest

from config import (
    API_ID, API_HASH,
    GROUP_GAP_SECONDS, MESSAGE_GAP_SECONDS, DEFAULT_INTERVAL_MINUTES,
    MIN_INTERVAL_MINUTES, TRIAL_BIO_TEXT, BIO_CHECK_INTERVAL, OWNER_ID,
    MAX_GROUPS_PER_USER
)
from db.models import (
    get_session, get_user_groups, get_user_config,
    update_last_saved_id, update_current_msg_index,
    is_plan_active, log_send, remove_group, toggle_group,
    update_session_activity, is_trial_user, get_all_user_sessions,
    mark_session_auth_failed, mark_session_disabled, reset_session_auth_fails
)
from worker.utils import (
    is_night_mode, seconds_until_morning, format_time_remaining,
    UserLogAdapter
)
from worker.commands import process_command  # Used by event handler

logger = logging.getLogger(__name__)


class AdaptiveDelayController:
    """Dynamically adjusts gaps based on FloodWait and success rates."""
    MAX_MULTIPLIER = 10.0  # Hard cap — prevents runaway wait times

    def __init__(self, base_gap: int):
        self.base_gap = base_gap
        self.multiplier = 1.0
        self.success_streak = 0
        self.last_flood_at = None

    def get_gap(self) -> int:
        return int(self.base_gap * self.multiplier)

    def on_flood(self, wait_seconds: int):
        self.last_flood_at = datetime.utcnow()
        new_mult = max(self.multiplier * 1.5, (wait_seconds / self.base_gap) * 1.1)
        self.multiplier = min(new_mult, self.MAX_MULTIPLIER)  # cap applied
        self.success_streak = 0

    def on_success(self):
        self.success_streak += 1
        # Every 10 successes, slowly decrease multiplier back to 1.0
        if self.success_streak >= 10 and self.multiplier > 1.0:
            self.multiplier = max(1.0, self.multiplier * 0.9)
            self.success_streak = 0


class UserSender:
    """Handles message sending for a single user using their own API credentials."""
    
    # After this many consecutive auth failures, the session is permanently disabled
    MAX_AUTH_FAILURES = 3

    def __init__(self, user_id: int, phone: str, semaphore: asyncio.Semaphore = None):
        self.user_id = user_id
        self.phone = phone
        self.client = None
        self.running = False
        # Semaphore shared across all senders — caps simultaneous Telethon connections
        self._semaphore = semaphore or asyncio.Semaphore(1)
        
        # Professional Logging with Adapter
        self.logger = UserLogAdapter(logger, {'user_id': user_id, 'phone': phone})
        self.wake_up_event = asyncio.Event()
        self.responder_cache = {}  # Cache: {sender_id: timestamp} to avoid double-replies
        self.status = "Initializing"
        self.message_counter = 0  # Track total sends in this session
        
        # Performance & Reliability state
        self.config_cache = {} # {key: (value, expiry)}
        self.adaptive_group_gap = AdaptiveDelayController(GROUP_GAP_SECONDS)
        self.adaptive_msg_gap = AdaptiveDelayController(MESSAGE_GAP_SECONDS)
        self.last_heartbeat = None
        self.error_streak = 0
        self.first_run = True  # Flag for staggered first cycle
    
    async def update_status(self, status: str):
        """Update worker status in database for the current account."""
        self.status = status
        try:
            from db.database import get_database
            db = get_database()
            await db.sessions.update_one(
                {"user_id": self.user_id, "phone": self.phone},
                {"$set": {
                    "worker_status": status, 
                    "status_updated_at": datetime.utcnow(),
                    "error_streak": self.error_streak,
                    "last_flood_at": self.adaptive_group_gap.last_flood_at
                }}
            )
        except Exception:
            pass

    async def _get_cached_config(self):
        """Get user config with 5-minute TTL cache."""
        cache_key = f"config_{self.user_id}"
        cached = self.config_cache.get(cache_key)
        if cached:
            val, expiry = cached
            if datetime.utcnow() < expiry:
                return val
        
        config = await get_user_config(self.user_id)
        self.config_cache[cache_key] = (config, datetime.utcnow() + timedelta(minutes=5))
        return config

    async def _cached_is_plan_active(self):
        """Check plan status with 10-minute TTL cache."""
        cache_key = f"plan_{self.user_id}"
        cached = self.config_cache.get(cache_key)
        if cached:
            val, expiry = cached
            if datetime.utcnow() < expiry:
                return val
        
        active = await is_plan_active(self.user_id)
        self.config_cache[cache_key] = (active, datetime.utcnow() + timedelta(minutes=10))
        return active

    async def start(self):
        """Start the sender loop — semaphore only guards the short connect+auth phase."""
        self.running = True
        self.logger.info("Starting sender...")

        # ── Pre-flight: validate session record exists ─────────────────────
        session_data = await get_session(self.user_id, self.phone)
        if not session_data or not session_data.get("connected"):
            self.logger.warning("No connected session record found — aborting")
            return

        session_string = session_data.get("session_string", "")
        if len(session_string) < 50:  # Valid Telethon StringSession strings are very long
            self.logger.warning("Session string missing or too short — disabling")
            await mark_session_disabled(self.user_id, self.phone, "invalid_session_string")
            return

        api_id = session_data.get("api_id") or API_ID
        api_hash = session_data.get("api_hash") or API_HASH

        # Build the client first (no network yet)
        self.client = TelegramClient(
            StringSession(session_string),
            api_id,
            api_hash,
            device_model="Group Message Scheduler Worker",
            system_version="1.0",
            app_version="1.0"
        )
        self.client.phone = self.phone

        # ── Phase 1: Connect + Auth (semaphore caps simultaneous connects) ──
        # The semaphore is released as soon as auth succeeds or fails.
        # It does NOT hold during the long-running send loop.
        authorized = False
        async with self._semaphore:
            authorized = await self._connect_and_authenticate()

        if not authorized:
            if self.client:
                await self.client.disconnect()
            return

        # ── Phase 2: Run session (no semaphore — slot is already freed) ─────
        await self._run_session()

    async def _connect_and_authenticate(self) -> bool:
        """
        Connect to Telegram and verify authorization.
        Returns True if authorized, False otherwise.
        Semaphore is held only during this short phase.
        """
        try:
            await self.client.connect()
        except (ConnectionError, OSError) as conn_err:
            self.logger.warning(f"Network connection failed: {conn_err}")
            return False

        if not await self.client.is_user_authorized():
            fail_count = await mark_session_auth_failed(self.user_id, self.phone)
            if fail_count >= self.MAX_AUTH_FAILURES:
                self.logger.error(
                    f"Session unauthorized — {fail_count} failures. "
                    f"Permanently disabling."
                )
                await mark_session_disabled(
                    self.user_id, self.phone, f"auth_failed_{fail_count}x"
                )
            else:
                self.logger.warning(
                    f"Session unauthorized (failure {fail_count}/{self.MAX_AUTH_FAILURES}). "
                    f"Will retry after 6h cooldown."
                )
            return False

        # Authorized — reset any previous failure counts
        await reset_session_auth_fails(self.user_id, self.phone)
        self.logger.info("✅ Authorized successfully")
        return True

    async def _run_session(self):
        """
        Register event handlers, run background tasks, and enter the send loop.
        Called AFTER the semaphore is released — runs for the entire session lifetime.
        """
        # Initial Smart Delay: stagger startups to avoid simultaneous API bursts
        startup_delay = random.randint(10, 60)
        self.logger.info(f"🏁 Waiting {startup_delay}s (anti-burst) before loop...")
        await asyncio.sleep(startup_delay)

        try:
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
                        self.logger.info(f"Received command: {text.split()[0]}")
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
                        self.logger.info("New ad detected! Waking up worker...")
                        self.wake_up_event.set()
                        await asyncio.sleep(0.1)
                        self.wake_up_event.clear()

                except Exception as e:
                    self.logger.error(f"Outgoing handler error: {e}")

            # Handler 2: Incoming messages (auto-responder + remote commands)
            @self.client.on(events.NewMessage(incoming=True))
            async def incoming_handler(event):
                """Handle incoming messages: commands from owner + auto-responder."""
                try:
                    if not event.message or not event.message.text:
                        return
                        
                    text = event.message.text.strip()
                    sender_id = event.sender_id
                    
                    # 1. Handle Commands (Incoming from owner)
                    if text.startswith(".") and (sender_id == self.user_id or sender_id == OWNER_ID):
                        self.logger.info(f"Received remote command: {text.split()[0]}")
                        await process_command(self.client, self.user_id, event.message)
                        return

                    # 2. Handle Auto-Responder (Private messages only)
                    if event.is_private:
                        await self.handle_auto_reply(event)

                except Exception as e:
                    self.logger.error(f"Incoming handler error: {e}")
            
            # Check bio on startup (for trial users)
            await self.check_and_enforce_bio()
            
            # Start background tasks
            watchdog_task = asyncio.create_task(self._connection_watchdog())
            bio_task = asyncio.create_task(self.bio_monitor_loop())
            
            # Run the main send loop
            await self.run_loop()
            
            # Cancel tasks when main loop ends
            bio_task.cancel()
            watchdog_task.cancel()

        except Exception as e:
            self.logger.error(f"Error in session lifecycle: {e}")
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
                self.logger.info(f"Enforcing trial bio...")
                await self.client(UpdateProfileRequest(about=TRIAL_BIO_TEXT))
                self.logger.info(f"Bio updated successfully")
            
        except Exception as e:
            self.logger.error(f"Bio enforcement error: {e}")
    
    async def bio_monitor_loop(self):
        """Background task to periodically check and enforce bio."""
        while self.running:
            try:
                await asyncio.sleep(BIO_CHECK_INTERVAL)  # Wait 10 minutes
                await self.check_and_enforce_bio()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Bio monitor error: {e}")
    
    async def handle_auto_reply(self, event):
        """Send automated reply to incoming private messages."""
        try:
            sender = await event.get_sender()
            sender_id = event.sender_id
            
            # Skip bots and deleted users
            if not sender or getattr(sender, 'bot', False):
                return
            
            # 1. Check if responder is enabled
            config = await self._get_cached_config()
            if not config.get("auto_reply_enabled", False):
                return
            
            # 2. Prevent spamming (reply once every 24h per user)
            now = datetime.utcnow().timestamp()
            last_reply = self.responder_cache.get(sender_id, 0)
            if now - last_reply < 86400:  # 24 hours
                return
            
            reply_text = config.get("auto_reply_text", "Hello! Thanks for your message.")
            
            self.logger.info(f"Sending auto-reply to {sender_id}")
            await event.reply(reply_text)
            
            # Update cache
            self.responder_cache[sender_id] = now
            
        except Exception as e:
            self.logger.error(f"Auto-reply error: {e}")

    async def run_loop(self):
        """Main sender loop - INFINITE LOOP with Smart Proper Rotation."""
        while self.running:
            try:
                # 0. Log session status
                self.logger.info(f"Current cycle checking config...")
                asyncio.create_task(update_session_activity(self.user_id, self.phone))
                
                # HUMAN-LIKE BEHAVIOR: First-run staggered start 
                # (Prevents multiple accounts from hitting Telegram API at once after a bot reboot)
                if self.first_run:
                    stagger_delay = random.uniform(30, 120)  # 30s to 2min
                    self.logger.info(f"⏳ First-run stagger: waiting {stagger_delay:.1f}s before starting...")
                    await self.update_status(f"Staggering ({int(stagger_delay)}s)")
                    await asyncio.sleep(stagger_delay)
                    self.first_run = False
                
                # 1. Check plan validity
                if not await self._cached_is_plan_active():
                    self.logger.info(f"Plan expired or inactive, sleeping 5 min...")
                    await self.update_status("Inactive Plan")
                    await asyncio.sleep(300)
                    continue
                
                # 2. Check night mode
                if await is_night_mode():
                    wait_seconds = seconds_until_morning()
                    self.logger.info(f"Auto-Night mode, sleeping {format_time_remaining(wait_seconds)}...")
                    await self.update_status("Night Mode")
                    await asyncio.sleep(min(wait_seconds, 3600))
                    continue
                
                # 3. Get groups and messages
                all_raw_groups = await get_user_groups(self.user_id, enabled_only=True)
                if not all_raw_groups:
                    await self.update_status("Sleeping (No groups)")
                    self.logger.debug(f"No groups yet, waiting...")
                    await asyncio.sleep(300)
                    continue
                
                # DISTRIBUTED LOAD BALANCING
                # Get all active sessions for this user
                all_sessions = await get_all_user_sessions(self.user_id)
                all_sessions.sort(key=lambda s: s["phone"]) # Stable sort
                session_phones = [s["phone"] for s in all_sessions]
                num_accounts = len(session_phones)
                
                # STABLE SORT groups
                all_raw_groups.sort(key=lambda x: x.get('chat_id', 0))
                
                # Assign groups to THIS account based on index (Modulo assignment)
                if num_accounts > 1:
                    try:
                        my_idx = session_phones.index(self.phone)
                        groups = [g for i, g in enumerate(all_raw_groups) if i % num_accounts == my_idx]
                        self.logger.info(f"⚖️ Balancing: Account {my_idx+1}/{num_accounts} taking {len(groups)}/{len(all_raw_groups)} groups.")
                    except ValueError:
                        groups = all_raw_groups # Fallback
                else:
                    groups = all_raw_groups

                if not groups:
                    await self.update_status("Sleeping (No assigned groups)")
                    await asyncio.sleep(300)
                    continue

                all_messages = await self.get_all_saved_messages()
                if not all_messages:
                    await self.update_status("Sleeping (No ads)")
                    self.logger.debug(f"No messages yet, waiting...")
                    await asyncio.sleep(300)
                    continue
                
                # STABLE SORT messages
                all_messages.sort(key=lambda x: x.id)
                
                # 4. Build proper smart rotation pairs
                config = await self._get_cached_config()
                shuffle_mode = config.get("shuffle_mode", False)
                copy_mode = config.get("copy_mode", False)
                send_mode = config.get("send_mode", "sequential")
                
                pairs = []
                if send_mode == "sequential":
                    # Ad 1 to all groups, then Ad 2 to all groups
                    for msg in all_messages:
                        for group in groups:
                            pairs.append((msg, group))
                elif send_mode == "rotate":
                    # Ad 1 to Group 1, Ad 2 to Group 2... Only 1 ad per group
                    for j, group in enumerate(groups):
                        msg = all_messages[j % len(all_messages)]
                        pairs.append((msg, group))
                elif send_mode == "random":
                    # Random Ad to each group
                    for group in groups:
                        msg = random.choice(all_messages)
                        pairs.append((msg, group))
                else:
                    # Fallback
                    for msg in all_messages:
                        for group in groups:
                            pairs.append((msg, group))
                
                if shuffle_mode:
                    seed = f"{self.user_id}_{datetime.utcnow().strftime('%Y%m%d')}"
                    random.Random(seed).shuffle(pairs)
                
                # 5. Get current step
                current_session = await get_session(self.user_id, self.phone)
                current_step = current_session.get("current_msg_index", 0)
                
                if current_step >= len(pairs) or current_step < 0:
                    # CYCLE COMPLETE
                    user_interval_minutes = config.get("interval_min", DEFAULT_INTERVAL_MINUTES)
                    
                    # Apply random variance: subtract 0-5 minutes
                    variance_mins = random.randint(0, 5)
                    actual_interval = max(user_interval_minutes - variance_mins, MIN_INTERVAL_MINUTES - 5)
                    
                    self.logger.info(f"🔄 Loop complete! Set: {user_interval_minutes}m | Actual: {actual_interval}m (-{variance_mins}m variance)")
                    
                    cycle_wait_seconds = actual_interval * 60
                    elapsed = 0
                    night_interrupted = False
                    while elapsed < cycle_wait_seconds and self.running:
                        if await is_night_mode():
                            # Break inner loop so outer loop can handle night mode cleanly
                            night_interrupted = True
                            break
                        
                        rem_min = int((cycle_wait_seconds - elapsed) / 60)
                        await self.update_status(f"Next check in {rem_min}m")
                        
                        sleep_chunk = min(60, cycle_wait_seconds - elapsed)
                        await asyncio.sleep(sleep_chunk)
                        elapsed += sleep_chunk
                    
                    if night_interrupted:
                        # Night mode kicked in mid-wait — go back to outer loop to handle it
                        continue
                    
                    self.logger.info(f"▶️ Cycle interval complete! Restarting...")
                    current_step = 0
                    await update_current_msg_index(self.user_id, self.phone, 0)
                    continue # Re-fetch for new cycle
                
                # 6. Get the pair to send
                msg, group = pairs[current_step]
                total_steps = len(pairs)
                
                chat_title = group.get('chat_title', 'Unknown')
                chat_id = group.get('chat_id')

                # DOUBLE-SEND PROTECTION
                try:
                    from db.database import get_database
                    db = get_database()
                    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
                    recent_send = await db.send_logs.find_one({
                        "user_id": self.user_id,
                        "phone": self.phone,
                        "chat_id": chat_id,
                        "saved_msg_id": msg.id,
                        "sent_at": {"$gte": one_hour_ago},
                        "status": "success"
                    })
                    if recent_send:
                        self.logger.warning(f"🛡 Anti-Duplicate: Msg {msg.id} already sent to {chat_title} recently. Skipping.")
                        current_step += 1
                        await update_current_msg_index(self.user_id, self.phone, current_step)
                        continue
                except Exception as e:
                    self.logger.error(f"Error checking recent sends: {e}")

                self.logger.info(f"📤 (Step {current_step + 1}/{total_steps}) Forwarding msg {msg.id} to {chat_title}...")
                await self.update_status(f"Sending to {chat_title}")

                # 7. Send the single message
                flood_triggered, flood_wait = await self.forward_single_message(msg, group, copy_mode=copy_mode)
                
                if not flood_triggered:
                    self.message_counter += 1

                if flood_triggered:
                    self.logger.warning(f"⚠️ Flood detected, sleeping {flood_wait}s...")
                    await asyncio.sleep(flood_wait)
                    continue 
                
                # 8. Increment and save state!
                current_step += 1
                await update_current_msg_index(self.user_id, self.phone, current_step)
                
                # 9. Adaptive Interval Delay between groups!
                if current_step < len(pairs):
                    # Always use group gap between steps within a cycle.
                    # For sequential mode: also add a larger batch gap when
                    # all groups have been visited for the current message.
                    is_sequential = (send_mode == "sequential")
                    is_msg_boundary = is_sequential and len(groups) > 0 and (current_step % len(groups) == 0)

                    if is_msg_boundary:
                        base_gap = self.adaptive_msg_gap.get_gap()
                        gap_type = "ADAPTIVE_MSG_GAP"
                    else:
                        base_gap = self.adaptive_group_gap.get_gap()
                        gap_type = "ADAPTIVE_GROUP_GAP"
                        # Divide gap across parallel accounts so total rate stays constant
                        if num_accounts > 1:
                            base_gap = max(30, base_gap // num_accounts)

                    wait_time = random.randint(int(base_gap * 0.9), int(base_gap * 1.1))
                    self.logger.info(f"⏳ Waiting {wait_time}s ({gap_type}) before next step...")

                    elapsed = 0
                    night_gap_interrupted = False
                    while elapsed < wait_time and self.running:
                        if await is_night_mode():
                            night_gap_interrupted = True
                            break

                        rem_sec = wait_time - elapsed
                        status_msg = f"Next in {rem_sec}s" if rem_sec < 60 else f"Next in {int(rem_sec/60)}m"
                        await self.update_status(status_msg)

                        sleep_chunk = min(30, wait_time - elapsed)
                        await asyncio.sleep(sleep_chunk)
                        elapsed += sleep_chunk

                    if night_gap_interrupted:
                        # Night mode hit mid-gap — save step and let outer loop handle it
                        continue
                else:
                    self.logger.info(f"✅ Last step in cycle forwarded")
                
                # 10. Human-like Long Break (Every 50 messages)
                if self.message_counter > 0 and self.message_counter % 50 == 0:
                    break_time = random.randint(600, 1200) 
                    self.logger.info(f"😴 Taking long break ({int(break_time/60)}m) after {self.message_counter} sends...")
                    
                    elapsed = 0
                    while elapsed < break_time and self.running:
                        await self.update_status(f"Human Break ({int((break_time-elapsed)/60)}m)")
                        sleep_chunk = min(60, break_time - elapsed)
                        await asyncio.sleep(sleep_chunk)
                        elapsed += sleep_chunk

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Loop error: {e} - retrying in 60s...")
                await self.update_status("Error (Retrying)")
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
            # HUMAN-LIKE BEHAVIOR: Typing indicator
            # Randomized duration (3-8s) and 10% chance to skip typing completely
            if random.random() > 0.1:
                typing_duration = random.uniform(3, 8)
                async with self.client.action(chat_id, 'typing'):
                    await asyncio.sleep(typing_duration)
            
            if copy_mode:
                await self.client.send_message(
                    entity=chat_id,
                    message=message.text or "",
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
            
            self.logger.info(f"{log_action} message {message.id} to {chat_title}")
            self.adaptive_group_gap.on_success()
            self.adaptive_msg_gap.on_success()
            self.error_streak = 0
            
            # Log in background to not block the main sender loop
            asyncio.create_task(log_send(
                user_id=self.user_id,
                chat_id=chat_id,
                saved_msg_id=message.id,
                status="success",
                phone=self.phone
            ))
            return (False, 0)
            
        except FloodWaitError as e:
            self.logger.warning(f"FloodWait: {e.seconds}s on {chat_title}")
            self.adaptive_group_gap.on_flood(e.seconds)
            self.adaptive_msg_gap.on_flood(e.seconds)
            asyncio.create_task(log_send(self.user_id, chat_id, message.id, "flood_wait", f"FloodWait {e.seconds}s", phone=self.phone))
            return (True, int(e.seconds * 1.1) + 5)
            
        except PeerFloodError:
            self.logger.error(f"PeerFlood error on {chat_title}")
            asyncio.create_task(log_send(self.user_id, chat_id, message.id, "peer_flood", "PeerFlood", phone=self.phone))
            # PeerFlood usually means the account is restricted for this specific group/action
            # We don't want to stop the whole loop, just wait a bit and maybe skip this group next time
            return (True, 300) # 5 min cooling
            
        except (ChannelInvalidError, UsernameNotOccupiedError, UsernameInvalidError, InviteHashExpiredError) as e:
            self.logger.warning(f"❌ Removing invalid/expired group {chat_title}: {type(e).__name__}")
            asyncio.create_task(remove_group(self.user_id, chat_id))
            asyncio.create_task(log_send(self.user_id, chat_id, message.id, "removed", f"Invalid/Expired: {type(e).__name__}", phone=self.phone))
            return (False, 0)

        except (ChatWriteForbiddenError, ChannelPrivateError, ChatAdminRequiredError, UserBannedInChannelError) as e:
            reason = type(e).__name__
            self.logger.warning(f"⚠️ Pausing restricted group {chat_title}: {reason}")
            asyncio.create_task(toggle_group(self.user_id, chat_id, enabled=False, reason=reason))
            asyncio.create_task(log_send(self.user_id, chat_id, message.id, "auto_paused", f"Auto-Paused: {reason}", phone=self.phone))
            return (False, 0)
            
        except InputUserDeactivatedError:
            self.logger.error(f"User account deactivated!")
            asyncio.create_task(log_send(self.user_id, chat_id, message.id, "failed", "UserDeactivated", phone=self.phone))
            self.running = False
            return (False, 0)
            
        except RPCError as e:
            self.error_streak += 1
            error_msg = str(e).upper()
            
            # Smart RPC categorization
            if any(x in error_msg for x in ["CHAT_ADMIN_REQUIRED", "CHAT_WRITE_FORBIDDEN", "USER_BANNED_IN_CHANNEL"]):
                self.logger.warning(f"⚠️ Auto-pausing group {chat_title} due to RPC error: {e}")
                asyncio.create_task(toggle_group(self.user_id, chat_id, enabled=False, reason=f"RPC Error: {error_msg}"))
                asyncio.create_task(log_send(self.user_id, chat_id, message.id, "auto_paused", f"RPC: {error_msg}", phone=self.phone))
            elif any(x in error_msg for x in ["CHANNEL_INVALID", "USERNAME_NOT_OCCUPIED", "USERNAME_INVALID", "INVITE_HASH_EXPIRED"]):
                self.logger.warning(f"❌ Removing group {chat_title} due to fatal RPC error: {e}")
                asyncio.create_task(remove_group(self.user_id, chat_id))
                asyncio.create_task(log_send(self.user_id, chat_id, message.id, "removed", f"Fatal RPC: {error_msg}", phone=self.phone))
            else:
                self.logger.error(f"RPC Error forwarding to {chat_title}: {e}")
                asyncio.create_task(log_send(self.user_id, chat_id, message.id, "failed", str(e), phone=self.phone))
            return (False, 0)
            
        except Exception as e:
            self.error_streak += 1
            self.logger.error(f"Error forwarding to {chat_title}: {e}")
            asyncio.create_task(log_send(self.user_id, chat_id, message.id, "failed", str(e), phone=self.phone))
            return (False, 0)

    async def _connection_watchdog(self):
        """Background heartbeat with smart authorization check."""
        while self.running:
            try:
                await asyncio.sleep(600) # Every 10 minutes
                if self.client and self.client.is_connected():
                    # 1. Network Ping
                    await self.client.get_me()
                    
                    # 2. Authorization Check (Prevents ghost runs)
                    if not await self.client.is_user_authorized():
                        self.logger.error("Session revoked or unauthorized. Stopping sender.")
                        self.running = False
                        await self.update_status("🔴 Session Revoked")
                        return

                    self.last_heartbeat = datetime.utcnow()
                elif self.running:
                    self.logger.warning("Watchdog detected disconnected client. Reconnecting...")
                    await self.client.connect()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Watchdog heartbeat error: {e}")
