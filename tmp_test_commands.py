import asyncio
from unittest.mock import MagicMock, patch
from worker.commands import handle_status, handle_addplan
from datetime import datetime

# Mocking dependencies
async def mock_get_session(user_id, phone=None):
    return {"phone": "1234567890"}

async def mock_get_plan(user_id):
    return {"plan_type": "trial", "status": "active", "expires_at": datetime(2027, 1, 1)}

async def mock_get_user_config(user_id):
    return {"interval_min": 10, "send_mode": "sequential"}

async def mock_get_user_groups(user_id):
    return [{"chat_id": 1, "chat_title": "Test Group", "enabled": True}]

async def mock_reply_to_command(client, message, text):
    print(f"REPLY SENT:\n{text}")

async def test_worker_status_owner():
    print("Testing .status as owner for another user...")
    client = MagicMock()
    message = MagicMock()
    
    with patch("worker.commands.get_session", mock_get_session), \
         patch("worker.commands.get_plan", mock_get_plan), \
         patch("worker.commands.get_user_config", mock_get_user_config), \
         patch("worker.commands.get_user_groups", mock_get_user_groups), \
         patch("worker.commands.reply_to_command", mock_reply_to_command), \
         patch("core.config.OWNER_ID", 111):
        
        await handle_status(client, 111, message, ".status 222")

async def test_addplan_owner():
    print("\nTesting .addplan as owner...")
    client = MagicMock()
    message = MagicMock()
    
    with patch("worker.commands.reply_to_command", mock_reply_to_command), \
         patch("models.plan.activate_plan", MagicMock(return_value=asyncio.Future())), \
         patch("models.plan.extend_plan", MagicMock(return_value=asyncio.Future())), \
         patch("core.config.OWNER_ID", 111):
        
        # We need to mock activate_plan and extend_plan more properly if they were awaited
        # But for simple check of logic flow:
        await handle_addplan(client, 111, message, ".addplan 222 week")

if __name__ == "__main__":
    asyncio.run(test_worker_status_owner())
    asyncio.run(test_addplan_owner())
