
import asyncio
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.database import get_database
from db.models import toggle_group, remove_group, get_user_groups

async def verify():
    db = get_database()
    user_id = 123456789
    chat_id_pause = 111
    chat_id_delete = 222
    
    # 1. Setup test groups
    await db.groups.delete_many({"user_id": user_id})
    await db.groups.insert_one({
        "user_id": user_id,
        "chat_id": chat_id_pause,
        "chat_title": "Test Group Pause",
        "enabled": True
    })
    await db.groups.insert_one({
        "user_id": user_id,
        "chat_id": chat_id_delete,
        "chat_title": "Test Group Delete",
        "enabled": True
    })
    
    print("--- Initial State ---")
    groups = await get_user_groups(user_id)
    for g in groups:
        print(f"Group: {g['chat_title']} | Enabled: {g['enabled']}")
        
    # 2. Test Pausing
    print("\n--- Testing Pause (e.g. UserBannedInChannelError) ---")
    await toggle_group(user_id, chat_id_pause, enabled=False, reason="UserBannedInChannelError")
    
    group_pause = await db.groups.find_one({"user_id": user_id, "chat_id": chat_id_pause})
    print(f"Status: {group_pause['enabled']} | Reason: {group_pause.get('pause_reason')}")
    assert group_pause['enabled'] == False
    assert group_pause['pause_reason'] == "UserBannedInChannelError"
    
    # 3. Test Deletion
    print("\n--- Testing Delete (e.g. ChannelInvalidError) ---")
    await remove_group(user_id, chat_id_delete)
    
    group_delete = await db.groups.find_one({"user_id": user_id, "chat_id": chat_id_delete})
    print(f"Group found in DB: {group_delete is not None}")
    assert group_delete is None
    
    # 4. Cleanup
    await db.groups.delete_many({"user_id": user_id})
    print("\n✅ Verification Successful!")

if __name__ == "__main__":
    asyncio.run(verify())
