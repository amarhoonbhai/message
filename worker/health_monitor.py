"""
Health Monitor for Group Message Scheduler.
Provides a quick diagnostic summary of all active account sessions and their performance metrics.
"""

import asyncio
import logging
from datetime import datetime
from db.database import get_database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def get_health_summary():
    db = get_database()
    sessions = await db.sessions.find({"connected": True}).to_list(length=100)
    
    table_data = []
    headers = ["Phone", "Status", "Errors", "Last Active", "Health State"]
    
    now = datetime.utcnow()
    
    for s in sessions:
        phone = s.get("phone", "Unknown")
        status = s.get("worker_status", "Off")
        error_streak = s.get("error_streak", 0)
        last_active = s.get("status_updated_at", now)
        
        # Calculate health state
        if error_streak > 5:
            health = "🔴 CRITICAL"
        elif error_streak > 0:
            health = "🟡 UNSTABLE"
        elif (now - last_active).total_seconds() > 600:
            health = "⚪ STALE"
        else:
            health = "🟢 HEALTHY"
            
        last_active_str = last_active.strftime("%H:%M:%S")
        table_data.append([phone, status, error_streak, last_active_str, health])
        
    print("\n" + "="*80)
    print(f"BOT HEALTH MONITOR - {now.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print("="*80)
    
    if not table_data:
        print("No active sessions found.")
    else:
        # Simple manual table formatting for reliability without external deps
        row_format = "{:<15} {:<25} {:<10} {:<15} {:<15}"
        print(row_format.format(*headers))
        print("-" * 80)
        for row in table_data:
            print(row_format.format(*row))
    print("=" * 80 + "\n")

if __name__ == "__main__":
    asyncio.run(get_health_summary())
