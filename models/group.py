"""
Group model — CRUD for the groups collection.
"""

from datetime import datetime
from typing import Optional, List

from core.database import get_database
from core.config import MAX_GROUPS_PER_USER


async def add_group(
    user_id: int,
    chat_id: int,
    chat_title: str,
    account_phone: str = None,
) -> dict:
    """Add or update a group linked to a specific account phone."""
    db = get_database()
    now = datetime.utcnow()

    result = await db.groups.find_one_and_update(
        {"user_id": user_id, "chat_id": chat_id},
        {
            "$set": {
                "chat_title": chat_title,
                "enabled": True,
                "updated_at": now,
                "account_phone": account_phone,
            },
            "$setOnInsert": {
                "user_id": user_id,
                "chat_id": chat_id,
                "created_at": now,
            },
        },
        upsert=True,
        return_document=True,
    )
    return result


async def get_user_groups(
    user_id: int,
    enabled_only: bool = False,
    phone: str = None,
) -> List[dict]:
    """Get all groups for user (optionally filtered)."""
    db = get_database()
    query: dict = {"user_id": user_id}
    if enabled_only:
        query["enabled"] = True
    if phone:
        query["account_phone"] = phone
    cursor = db.groups.find(query)
    return await cursor.to_list(length=1000)


async def remove_group(user_id: int, chat_id: int):
    """Remove a group."""
    db = get_database()
    await db.groups.delete_one({"user_id": user_id, "chat_id": chat_id})


async def toggle_group(
    user_id: int,
    chat_id: int,
    enabled: bool,
    reason: str = None,
):
    """Enable or disable a group."""
    db = get_database()
    update: dict = {
        "enabled": enabled,
        "updated_at": datetime.utcnow(),
    }
    if reason:
        update["pause_reason"] = reason
    elif enabled:
        update["pause_reason"] = None

    await db.groups.update_one(
        {"user_id": user_id, "chat_id": chat_id},
        {"$set": update},
    )


async def get_group_count(user_id: int) -> int:
    """Get count of user's groups."""
    db = get_database()
    return await db.groups.count_documents({"user_id": user_id})
