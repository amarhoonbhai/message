"""
User model — CRUD operations for the users collection.

Preserves all existing functionality from db/models.py.
"""

from datetime import datetime, timedelta
from typing import Optional
import secrets

from core.database import get_database
from core.config import OWNER_ID # Actually, let me check if I can just remove them


async def create_user(user_id: int, referred_by: Optional[str] = None) -> dict:
    """Create a new user."""
    db = get_database()
    now = datetime.utcnow()

    doc = {
        "user_id": user_id,
        "created_at": now,
    }

    await db.users.update_one(
        {"user_id": user_id},
        {"$setOnInsert": doc},
        upsert=True,
    )

    return doc


async def get_user(user_id: int) -> Optional[dict]:
    """Get user by ID."""
    db = get_database()
    return await db.users.find_one({"user_id": user_id})




async def get_user_config(user_id: int) -> dict:
    """Get user settings (interval, shuffle, etc)."""
    db = get_database()
    doc = await db.user_configs.find_one({"user_id": user_id})
    if not doc:
        # Return defaults
        return {
            "user_id": user_id,
            "interval_min": 60,
            "shuffle_mode": False,
            "copy_mode": False,
            "send_mode": "sequential",
            "auto_reply_enabled": False,
            "auto_reply_text": "Hello! I am currently away. (Auto-reply)",
        }
    return doc


async def update_user_config(user_id: int, **kwargs):
    """Update specific user settings."""
    db = get_database()
    kwargs["updated_at"] = datetime.utcnow()
    await db.user_configs.update_one(
        {"user_id": user_id},
        {"$set": kwargs},
        upsert=True
    )
