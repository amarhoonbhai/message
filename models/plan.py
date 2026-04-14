"""
Plans model — plan CRUD (paid).

Preserves consolidated functionality for premium plan management.
"""

from datetime import datetime, timedelta
from typing import Optional

from core.database import get_database
from core.config import (
    PLAN_DURATIONS, DEFAULT_INTERVAL_MINUTES, TIMEZONE
)

import pytz

IST = pytz.timezone(TIMEZONE)

async def get_expiring_plans() -> list:
    """Get active plans expiring within the next 24 hours."""
    db = get_database()
    now = datetime.utcnow()
    cursor = db.plans.find({
        "status": "active",
        "expires_at": {"$lte": now + timedelta(hours=24), "$gt": now},
        "expiration_warnings_sent": {"$lt": 3}
    })
    return await cursor.to_list(None)

async def get_plans_needing_expiry_reminder() -> list:
    """Get plans that are expired and need a reminder (every 24h, up to 7 days)."""
    db = get_database()
    now = datetime.utcnow()
    yesterday = now - timedelta(hours=24)
    seven_days_ago = now - timedelta(days=7)
    
    cursor = db.plans.find({
        "expires_at": {"$lte": now, "$gte": seven_days_ago},
        "$or": [
            {"notified_expired": {"$ne": True}},
            {"last_expiry_notification_at": {"$lte": yesterday}}
        ]
    })
    return await cursor.to_list(None)

async def update_plan_notification(user_id: int, updates: dict):
    """Update notification related fields."""
    db = get_database()
    await db.plans.update_one({"user_id": user_id}, {"$set": updates})



async def get_plan(user_id: int) -> Optional[dict]:
    """Get user's plan."""
    db = get_database()
    plan = await db.plans.find_one({"user_id": user_id})
    if plan:
        if plan.get("expires_at") and plan["expires_at"] < datetime.utcnow():
            plan["status"] = "expired"
            await db.plans.update_one(
                {"user_id": user_id},
                {"$set": {"status": "expired"}},
            )
    return plan


async def is_plan_active(user_id: int) -> bool:
    """Check if user has active plan."""
    plan = await get_plan(user_id)
    return plan is not None and plan.get("status") == "active"




async def extend_plan(user_id: int, days: int):
    """Extend user's plan by days."""
    db = get_database()
    plan = await db.plans.find_one({"user_id": user_id})
    now = datetime.utcnow()

    if plan:
        current_expiry = plan.get("expires_at", now)
        if current_expiry < now:
            current_expiry = now
        new_expiry = current_expiry + timedelta(days=days)

        update = {
            "expires_at": new_expiry,
            "status": "active",
            "plan_type": "premium",
            "notified_expired": False,
            "expiration_warnings_sent": 0
        }

        await db.plans.update_one({"user_id": user_id}, {"$set": update})
    else:
        await db.plans.insert_one({
            "user_id": user_id,
            "plan_type": "premium",
            "status": "active",
            "started_at": now,
            "expires_at": now + timedelta(days=days),
            "notified_expired": False,
            "expiration_warnings_sent": 0
        })


async def activate_plan(user_id: int, plan_type: str):
    """Activate a paid plan for user."""
    days = PLAN_DURATIONS.get(plan_type, 30)
    await extend_plan(user_id, days)


async def get_subscription_stats() -> dict:
    """Get overview stats for subscriptions."""
    db = get_database()
    now = datetime.utcnow()
    pipeline = [
        {"$facet": {
            "total_subscribed": [{"$count": "count"}],
            "active": [{"$match": {"status": "active", "expires_at": {"$gt": now}}}, {"$count": "count"}],
            "expired": [{"$match": {"$or": [{"status": "expired"}, {"expires_at": {"$lte": now}}]}}, {"$count": "count"}],
            "expiring_soon": [{"$match": {"status": "active", "expires_at": {"$gt": now, "$lte": now + timedelta(days=7)}}}, {"$count": "count"}],
            "lifetime": [{"$match": {"status": "active", "expires_at": {"$gt": now + timedelta(days=3000)}}}, {"$count": "count"}]
        }}
    ]
    cursor = db.plans.aggregate(pipeline)
    result = await cursor.to_list(1)
    if result:
        res = result[0]
        return {
            "total_subscribed": res["total_subscribed"][0]["count"] if res["total_subscribed"] else 0,
            "active": res["active"][0]["count"] if res["active"] else 0,
            "expired": res["expired"][0]["count"] if res["expired"] else 0,
            "expiring_soon": res["expiring_soon"][0]["count"] if res["expiring_soon"] else 0,
            "lifetime": res["lifetime"][0]["count"] if res["lifetime"] else 0,
        }
    return {"total_subscribed": 0, "active": 0, "expired": 0, "expiring_soon": 0, "lifetime": 0}

async def query_subscriptions(filter_type="all", search_query="", skip=0, limit=10):
    """Query subscriptions with pagination and lookup user info."""
    db = get_database()
    now = datetime.utcnow()
    
    match_query = {}
    if filter_type == "active":
        match_query = {"status": "active", "expires_at": {"$gt": now}}
    elif filter_type == "expired":
        match_query = {"$or": [{"status": "expired"}, {"expires_at": {"$lte": now}}]}
    elif filter_type == "expiring_soon":
        match_query = {"status": "active", "expires_at": {"$gt": now, "$lte": now + timedelta(days=7)}}
    elif filter_type == "lifetime":
        match_query = {"status": "active", "expires_at": {"$gt": now + timedelta(days=3000)}}

    pipeline = [{"$match": match_query}] if match_query else []

    pipeline.append({
        "$lookup": {
            "from": "users",
            "localField": "user_id",
            "foreignField": "user_id",
            "as": "user_info"
        }
    })
    
    pipeline.append({"$unwind": {"path": "$user_info", "preserveNullAndEmptyArrays": True}})

    if search_query:
        if search_query.isdigit():
            pipeline.append({"$match": {"user_id": int(search_query)}})
        else:
            regex = {"$regex": search_query, "$options": "i"}
            pipeline.append({"$match": {
                "$or": [
                    {"user_info.username": regex},
                    {"user_info.first_name": regex},
                    {"user_info.last_name": regex}
                ]
            }})

    # Count total
    count_pipeline = list(pipeline)
    count_pipeline.append({"$count": "total"})
    
    cursor = db.plans.aggregate(count_pipeline)
    count_res = await cursor.to_list(1)
    total = count_res[0]["total"] if count_res else 0

    pipeline.append({"$sort": {"expires_at": -1}})
    pipeline.append({"$skip": skip})
    pipeline.append({"$limit": limit})

    cursor = db.plans.aggregate(pipeline)
    results = await cursor.to_list(limit)

    return total, results

async def reduce_plan(user_id: int, days: int):
    """Reduce plan by days."""
    db = get_database()
    plan = await db.plans.find_one({"user_id": user_id})
    if plan and plan.get("expires_at"):
        new_expiry = plan["expires_at"] - timedelta(days=days)
        now = datetime.utcnow()
        if new_expiry <= now:
            await db.plans.update_one({"user_id": user_id}, {"$set": {"expires_at": now, "status": "expired"}})
        else:
            await db.plans.update_one({"user_id": user_id}, {"$set": {"expires_at": new_expiry}})

async def mark_plan_expired(user_id: int):
    """Mark a plan as expired immediately."""
    db = get_database()
    await db.plans.update_one(
        {"user_id": user_id}, 
        {"$set": {"status": "expired", "expires_at": datetime.utcnow()}}
    )

async def delete_plan(user_id: int):
    """Hard delete a plan."""
    db = get_database()
    await db.plans.delete_one({"user_id": user_id})
