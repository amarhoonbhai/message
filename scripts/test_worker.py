"""
Diagnostic script to test if the Worker's event handler is correctly catching commands.
Run this script to see if your account is correctly triggering the dot commands.
"""

import asyncio
import logging
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from db.models import get_session
from worker.commands import process_command

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_events(user_id: int):
    # Load session
    session_data = await get_session(user_id)
    if not session_data:
        print(f"❌ No session found for User ID {user_id}")
        return
        
    session_string = session_data.get("session_string")
    api_id = session_data.get("api_id")
    api_hash = session_data.get("api_hash")
    
    print(f"🔄 Connecting to account for User {user_id}...")
    
    client = TelegramClient(
        StringSession(session_string), 
        api_id, 
        api_hash
    )
    
    await client.connect()
    
    if not await client.is_user_authorized():
        print("❌ Session is not authorized!")
        return
        
    me = await client.get_me()
    print(f"✅ Logged in as: {me.first_name} (@{me.username})")
    print("--------------------------------------------------")
    print("🔍 LISTENING FOR COMMANDS...")
    print("Go to ANY chat on your Telegram app (Phone/Desktop) and send: .help")
    print("Watch this terminal for logs.")
    print("--------------------------------------------------")
    
    @client.on(events.NewMessage(from_users='me'))
    async def handler(event):
        try:
            print(f"📩 Event Received! Text: '{event.message.text}' | Chat ID: {event.chat_id}")
            if event.message.text and event.message.text.strip().startswith("."):
                print(f"🚀 Processing command: {event.message.text.split()[0]}")
                # Pass directly to the real command processor
                await process_command(client, user_id, event.message)
                print("✅ Command processed.")
        except Exception as e:
            print(f"❌ Error in handler: {e}")

    print("Worker event test is running. Press Ctrl+C to stop.")
    await client.run_until_disconnected()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("user_id", type=int, help="Telegram User ID to test")
    args = parser.parse_args()
    
    try:
        asyncio.run(test_events(args.user_id))
    except KeyboardInterrupt:
        print("\nStopping test...")
