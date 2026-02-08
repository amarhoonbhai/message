import asyncio
from datetime import datetime, timedelta
import sys
import os
from collections import Counter

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.database import get_database

async def analyze():
    db = get_database()
    since = datetime.utcnow() - timedelta(hours=24)
    
    print(f"--- Analysis Report (Last 24h) ---")
    print(f"Since: {since}")
    
    # Analyze by status
    status_pipeline = [
        {"$match": {"sent_at": {"$gte": since}}},
        {"$group": {"_id": "$status", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    
    status_results = await db.send_logs.aggregate(status_pipeline).to_list(length=None)
    print("\n--- Status Summary ---")
    for res in status_results:
        print(f"{res['_id']}: {res['count']}")

    # Analyze specifically failures
    failure_pipeline = [
        {"$match": {"sent_at": {"$gte": since}, "status": "failed"}},
        {"$group": {"_id": "$error", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    
    failures = await db.send_logs.aggregate(failure_pipeline).to_list(length=None)
    
    print("\n--- Failure Breakdown ---")
    if not failures:
        print("No failures found in the last 24h (check status summary for other states).")
    for fail in failures:
        error_msg = fail['_id'] or "Unknown/None"
        print(f"Count: {fail['count']} | Error: {error_msg}")

    # Analyze removed groups
    removed_pipeline = [
        {"$match": {"sent_at": {"$gte": since}, "status": "removed"}},
        {"$group": {"_id": "$error", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    removed_results = await db.send_logs.aggregate(removed_pipeline).to_list(length=None)
    print("\n--- Removed Groups Breakdown ---")
    for res in removed_results:
        print(f"Count: {res['count']} | Error: {res['_id']}")

    # Check for flood_wait and peer_flood specifically if they use those statuses
    other_pipeline = [
        {"$match": {"sent_at": {"$gte": since}, "status": {"$in": ["flood_wait", "peer_flood"]}}},
        {"$group": {"_id": "$status", "count": {"$sum": 1}}}
    ]
    other_results = await db.send_logs.aggregate(other_pipeline).to_list(length=None)
    if other_results:
        print("\n--- Flood/Peer Summary ---")
        for res in other_results:
            print(f"{res['_id']}: {res['count']}")

if __name__ == "__main__":
    asyncio.run(analyze())
