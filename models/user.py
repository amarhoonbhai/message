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

    # ── Level Up: 3-Day Trial Policy ──
    from models.plan import get_plan, extend_plan
    existing_plan = await get_plan(user_id)
    if not existing_plan:
        # Assign 3 days trial automatically
        await extend_plan(user_id, 3)
        # Note: we use extend_plan here which handles creation if missing.
        # We can also tag it as "trial" if needed, but the user asked for "trial plan".

    return doc


async def get_user(user_id: int) -> Optional[dict]:
    """Get user by ID."""
    db = get_database()
    return await db.users.find_one({"user_id": user_id})

async def update_user_profile(user_id: int, username: str = None, first_name: str = None, last_name: str = None):
    """Update user's profile information."""
    db = get_database()
    updates = {}
    if username is not None:
        updates["username"] = username
    if first_name is not None:
        updates["first_name"] = first_name
    if last_name is not None:
        updates["last_name"] = last_name
        
    if updates:
        # Also ensure last_active is updated
        updates["last_active"] = datetime.utcnow()
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": updates},
            upsert=True
        )




async def get_user_config(user_id: int) -> dict:
    """Get user settings (interval, shuffle, etc)."""
    from core.config import DEFAULT_INTERVAL_MINUTES
    db = get_database()
    doc = await db.config.find_one({"user_id": user_id})
    if not doc:
        # Return defaults
        return {
            "user_id": user_id,
            "interval_min": DEFAULT_INTERVAL_MINUTES,
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
    await db.config.update_one(
        {"user_id": user_id},
        {"$set": kwargs},
        upsert=True
    )
