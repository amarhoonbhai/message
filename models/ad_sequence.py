"""
Ad sequence model — manages daily resetting sequence counters for ad messages.
"""

from datetime import datetime, timedelta
import logging
from core.database import get_database

logger = logging.getLogger(__name__)


async def get_next_ad_sequence_number(user_id: int, phone: str = None) -> int:
    """
    Get the next sequence number for an ad message.
    Resets to 1 after 24 hours (or each day).
    """
    db = get_database()
    now = datetime.utcnow()

    query = {"user_id": user_id}
    if phone:
        query["phone"] = phone

    doc = await db.ad_counters.find_one(query)

    if not doc:
        seq_num = 1
        await db.ad_counters.update_one(
            query,
            {
                "$set": {
                    "user_id": user_id,
                    "phone": phone,
                    "seq_num": seq_num,
                    "reset_at": now,
                    "updated_at": now,
                }
            },
            upsert=True,
        )
        return seq_num

    reset_at = doc.get("reset_at")
    is_24h_passed = not reset_at or (now - reset_at >= timedelta(hours=24))
    is_date_changed = not reset_at or (now.date() != reset_at.date())

    if is_24h_passed or is_date_changed:
        seq_num = 1
        await db.ad_counters.update_one(
            query,
            {
                "$set": {
                    "seq_num": seq_num,
                    "reset_at": now,
                    "updated_at": now,
                }
            },
        )
        return seq_num

    res = await db.ad_counters.find_one_and_update(
        query,
        {"$inc": {"seq_num": 1}, "$set": {"updated_at": now}},
        return_document=True,
    )
    return res.get("seq_num", 1) if res else 1
