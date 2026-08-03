"""
Centralized Redis caching service for plan status, user configs, and settings.
Includes JSON serialization for datetime objects and transparent fallbacks on error.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from core.redis_client import get_redis_pool

logger = logging.getLogger(__name__)

# Key prefixes
PLAN_CACHE_PREFIX = "cache:plan:"
CONFIG_CACHE_PREFIX = "cache:config:"
DEFAULT_TTL = 300  # 5 minutes


try:
    import orjson
    HAS_ORJSON = True
except ImportError:
    HAS_ORJSON = False

class CustomJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle datetime objects."""
    def default(self, obj):
        if isinstance(obj, datetime):
            return {"__datetime__": True, "val": obj.isoformat()}
        return super().default(obj)


def datetime_decoder(dct: dict) -> dict:
    """JSON decoder hook to restore datetime objects."""
    for key, value in dct.items():
        if isinstance(value, dict) and value.get("__datetime__"):
            try:
                dct[key] = datetime.fromisoformat(value["val"])
            except (ValueError, TypeError):
                pass
    return dct


def serialize_data(data: dict) -> str:
    """Serialize dictionary cleanly to JSON string."""
    clean = {k: v for k, v in data.items() if k != "_id"}
    if HAS_ORJSON:
        def default(obj):
            if isinstance(obj, datetime):
                return {"__datetime__": True, "val": obj.isoformat()}
            raise TypeError
        return orjson.dumps(clean, default=default).decode("utf-8")
    return json.dumps(clean, cls=CustomJSONEncoder)


# ── PLAN CACHING ─────────────────────────────────────────────────────────────

async def get_cached_plan(user_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve user's cached plan from Redis."""
    try:
        redis = await get_redis_pool()
        raw = await redis.get(f"{PLAN_CACHE_PREFIX}{user_id}")
        if raw:
            return json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw, object_hook=datetime_decoder)
    except Exception as e:
        logger.warning(f"Redis cache read error (get_cached_plan) for user {user_id}: {e}")
    return None


async def set_cached_plan(user_id: int, plan: Dict[str, Any], ttl: int = DEFAULT_TTL):
    """Store user's plan in Redis with TTL."""
    try:
        if not plan:
            return
        redis = await get_redis_pool()
        payload = serialize_data(plan)
        await redis.setex(f"{PLAN_CACHE_PREFIX}{user_id}", ttl, payload)
    except Exception as e:
        logger.warning(f"Redis cache write error (set_cached_plan) for user {user_id}: {e}")


async def invalidate_plan_cache(user_id: int):
    """Invalidate plan cache for a user."""
    try:
        redis = await get_redis_pool()
        await redis.delete(f"{PLAN_CACHE_PREFIX}{user_id}")
    except Exception as e:
        logger.warning(f"Redis cache invalidation error (invalidate_plan_cache) for user {user_id}: {e}")


# ── CONFIG CACHING ────────────────────────────────────────────────────────────

async def get_cached_user_config(user_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve user's cached config from Redis."""
    try:
        redis = await get_redis_pool()
        raw = await redis.get(f"{CONFIG_CACHE_PREFIX}{user_id}")
        if raw:
            return json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw, object_hook=datetime_decoder)
    except Exception as e:
        logger.warning(f"Redis cache read error (get_cached_user_config) for user {user_id}: {e}")
    return None


async def set_cached_user_config(user_id: int, config: Dict[str, Any], ttl: int = DEFAULT_TTL):
    """Store user's config in Redis with TTL."""
    try:
        if not config:
            return
        redis = await get_redis_pool()
        payload = serialize_data(config)
        await redis.setex(f"{CONFIG_CACHE_PREFIX}{user_id}", ttl, payload)
    except Exception as e:
        logger.warning(f"Redis cache write error (set_cached_user_config) for user {user_id}: {e}")


async def invalidate_user_config_cache(user_id: int):
    """Invalidate user config cache."""
    try:
        redis = await get_redis_pool()
        await redis.delete(f"{CONFIG_CACHE_PREFIX}{user_id}")
    except Exception as e:
        logger.warning(f"Redis cache invalidation error (invalidate_user_config_cache) for user {user_id}: {e}")


async def invalidate_all_user_cache(user_id: int):
    """Invalidate both plan and config cache for a user."""
    await invalidate_plan_cache(user_id)
    await invalidate_user_config_cache(user_id)
