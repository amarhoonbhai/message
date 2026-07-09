"""
Standalone script to generate a Telethon StringSession manually.
Run this script locally to get a session string if the Login Bot is having issues.
"""

import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession

async def main():
    print("🚀 Telethon Session Generator")
    print("----------------------------")
    
    api_id = input("Enter your API ID: ").strip()
    api_hash = input("Enter your API Hash: ").strip()
    
    if not api_id or not api_hash:
        print("❌ API ID and Hash are required!")
        return
    
    try:
        api_id = int(api_id)
    except ValueError:
        print("❌ API ID must be a number!")
        return
        
    client = TelegramClient(
        StringSession(), 
        api_id, 
        api_hash,
        device_model="Spinify Ads Bot",
        system_version="1.0",
        app_version="1.0"
    )
    
    await client.start()
    
    session_string = client.session.save()
    
    print("\n✅ Session Generated Successfully!")
    print("--------------------------------")
    print(f"\nYour Session String:\n\n{session_string}\n")
    print("--------------------------------")
    print("⚠️  KEEP THIS STRING SECRET! Anyone with this string can access your account.")
    print("You can manually insert this into your MongoDB 'sessions' collection if needed.")
    
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
