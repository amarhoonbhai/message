"""
Failure Analysis Script.
Groups send_logs failures by error message to identify root causes.
"""

import asyncio
from datetime import datetime, timedelta
from db.database import get_database

async def analyze_failures():
    db = get_database()
    since = datetime.utcnow() - timedelta(hours=24)
    
    pipeline = [
        {"$match": {"sent_at": {"$gte": since}, "status": "failed"}},
        {"$group": {"_id": "$error", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    
    results = await db.send_logs.aggregate(pipeline).to_list(length=100)
    
    print("\n" + "="*60)
    print(f"FAILURE BREAKDOWN (LAST 24H)")
    print("="*60)
    
    if not results:
        print("No failures found in the last 24 hours.")
    else:
        for r in results:
            error = r['_id'] or "Unknown Error"
            count = r['count']
            print(f"[{count:>3}] {error}")
    print("="*60 + "\n")

if __name__ == "__main__":
    asyncio.run(analyze_failures())
