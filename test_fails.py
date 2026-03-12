import asyncio
import os
import sys

sys.path.append(os.getcwd())
from core.database import get_database

async def main():
    db = get_database()
    cursor = db.send_logs.aggregate([
        {"$match": {"status": "failed"}},
        {"$group": {"_id": "$error", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 5}
    ])
    async for d in cursor:
        print(f"{d['count']} occurrences: {d['_id']}")

asyncio.run(main())
