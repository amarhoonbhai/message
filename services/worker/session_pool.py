"""
Telethon Session Pool — maintains a cache of connected TelegramClient instances.

Avoids reconnecting for every job by caching authenticated clients with LRU
eviction and idle-timeout cleanup.
"""

import asyncio
import logging
import time
from typing import Dict, Optional, Tuple
from collections import OrderedDict

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import (
    AuthKeyUnregisteredError,
    UserDeactivatedBanError,
)

from core.config import SESSION_POOL_MAX_SIZE, SESSION_POOL_IDLE_TTL
from models.session import get_session, mark_session_disabled

logger = logging.getLogger(__name__)


class _PoolEntry:
    """Wraps a TelegramClient with metadata for pool management."""
    __slots__ = ("client", "user_id", "phone", "last_used", "lock")

    def __init__(self, client: TelegramClient, user_id: int, phone: str):
        self.client = client
        self.user_id = user_id
        self.phone = phone
        self.last_used = time.monotonic()
        self.lock = asyncio.Lock()  # Prevents concurrent sends on same client

    def touch(self):
        self.last_used = time.monotonic()


class SessionPool:
    """
    Thread-safe (asyncio-safe) pool of Telethon clients.

    Usage:
        pool = SessionPool()
        client = await pool.acquire(user_id, phone)
        # ... use client ...
        pool.release(user_id, phone)   # marks it idle
    """

    def __init__(
        self,
        max_size: int = SESSION_POOL_MAX_SIZE,
        idle_ttl: int = SESSION_POOL_IDLE_TTL,
    ):
        self.max_size = max_size
        self.idle_ttl = idle_ttl
        self._pool: OrderedDict[Tuple[int, str], _PoolEntry] = OrderedDict()
        self._global_lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the background cleanup loop."""
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info(f"Session pool started (max_size={self.max_size}, idle_ttl={self.idle_ttl}s)")

    async def stop(self):
        """Disconnect all clients and stop cleanup."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        async with self._global_lock:
            for key, entry in list(self._pool.items()):
                try:
                    await entry.client.disconnect()
                except Exception:
                    pass
            self._pool.clear()

        logger.info("Session pool stopped — all clients disconnected")

    async def acquire(self, user_id: int, phone: str) -> TelegramClient:
        """
        Get a connected, authenticated Telethon client for (user_id, phone).

        If a cached client exists and is connected → reuse it.
        If disconnected → reconnect.
        If not in pool → create, connect, cache.

        Raises RuntimeError if the session cannot be loaded or authenticated.
        """
        key = (user_id, phone)

        async with self._global_lock:
            entry = self._pool.get(key)

            if entry is not None:
                # Move to end (LRU)
                self._pool.move_to_end(key)
                entry.touch()

                if entry.client.is_connected():
                    return entry.client

                # Try reconnect
                try:
                    await entry.client.connect()
                    if await entry.client.is_user_authorized():
                        logger.info(f"Reconnected pooled client for {phone}")
                        return entry.client
                except Exception as e:
                    logger.warning(f"Reconnect failed for {phone}: {e}")

                # Reconnect failed — remove and rebuild
                try:
                    await entry.client.disconnect()
                except Exception:
                    pass
                del self._pool[key]

            # Build a new client
            client = await self._create_client(user_id, phone)

            # Evict oldest if at capacity
            if len(self._pool) >= self.max_size:
                oldest_key, oldest = self._pool.popitem(last=False)
                try:
                    await oldest.client.disconnect()
                    logger.info(f"Evicted idle client {oldest.phone} from pool")
                except Exception:
                    pass

            self._pool[key] = _PoolEntry(client, user_id, phone)
            return client

    def release(self, user_id: int, phone: str):
        """Mark a client as idle (touch its last_used timestamp)."""
        key = (user_id, phone)
        entry = self._pool.get(key)
        if entry:
            entry.touch()

    async def get_lock(self, user_id: int, phone: str) -> asyncio.Lock:
        """Get the per-client lock to prevent concurrent sends."""
        key = (user_id, phone)
        entry = self._pool.get(key)
        if entry:
            return entry.lock
        return asyncio.Lock()  # Fallback — shouldn't happen

    async def _create_client(self, user_id: int, phone: str) -> TelegramClient:
        """Load session from DB, create and connect a TelegramClient."""
        session_data = await get_session(user_id, phone)
        if not session_data:
            raise RuntimeError(f"No session found for {phone} (user {user_id})")

        session_string = session_data.get("session_string", "")
        api_id = session_data.get("api_id")
        api_hash = session_data.get("api_hash")

        if not session_string or len(session_string) < 50:
            raise RuntimeError(f"Invalid session string for {phone}")
        if not api_id or not api_hash:
            raise RuntimeError(f"Missing API credentials for {phone}")

        client = TelegramClient(
            StringSession(session_string),
            api_id,
            api_hash,
            device_model="Worker Pool Client",
            system_version="2.0",
            app_version="2.0",
        )

        try:
            await client.connect()
        except (ConnectionError, OSError) as e:
            raise RuntimeError(f"Connection failed for {phone}: {e}")

        if not await client.is_user_authorized():
            await client.disconnect()
            await mark_session_disabled(user_id, phone, "auth_failed_pool")
            raise RuntimeError(f"Session unauthorized for {phone}")

        logger.info(f"✅ New pooled client for {phone} (user {user_id})")
        return client

    async def _cleanup_loop(self):
        """Background task: disconnect clients idle for longer than TTL."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                now = time.monotonic()

                async with self._global_lock:
                    to_evict = []
                    for key, entry in self._pool.items():
                        if now - entry.last_used > self.idle_ttl:
                            to_evict.append(key)

                    for key in to_evict:
                        entry = self._pool.pop(key)
                        try:
                            await entry.client.disconnect()
                            logger.info(f"Evicted idle client {entry.phone}")
                        except Exception:
                            pass

                    if to_evict:
                        logger.info(f"Pool cleanup: evicted {len(to_evict)}, remaining {len(self._pool)}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Pool cleanup error: {e}")
