import asyncio
from db.database import get_database
from datetime import datetime, timedelta

async def check_errors():
    db = get_database()
    now = datetime.utcnow()
    last_hour = now - timedelta(hours=1)
    
    # Check total logs in last hour
    total = await db.send_logs.count_documents({"sent_at": {"$gte": last_hour}})
    sent = await db.send_logs.count_documents({"sent_at": {"$gte": last_hour}, "status": "success"})
    failed = await db.send_logs.count_documents({"sent_at": {"$gte": last_hour}, "status": {"$ne": "success"}})
    
    print(f"--- Stats (Last 1 hour) ---")
    print(f"Total attempts: {total}")
    print(f"Success: {sent}")
    print(f"Failed: {failed}")
    
    if failed > 0:
        print("\n--- Recent Failures ---")
        cursor = db.send_logs.find({"sent_at": {"$gte": last_hour}, "status": {"$ne": "success"}}).sort("sent_at", -1).limit(10)
        async for log in cursor:
            print(f"[{log['sent_at'].strftime('%H:%M:%S')}] {log['phone']} -> {log['chat_id']}: {log.get('error', 'Unknown error')}")
            
    # Check sessions
    sessions = await db.sessions.find({"connected": True}).to_list(length=100)
    print(f"\n--- Active Sessions ({len(sessions)}) ---")
    for s in sessions:
        print(f"{s['phone']}: {s.get('worker_status', 'Unknown')} | Errors: {s.get('error_streak', 0)}")

if __name__ == "__main__":
    asyncio.run(check_errors())
