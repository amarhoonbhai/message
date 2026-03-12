"""
User model — CRUD operations for the users collection.

Preserves all existing functionality from db/models.py.
"""

from datetime import datetime, timedelta
from typing import Optional
import secrets

from core.database import get_database
from core.config import TRIAL_DAYS, REFERRAL_BONUS_DAYS, REFERRALS_NEEDED


async def create_user(user_id: int, referred_by: Optional[str] = None) -> dict:
    """Create a new user with optional referral tracking."""
    db = get_database()
    now = datetime.utcnow()

    referral_code = secrets.token_hex(4)

    doc = {
        "user_id": user_id,
        "referral_code": referral_code,
        "referred_by": referred_by,
        "referral_count": 0,
        "created_at": now,
    }

    await db.users.update_one(
        {"user_id": user_id},
        {"$setOnInsert": doc},
        upsert=True,
    )

    if referred_by:
        await db.users.update_one(
            {"referral_code": referred_by},
            {"$inc": {"referral_count": 1}},
        )

    return doc


async def get_user(user_id: int) -> Optional[dict]:
    """Get user by ID."""
    db = get_database()
    return await db.users.find_one({"user_id": user_id})


async def get_user_by_referral_code(code: str) -> Optional[dict]:
    """Get user by referral code."""
    db = get_database()
    return await db.users.find_one({"referral_code": code})


async def check_referral_bonus(referral_code: str):
    """Check if referrer earned bonus and apply it."""
    db = get_database()
    referrer = await db.users.find_one({"referral_code": referral_code})
    if not referrer:
        return

    if referrer.get("referral_count", 0) >= REFERRALS_NEEDED:
        from models.plan import extend_plan
        await extend_plan(referrer["user_id"], REFERRAL_BONUS_DAYS, upgrade_to_paid=False)


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
