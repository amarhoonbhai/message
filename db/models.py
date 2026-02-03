"""
MongoDB document models and helper functions for CRUD operations.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import secrets
import pytz

from .database import get_database
from config import (
    TRIAL_DAYS, REFERRAL_BONUS_DAYS, REFERRALS_NEEDED,
    PLAN_DURATIONS, DEFAULT_INTERVAL_MINUTES, TIMEZONE
)

IST = pytz.timezone(TIMEZONE)


# ==================== USERS ====================

async def create_user(user_id: int, referred_by: Optional[str] = None) -> Dict[str, Any]:
    """Create a new user."""
    db = get_database()
    
    user_doc = {
        "user_id": user_id,
        "created_at": datetime.utcnow(),
        "referred_by": referred_by,
        "referrals_count": 0,
        "referral_code": secrets.token_urlsafe(8),
    }
    
    await db.users.update_one(
        {"user_id": user_id},
        {"$setOnInsert": user_doc},
        upsert=True
    )
    
    # If referred, increment referrer's count
    if referred_by:
        await db.users.update_one(
            {"referral_code": referred_by},
            {"$inc": {"referrals_count": 1}}
        )
        # Check if referrer earned bonus
        await check_referral_bonus(referred_by)
    
    return await get_user(user_id)


async def get_user(user_id: int) -> Optional[Dict[str, Any]]:
    """Get user by ID."""
    db = get_database()
    return await db.users.find_one({"user_id": user_id})


async def get_user_by_referral_code(code: str) -> Optional[Dict[str, Any]]:
    """Get user by referral code."""
    db = get_database()
    return await db.users.find_one({"referral_code": code})


async def check_referral_bonus(referral_code: str):
    """Check if referrer earned bonus and apply it."""
    db = get_database()
    referrer = await db.users.find_one({"referral_code": referral_code})
    
    if referrer and referrer.get("referrals_count", 0) >= REFERRALS_NEEDED:
        # Check if bonus not already applied
        if not referrer.get("referral_bonus_applied"):
            await extend_plan(referrer["user_id"], REFERRAL_BONUS_DAYS)
            await db.users.update_one(
                {"user_id": referrer["user_id"]},
                {"$set": {"referral_bonus_applied": True}}
            )


# ==================== SESSIONS ====================

async def create_session(
    user_id: int, 
    phone: str, 
    session_string: str,
    api_id: int = None,
    api_hash: str = None
) -> Dict[str, Any]:
    """Create or update user session with per-user API credentials."""
    db = get_database()
    
    session_doc = {
        "user_id": user_id,
        "phone": phone,
        "session_string": session_string,
        "api_id": api_id,
        "api_hash": api_hash,
        "connected": True,
        "connected_at": datetime.utcnow(),
    }
    
    await db.sessions.update_one(
        {"user_id": user_id},
        {"$set": session_doc},
        upsert=True
    )
    
    # Grant trial on first connection
    await grant_trial_if_new(user_id)
    
    return session_doc


async def get_session(user_id: int) -> Optional[Dict[str, Any]]:
    """Get session by user ID."""
    db = get_database()
    return await db.sessions.find_one({"user_id": user_id})


async def get_all_connected_sessions() -> List[Dict[str, Any]]:
    """Get all connected sessions for worker."""
    db = get_database()
    cursor = db.sessions.find({"connected": True})
    return await cursor.to_list(length=None)


async def disconnect_session(user_id: int):
    """Mark session as disconnected."""
    db = get_database()
    await db.sessions.update_one(
        {"user_id": user_id},
        {"$set": {"connected": False}}
    )


# ==================== CONFIG ====================

async def get_user_config(user_id: int) -> Dict[str, Any]:
    """Get user config, creating default if not exists."""
    db = get_database()
    
    config = await db.config.find_one({"user_id": user_id})
    
    if not config:
        config = {
            "user_id": user_id,
            "interval_min": DEFAULT_INTERVAL_MINUTES,
            "last_saved_id": 0,
            "updated_at": datetime.utcnow(),
        }
        await db.config.insert_one(config)
    
    return config


async def update_user_config(user_id: int, **kwargs) -> Dict[str, Any]:
    """Update user config."""
    db = get_database()
    
    kwargs["updated_at"] = datetime.utcnow()
    
    await db.config.update_one(
        {"user_id": user_id},
        {"$set": kwargs},
        upsert=True
    )
    
    return await get_user_config(user_id)


async def update_last_saved_id(user_id: int, last_saved_id: int):
    """Update last processed saved message ID."""
    db = get_database()
    await db.config.update_one(
        {"user_id": user_id},
        {"$set": {"last_saved_id": last_saved_id, "updated_at": datetime.utcnow()}},
        upsert=True
    )


async def update_current_msg_index(user_id: int, index: int):
    """Update current message index for continuous loop forwarding."""
    db = get_database()
    await db.config.update_one(
        {"user_id": user_id},
        {"$set": {"current_msg_index": index, "updated_at": datetime.utcnow()}},
        upsert=True
    )


# ==================== GROUPS ====================

async def add_group(user_id: int, chat_id: int, chat_title: str) -> bool:
    """Add a group for user. Returns False if at max limit."""
    db = get_database()
    
    # Check group count
    from config import MAX_GROUPS_PER_USER
    count = await db.groups.count_documents({"user_id": user_id})
    
    if count >= MAX_GROUPS_PER_USER:
        return False
    
    group_doc = {
        "user_id": user_id,
        "chat_id": chat_id,
        "chat_title": chat_title,
        "enabled": True,
        "added_at": datetime.utcnow(),
    }
    
    await db.groups.update_one(
        {"user_id": user_id, "chat_id": chat_id},
        {"$set": group_doc},
        upsert=True
    )
    
    return True


async def get_user_groups(user_id: int, enabled_only: bool = False) -> List[Dict[str, Any]]:
    """Get all groups for user."""
    db = get_database()
    
    query = {"user_id": user_id}
    if enabled_only:
        query["enabled"] = True
    
    cursor = db.groups.find(query)
    return await cursor.to_list(length=None)


async def remove_group(user_id: int, chat_id: int):
    """Remove a group."""
    db = get_database()
    await db.groups.delete_one({"user_id": user_id, "chat_id": chat_id})


async def toggle_group(user_id: int, chat_id: int, enabled: bool):
    """Enable or disable a group."""
    db = get_database()
    await db.groups.update_one(
        {"user_id": user_id, "chat_id": chat_id},
        {"$set": {"enabled": enabled}}
    )


async def get_group_count(user_id: int) -> int:
    """Get count of user's groups."""
    db = get_database()
    return await db.groups.count_documents({"user_id": user_id})


# ==================== PLANS ====================

async def grant_trial_if_new(user_id: int):
    """Grant trial if user doesn't have a plan."""
    db = get_database()
    
    existing = await db.plans.find_one({"user_id": user_id})
    
    if not existing:
        plan_doc = {
            "user_id": user_id,
            "plan_type": "trial",
            "expires_at": datetime.utcnow() + timedelta(days=TRIAL_DAYS),
            "status": "active",
            "created_at": datetime.utcnow(),
        }
        await db.plans.insert_one(plan_doc)


async def get_plan(user_id: int) -> Optional[Dict[str, Any]]:
    """Get user's plan."""
    db = get_database()
    plan = await db.plans.find_one({"user_id": user_id})
    
    if plan:
        # Check if expired
        if plan["expires_at"] < datetime.utcnow():
            await db.plans.update_one(
                {"user_id": user_id},
                {"$set": {"status": "expired"}}
            )
            plan["status"] = "expired"
    
    return plan


async def is_plan_active(user_id: int) -> bool:
    """Check if user has active plan."""
    plan = await get_plan(user_id)
    return plan is not None and plan.get("status") == "active" and plan["expires_at"] > datetime.utcnow()


async def is_trial_user(user_id: int) -> bool:
    """Check if user is on trial plan (not paid)."""
    plan = await get_plan(user_id)
    if not plan:
        return False
    return (
        plan.get("plan_type") == "trial" and 
        plan.get("status") == "active" and 
        plan["expires_at"] > datetime.utcnow()
    )


async def extend_plan(user_id: int, days: int):
    """Extend user's plan by days."""
    db = get_database()
    
    plan = await get_plan(user_id)
    
    if plan:
        # Extend from current expiry or now
        base_date = max(plan["expires_at"], datetime.utcnow())
        new_expiry = base_date + timedelta(days=days)
        
        await db.plans.update_one(
            {"user_id": user_id},
            {"$set": {"expires_at": new_expiry, "status": "active"}}
        )
    else:
        # Create new plan
        plan_doc = {
            "user_id": user_id,
            "plan_type": "paid",
            "expires_at": datetime.utcnow() + timedelta(days=days),
            "status": "active",
            "created_at": datetime.utcnow(),
        }
        await db.plans.insert_one(plan_doc)


async def activate_plan(user_id: int, plan_type: str):
    """Activate a paid plan for user."""
    days = PLAN_DURATIONS.get(plan_type, 7)
    await extend_plan(user_id, days)
    
    db = get_database()
    await db.plans.update_one(
        {"user_id": user_id},
        {"$set": {"plan_type": plan_type}}
    )


# ==================== REDEEM CODES ====================

async def generate_redeem_code(plan_type: str) -> str:
    """Generate a new redeem code."""
    db = get_database()
    
    code = secrets.token_urlsafe(12).upper()[:12]
    
    code_doc = {
        "code": code,
        "plan_type": plan_type,
        "duration_days": PLAN_DURATIONS.get(plan_type, 7),
        "created_at": datetime.utcnow(),
        "used_by": None,
        "used_at": None,
    }
    
    await db.redeem_codes.insert_one(code_doc)
    return code


async def redeem_code(user_id: int, code: str) -> tuple[bool, str]:
    """
    Redeem a code for user.
    Returns (success, message).
    """
    db = get_database()
    
    code_doc = await db.redeem_codes.find_one({"code": code.upper()})
    
    if not code_doc:
        return False, "❌ Invalid code."
    
    if code_doc.get("used_by"):
        return False, "❌ This code has already been used."
    
    # Apply plan
    await extend_plan(user_id, code_doc["duration_days"])
    
    # Mark code as used
    await db.redeem_codes.update_one(
        {"code": code.upper()},
        {"$set": {"used_by": user_id, "used_at": datetime.utcnow()}}
    )
    
    plan_type = code_doc["plan_type"]
    days = code_doc["duration_days"]
    
    return True, f"✅ Code redeemed! +{days} days ({plan_type}) added to your plan."


# ==================== SEND LOGS ====================

async def log_send(
    user_id: int,
    chat_id: int,
    saved_msg_id: int,
    status: str = "success",
    error: Optional[str] = None
):
    """Log a message send attempt."""
    db = get_database()
    
    log_doc = {
        "user_id": user_id,
        "chat_id": chat_id,
        "saved_msg_id": saved_msg_id,
        "sent_at": datetime.utcnow(),
        "status": status,
        "error": error,
    }
    
    await db.send_logs.insert_one(log_doc)


async def get_send_stats(hours: int = 24) -> Dict[str, int]:
    """Get send statistics for the last N hours."""
    db = get_database()
    
    since = datetime.utcnow() - timedelta(hours=hours)
    
    total = await db.send_logs.count_documents({"sent_at": {"$gte": since}})
    success = await db.send_logs.count_documents({"sent_at": {"$gte": since}, "status": "success"})
    failed = await db.send_logs.count_documents({"sent_at": {"$gte": since}, "status": "failed"})
    
    return {
        "total": total,
        "success": success,
        "failed": failed,
    }


# ==================== ADMIN STATS ====================

async def get_admin_stats() -> Dict[str, Any]:
    """Get overall statistics for admin panel."""
    db = get_database()
    
    total_users = await db.users.count_documents({})
    connected_sessions = await db.sessions.count_documents({"connected": True})
    
    # Plan stats
    now = datetime.utcnow()
    trial_active = await db.plans.count_documents({
        "plan_type": "trial",
        "status": "active",
        "expires_at": {"$gt": now}
    })
    paid_active = await db.plans.count_documents({
        "plan_type": {"$in": ["week", "month", "paid"]},
        "status": "active",
        "expires_at": {"$gt": now}
    })
    expired = await db.plans.count_documents({"status": "expired"})
    
    # Send stats
    send_stats = await get_send_stats(24)
    
    # Groups removed (from logs)
    groups_removed = await db.send_logs.count_documents({
        "sent_at": {"$gte": now - timedelta(hours=24)},
        "status": "removed"
    })
    
    return {
        "total_users": total_users,
        "connected_sessions": connected_sessions,
        "trial_active": trial_active,
        "paid_active": paid_active,
        "expired": expired,
        "sends_24h": send_stats["total"],
        "success_24h": send_stats["success"],
        "failed_24h": send_stats["failed"],
        "groups_removed_24h": groups_removed,
    }


async def get_all_users_for_broadcast(filter_type: str = "all") -> List[int]:
    """Get user IDs for broadcast."""
    db = get_database()
    now = datetime.utcnow()
    
    if filter_type == "all":
        cursor = db.users.find({}, {"user_id": 1})
    elif filter_type == "connected":
        cursor = db.sessions.find({"connected": True}, {"user_id": 1})
    elif filter_type == "trial":
        plan_cursor = db.plans.find({
            "plan_type": "trial",
            "status": "active",
            "expires_at": {"$gt": now}
        }, {"user_id": 1})
        return [p["user_id"] async for p in plan_cursor]
    elif filter_type == "paid":
        plan_cursor = db.plans.find({
            "plan_type": {"$in": ["week", "month", "paid"]},
            "status": "active",
            "expires_at": {"$gt": now}
        }, {"user_id": 1})
        return [p["user_id"] async for p in plan_cursor]
    else:
        cursor = db.users.find({}, {"user_id": 1})
    
    return [u["user_id"] async for u in cursor]
