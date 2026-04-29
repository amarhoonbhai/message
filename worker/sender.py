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
    GROUP_GAP_SECONDS, MESSAGE_GAP_SECONDS, DEFAULT_INTERVAL_MINUTES,
    MIN_INTERVAL_MINUTES, OWNER_ID, MAX_GROUPS_PER_USER
)
from db.models import (
    get_session, get_user_groups, get_user_config,
    update_last_saved_id, update_current_msg_index,
    is_plan_active, log_send as db_log_send, remove_group, toggle_group,
    update_session_activity, get_all_user_sessions,
    mark_session_auth_failed, mark_session_disabled, reset_session_auth_fails
)
from models.group import mark_group_failing, clear_group_fail, remove_stale_failing_groups
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
        """Apply adaptive multiplier and random jitter for human-like behavior."""
        jitter = random.uniform(0.8, 1.2)
        return int(self.base_gap * self.multiplier * jitter)

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
        self.last_status = ""  # Cache to prevent redundant DB writes
        self.adaptive_group_gap = AdaptiveDelayController(GROUP_GAP_SECONDS)
        self.adaptive_msg_gap = AdaptiveDelayController(MESSAGE_GAP_SECONDS)
        self.last_heartbeat = None
        self.error_streak = 0
        
        # V6: Smart dialog priming — only once on startup
        self._dialogs_primed = False
        # V6: Cycle dedup — prevent double-sends on crash/restart
        self._cycle_id = None
        self._sent_this_cycle = set()  # {(msg_id, chat_id)} already sent
        # V6: PeerFlood exponential backoff tracking
        self._peer_flood_count = 0
        # V6: Cycle timing metrics
        self._cycle_start_time = None
        self._last_cycle_duration = None
    
    async def update_status(self, status: str):
        """Update worker status in database with throttling for smoothness."""
        if status == self.last_status:
            return
            
        self.status = status
        self.last_status = status
        
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
        self.config_cache[cache_key] = (config, datetime.utcnow() + timedelta(seconds=60))
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
        self.config_cache[cache_key] = (active, datetime.utcnow() + timedelta(minutes=1))
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

        api_id = session_data.get("api_id")
        api_hash = session_data.get("api_hash")

        if not api_id or not api_hash:
            self.logger.error("API ID or Hash missing from session document — disabling")
            await mark_session_disabled(self.user_id, self.phone, "missing_api_credentials")
            return

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
        try:
            # ── PHASE 2a: REGISTER HANDLERS IMMEDIATELY ────────────────────
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

            self.logger.info("✅ Event handlers registered")

            # ── PHASE 2b: PRIME DIALOGS (once) ─────────────────────────────
            # Pre-load entity cache to prevent "Could not find entity" errors.
            # Only done once per session lifetime — not every cycle.
            try:
                self.logger.info("📂 Priming dialog cache...")
                async for _ in self.client.iter_dialogs(limit=300):
                    pass
                self._dialogs_primed = True
                self.logger.info("✅ Dialog cache primed")
            except Exception as e:
                self.logger.warning(f"Dialog priming failed (non-fatal): {e}")

            # ── PHASE 2c: START BACKGROUND TASKS & MAIN LOOP ───────────────
            watchdog_task = asyncio.create_task(self._connection_watchdog())
            
            # Run the main send loop
            await self.run_loop()
            
            # Cancel tasks when main loop ends
            watchdog_task.cancel()

        except Exception as e:
            self.logger.error(f"Error in session lifecycle: {e}")
        finally:
            if self.client:
                await self.client.disconnect()

    async def stop(self):
        """Stop the sender safely and cleanly close the connection."""
        self.running = False
        if self.client:
            try:
                # Disconnect politely
                if self.client.is_connected():
                    await self.client.disconnect()
            except Exception as e:
                self.logger.error(f"Error disconnecting client on stop: {e}")
    
    
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
        """Main sender loop — V6 Powerhouse."""
        while self.running:
            try:
                # 0. Fresh config + session activity
                self.config_cache.clear()
                self._cycle_start_time = datetime.utcnow()
                self._cycle_id = int(self._cycle_start_time.timestamp())
                self._sent_this_cycle.clear()
                self.logger.info(f"Starting new sending cycle (#{self._cycle_id})...")
                asyncio.create_task(update_session_activity(self.user_id, self.phone))
                
                # AUTO-CLEANUP: Remove groups failing for > 24h
                try:
                    removed_count = await remove_stale_failing_groups(self.user_id)
                    if removed_count > 0:
                        self.logger.info(f"🧹 Auto-cleanup: Removed {removed_count} stale failing group(s).")
                except Exception as e:
                    self.logger.warning(f"Maintenance tasks error: {e}")
                
                # AUTO-RECOVERY: If error streak is dangerously high
                if self.error_streak >= 20:
                    cooldown = min(self.error_streak * 30, 1800)
                    self.logger.warning(f"🛑 High error streak. Cooling down for {cooldown//60}m...")
                    await self.update_status(f"Cooldown ({cooldown//60}m)")
                    await asyncio.sleep(cooldown)
                    self.error_streak = 0
                    self.config_cache.clear()
                
                # 1. Check plan validity
                if not await self._cached_is_plan_active():
                    self.logger.info("Plan expired or inactive, sleeping 1 min...")
                    await self.update_status("Inactive Plan")
                    self.error_streak = 0
                    await asyncio.sleep(60)
                    continue
                
                # 2. Check night mode
                if await is_night_mode():
                    wait_seconds = seconds_until_morning()
                    self.logger.info(f"Auto-Night mode, sleeping {format_time_remaining(wait_seconds)}...")
                    await self.update_status("Night Mode")
                    await asyncio.sleep(min(wait_seconds, 3600))
                    continue
                
                # 3. Get groups — smart assignment
                all_raw_groups = await get_user_groups(self.user_id, enabled_only=True)
                
                my_groups = [g for g in all_raw_groups if g.get("account_phone") == self.phone]
                other_groups_count = len([g for g in all_raw_groups if g.get("account_phone") and g.get("account_phone") != self.phone])
                orphan_groups = [g for g in all_raw_groups if g.get("account_phone") is None]
                
                all_sessions = await get_all_user_sessions(self.user_id)
                all_sessions.sort(key=lambda s: s["phone"])
                session_phones = [s["phone"] for s in all_sessions]
                num_accounts = len(session_phones)
                
                groups = list(my_groups)
                if orphan_groups:
                    orphan_groups.sort(key=lambda x: x.get('chat_id', 0))
                    if num_accounts > 1:
                        try:
                            my_idx = session_phones.index(self.phone)
                            my_orphans = [g for i, g in enumerate(orphan_groups) if i % num_accounts == my_idx]
                            groups.extend(my_orphans)
                        except ValueError:
                            groups.extend(orphan_groups)
                    else:
                        groups.extend(orphan_groups)

                if other_groups_count > 0:
                    self.logger.info(f"🛡️ Skipping {other_groups_count} groups managed by other accounts.")

                if not groups:
                    await self.update_status("Sleeping (No assigned groups)")
                    await asyncio.sleep(60)
                    continue

                messages = await self.get_all_saved_messages()
                if not messages:
                    await self.update_status("Sleeping (No ads)")
                    await asyncio.sleep(60)
                    continue
                
                config = await self._get_cached_config()
                copy_mode = config.get("copy_mode", False)
                shuffle_mode = config.get("shuffle_mode", False)
                interval_minutes = config.get("interval_min", DEFAULT_INTERVAL_MINUTES)
                
                if shuffle_mode:
                    self.logger.info("🔀 Shuffle Mode: Randomized group order.")
                    random.shuffle(groups)

                # Re-prime dialogs only if initial priming failed
                if not self._dialogs_primed:
                    try:
                        async for _ in self.client.iter_dialogs(limit=300):
                            pass
                        self._dialogs_primed = True
                    except Exception:
                        pass

                # 4. Build tasks based on Send Mode
                send_mode = config.get("send_mode", "sequential")
                tasks = []
                
                if send_mode == "sequential":
                    for msg in messages:
                        for group in groups:
                            tasks.append((msg, group))
                elif send_mode == "rotate":
                    for i, group in enumerate(groups):
                        msg = messages[i % len(messages)]
                        tasks.append((msg, group))
                elif send_mode == "random":
                    for group in groups:
                        msg = random.choice(messages)
                        tasks.append((msg, group))
                
                self.logger.info(f"📋 {len(tasks)} tasks ({send_mode}) | {len(groups)} groups × {len(messages)} ads")

                success_groups = []
                failed_groups = []
                skipped_dedup = 0

                # 5. Process tasks with adaptive delays
                for i, (msg, group) in enumerate(tasks):
                    if not self.running: break
                    
                    # Night mode check every 10 tasks
                    if i % 10 == 0 and i > 0 and await is_night_mode():
                        self.logger.info("🌙 Night Mode detected mid-cycle. Pausing...")
                        break
                    
                    chat_id = group.get("chat_id")
                    chat_title = group.get('chat_title', 'Unknown')
                    
                    # V6: Cycle deduplication
                    dedup_key = (msg.id, chat_id)
                    if dedup_key in self._sent_this_cycle:
                        skipped_dedup += 1
                        continue
                    
                    self.logger.info(f"📤 [{i+1}/{len(tasks)}] → {chat_title}")
                    await self.update_status(f"Sending ({i+1}/{len(tasks)})")
                    
                    success, flood_triggered, flood_wait = await self.forward_single_message(msg, group, copy_mode=copy_mode)
                    
                    if success:
                        success_groups.append(chat_title)
                        self._sent_this_cycle.add(dedup_key)
                    else:
                        failed_groups.append(chat_title)
                    
                    if flood_triggered:
                        self.adaptive_group_gap.multiplier = min(self.adaptive_group_gap.multiplier * 1.1, 5.0)
                        await self.update_status(f"FloodWait ({flood_wait}s)")
                        await asyncio.sleep(flood_wait)
                        
                    # Apply gap between groups
                    if i < len(tasks) - 1:
                        is_last_group_for_msg = (send_mode == "sequential" and (i + 1) % len(groups) == 0)
                        if is_last_group_for_msg:
                            current_gap = self.adaptive_msg_gap.get_gap()
                            await self.update_status(f"Msg Gap ({current_gap}s)")
                        else:
                            current_gap = self.adaptive_group_gap.get_gap()
                        await asyncio.sleep(current_gap)
                
                # 6. Cycle complete — metrics and report
                actual_interval = max(interval_minutes, MIN_INTERVAL_MINUTES)
                cycle_duration = (datetime.utcnow() - self._cycle_start_time).total_seconds()
                self._last_cycle_duration = cycle_duration
                
                if success_groups or failed_groups:
                    from worker.utils import send_central_log, build_cycle_report
                    report = build_cycle_report(
                        self.phone, success_groups, failed_groups,
                        send_mode, actual_interval,
                        cycle_duration=cycle_duration, skipped=skipped_dedup
                    )
                    asyncio.create_task(send_central_log(report))
                
                self.logger.info(
                    f"✅ Cycle done in {cycle_duration:.0f}s | "
                    f"✓{len(success_groups)} ✗{len(failed_groups)} | "
                    f"Next in {actual_interval}m"
                )
                
                # Reset PeerFlood counter on successful cycle
                if len(success_groups) > 0:
                    self._peer_flood_count = 0
                
                # 7. Wait for next cycle
                wait_seconds = actual_interval * 60
                elapsed = 0
                while elapsed < wait_seconds and self.running:
                    if await is_night_mode():
                        break
                    rem_min = int((wait_seconds - elapsed) / 60)
                    await self.update_status(f"Next cycle in {rem_min}m")
                    sleep_chunk = min(60, wait_seconds - elapsed)
                    await asyncio.sleep(sleep_chunk)
                    elapsed += sleep_chunk

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.error_streak += 1
                self.logger.error(f"Loop error (streak {self.error_streak}): {e}")
                await self.update_status("Error (Retrying)")
                backoff = min(60 * self.error_streak, 600)
                await asyncio.sleep(backoff)
    
    async def get_all_saved_messages(self) -> list:
        """Fetch ALL Saved Messages (excluding command messages and service messages)."""
        try:
            messages = []
            async for msg in self.client.iter_messages('me', limit=100):
                # Skip command messages
                if msg.text and msg.text.strip().startswith("."):
                    continue
                # Skip MessageService (calls, pins, joins — cannot be forwarded)
                if hasattr(msg, 'action') and msg.action is not None:
                    continue
                # Skip messages with no content at all
                if not msg.text and not msg.media:
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
        Returns: (success: bool, flood_triggered: bool, flood_wait_seconds: int)
        """
        chat_id = group.get("chat_id")
        chat_title = group.get("chat_title", "Unknown")
        
        try:
            # ── STEP 1: Pre-validate entity (PREVENTS most errors) ──────────
            entity = None
            try:
                entity = await self.client.get_entity(chat_id)
            except (ChannelInvalidError, UsernameNotOccupiedError, UsernameInvalidError, InviteHashExpiredError) as e:
                # Group is dead — remove it immediately, don't even try to send
                self.logger.warning(f"❌ Pre-check failed: {chat_title} is invalid ({type(e).__name__}). Removing.")
                asyncio.create_task(remove_group(self.user_id, chat_id))
                asyncio.create_task(db_log_send(self.user_id, chat_id, message.id, "removed", f"Pre-check: {type(e).__name__}", phone=self.phone))
                return (False, False, 0)
            except (ChatWriteForbiddenError, ChannelPrivateError, ChatAdminRequiredError, UserBannedInChannelError) as e:
                # Group is restricted — mark as failing (will auto-remove after 24h)
                self.logger.warning(f"⚠️ Pre-check: {chat_title} restricted ({type(e).__name__}). Marking failing.")
                asyncio.create_task(mark_group_failing(self.user_id, chat_id, f"Pre-check: {type(e).__name__}"))
                asyncio.create_task(db_log_send(self.user_id, chat_id, message.id, "failing", f"Pre-check: {type(e).__name__}", phone=self.phone))
                return (False, False, 0)
            except ValueError as e:
                # Private group not in Telethon's entity cache — scan dialogs to find it
                self.logger.info(f"Entity not cached for {chat_id}, scanning dialogs...")
                try:
                    async for dialog in self.client.iter_dialogs(limit=300):
                        if dialog.id == chat_id:
                            entity = dialog.entity
                            break
                    if not entity:
                        raise ValueError(f"Not found in dialogs either")
                except Exception as dial_e:
                    self.logger.warning(f"Could not resolve entity for {chat_id}: {dial_e}")
                    asyncio.create_task(mark_group_failing(self.user_id, chat_id, f"Entity error: {dial_e}"))
                    asyncio.create_task(db_log_send(self.user_id, chat_id, message.id, "failing", f"Entity error: {dial_e}", phone=self.phone))
                    return (False, False, 0)

            except Exception as e:
                self.logger.warning(f"Could not resolve entity for {chat_id}: {e}")
                # Don't proceed if we can't even find the group
                asyncio.create_task(db_log_send(self.user_id, chat_id, message.id, "failed", f"Entity error: {e}", phone=self.phone))
                return (False, False, 0)
            
            # ── V6: Lightweight typing (30% chance, 1-2s) ────────────────
            if random.random() < 0.3:
                try:
                    async with self.client.action(entity, 'typing'):
                        await asyncio.sleep(random.uniform(1.0, 2.0))
                except Exception:
                    pass

            # ── STEP 6: Topic Awareness ──────────────────────────────────────
            topic_id = group.get("topic_id")

            # ── STEP 7: Send the message ─────────────────────────────────────
            if copy_mode or topic_id:
                # Safeguard: skip empty messages (no text and no media)
                if not message.text and not message.media:
                    self.logger.warning("Skipping empty message")
                    return (False, False, 0)

                # Use send_message as it reliably supports reply_to (for forums)
                await self.client.send_message(
                    entity=entity,
                    message=message.text or None,
                    file=message.media,
                    formatting_entities=message.entities if message.text else None,
                    reply_to=topic_id
                )
                log_action = f"Copied (Topic {topic_id})" if topic_id else "Copied"
            else:
                # Standard forward (shows "Forwarded from")
                await self.client.forward_messages(
                    entity=entity,
                    messages=message.id,
                    from_peer='me'
                )
                log_action = "Forwarded"
            
            self.logger.info(f"{log_action} message {message.id} to {chat_title}")
            self.adaptive_group_gap.on_success()
            self.adaptive_msg_gap.on_success()
            self.error_streak = 0
            
            # Log in background to not block the main sender loop
            asyncio.create_task(db_log_send(
                user_id=self.user_id,
                chat_id=chat_id,
                saved_msg_id=message.id,
                status="success",
                phone=self.phone
            ))
            
            # Clear failing status on success
            asyncio.create_task(clear_group_fail(self.user_id, chat_id))
            return (True, False, 0)
            
        except FloodWaitError as e:
            self.logger.warning(f"FloodWait: {e.seconds}s on {chat_title}")
            self.adaptive_group_gap.on_flood(e.seconds)
            self.adaptive_msg_gap.on_flood(e.seconds)
            asyncio.create_task(db_log_send(self.user_id, chat_id, message.id, "flood_wait", f"FloodWait {e.seconds}s", phone=self.phone))
            return (False, True, int(e.seconds * 1.1) + 5)
            
        except PeerFloodError:
            self.error_streak += 1
            self._peer_flood_count += 1
            # V6: Exponential backoff — 1h, 2h, 4h, 8h (max)
            cooldown_hours = min(2 ** (self._peer_flood_count - 1), 8)
            cooldown_secs = cooldown_hours * 3600
            self.logger.error(f"🚨 PeerFlood on {chat_title} — cooldown {cooldown_hours}h (flood #{self._peer_flood_count})")
            asyncio.create_task(db_log_send(self.user_id, chat_id, message.id, "peer_flood", "PeerFlood", phone=self.phone))
            from worker.utils import send_central_log, build_error_log
            asyncio.create_task(send_central_log(build_error_log(self.phone, chat_title, "🚨 PEER FLOOD", f"Account restricted — {cooldown_hours}h cooldown (#{self._peer_flood_count})")))
            await self.update_status(f"🚨 PeerFlood ({cooldown_hours}h cooldown)")
            return (False, True, cooldown_secs)
            
        except (ChannelInvalidError, UsernameNotOccupiedError, UsernameInvalidError, InviteHashExpiredError) as e:
            self.logger.warning(f"❌ Removing invalid/expired group {chat_title}: {type(e).__name__}")
            asyncio.create_task(remove_group(self.user_id, chat_id))
            asyncio.create_task(db_log_send(self.user_id, chat_id, message.id, "removed", f"Invalid/Expired: {type(e).__name__}", phone=self.phone))
            return (False, False, 0)

        except (ChatWriteForbiddenError, ChannelPrivateError, ChatAdminRequiredError, UserBannedInChannelError) as e:
            reason = type(e).__name__
            self.logger.warning(f"⚠️ Group {chat_title} failing: {reason}")
            asyncio.create_task(mark_group_failing(self.user_id, chat_id, reason))
            asyncio.create_task(db_log_send(self.user_id, chat_id, message.id, "failing", f"Failing: {reason}", phone=self.phone))
            return (False, False, 0)
            
        except InputUserDeactivatedError:
            self.logger.error(f"🛑 Account {self.phone} is deactivated by Telegram!")
            asyncio.create_task(mark_session_disabled(self.user_id, self.phone, reason="User Deactivated"))
            asyncio.create_task(db_log_send(self.user_id, chat_id, message.id, "failed", "UserDeactivated", phone=self.phone))
            # Log critical error to channel
            from worker.utils import send_central_log, build_error_log
            asyncio.create_task(send_central_log(build_error_log(self.phone, chat_title, "🛑 ACCOUNT DEACTIVATED", "Session permanently disabled")))
            self.running = False
            return (False, False, 0)
            
        except RPCError as e:
            self.error_streak += 1
            error_msg = str(e).upper()
            
            # Smart RPC categorization
            if any(x in error_msg for x in ["CHAT_ADMIN_REQUIRED", "CHAT_WRITE_FORBIDDEN", "USER_BANNED_IN_CHANNEL"]):
                self.logger.warning(f"⚠️ Group {chat_title} failing due to RPC: {e}")
                asyncio.create_task(mark_group_failing(self.user_id, chat_id, f"RPC: {error_msg[:40]}"))
                asyncio.create_task(db_log_send(self.user_id, chat_id, message.id, "failing", f"RPC: {error_msg}", phone=self.phone))
            elif any(x in error_msg for x in ["CHANNEL_INVALID", "USERNAME_NOT_OCCUPIED", "USERNAME_INVALID", "INVITE_HASH_EXPIRED"]):
                self.logger.warning(f"❌ Removing group {chat_title} due to fatal RPC error: {e}")
                asyncio.create_task(remove_group(self.user_id, chat_id))
                asyncio.create_task(db_log_send(self.user_id, chat_id, message.id, "removed", f"Fatal RPC: {error_msg}", phone=self.phone))
            elif "TOPIC_CLOSED" in error_msg:
                # Topic is closed but group itself may be valid — just skip, don't pause
                self.logger.warning(f"⚠️ Topic closed in {chat_title} — skipping (not pausing)")
                asyncio.create_task(db_log_send(self.user_id, chat_id, message.id, "skipped", "Topic closed", phone=self.phone))
            elif "MESSAGE_ID_INVALID" in error_msg or "OPERATION ON SUCH MESSAGE" in error_msg:
                # Stale message ID — skip silently, don't pause group
                self.logger.warning(f"⚠️ Message ID invalid for msg {message.id} — skipping")
                asyncio.create_task(db_log_send(self.user_id, chat_id, message.id, "skipped", "Message ID invalid", phone=self.phone))
            else:
                self.logger.error(f"RPC Error forwarding to {chat_title}: {e}")
                asyncio.create_task(db_log_send(self.user_id, chat_id, message.id, "failed", str(e), phone=self.phone))
            return (False, False, 0)
            
        except Exception as e:
            self.error_streak += 1
            self.logger.error(f"Error forwarding to {chat_title}: {e}")
            asyncio.create_task(db_log_send(self.user_id, chat_id, message.id, "failed", str(e), phone=self.phone))
            return (False, False, 0)

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
