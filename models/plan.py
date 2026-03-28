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
        }

        await db.plans.update_one({"user_id": user_id}, {"$set": update})
    else:
        await db.plans.insert_one({
            "user_id": user_id,
            "plan_type": "premium",
            "status": "active",
            "started_at": now,
            "expires_at": now + timedelta(days=days),
        })


async def activate_plan(user_id: int, plan_type: str):
    """Activate a paid plan for user."""
    days = PLAN_DURATIONS.get(plan_type, 30)
    await extend_plan(user_id, days)
