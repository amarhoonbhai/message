"""
Command handler for processing dot commands from user's Saved Messages.
Commands are sent by user to their own Saved Messages and processed by Worker.
"""

import logging
import re
from telethon import TelegramClient
from telethon.errors import (
    ChannelPrivateError,
    ChannelInvalidError,
    UsernameNotOccupiedError,
    UsernameInvalidError,
    InviteHashInvalidError,
    InviteHashExpiredError,
)
from telethon.tl.types import InputPeerSelf

from config import MAX_GROUPS_PER_USER, MIN_INTERVAL_MINUTES
from db.models import (
    get_session, get_user_groups, add_group, remove_group,
    get_user_config, update_user_config, get_plan, get_group_count
)

logger = logging.getLogger(__name__)


async def process_command(client: TelegramClient, user_id: int, message) -> bool:
    """
    Process a dot command from user's Saved Messages.
    Returns True if the message was a command and was processed.
    """
    if not message.text:
        return False
    
    text = message.text.strip()
    
    if not text.startswith("."):
        return False
    
    cmd = text.lower().split()[0]
    
    try:
        if cmd == ".help":
            await handle_help(client, user_id, message)
            return True
        elif cmd == ".status":
            await handle_status(client, user_id, message)
            return True
        elif cmd == ".groups":
            await handle_groups(client, user_id, message)
            return True
        elif cmd == ".addgroup":
            await handle_addgroup(client, user_id, message, text)
            return True
        elif cmd == ".rmgroup":
            await handle_rmgroup(client, user_id, message, text)
            return True
        elif cmd == ".interval":
            await handle_interval(client, user_id, message, text)
            return True
    except Exception as e:
        logger.error(f"[User {user_id}] Command error: {e}")
        await reply_to_command(client, message.chat_id, f"Error: {str(e)}")
    
    return False


async def reply_to_command(client: TelegramClient, chat_id, text: str):
    """Send a reply to the chat where command was sent."""
    await client.send_message(chat_id, text)


async def handle_help(client: TelegramClient, user_id: int, message):
    """Handle .help command."""
    text = """📚 Available Commands

━━━━━━━━━━━━━━━━━━━

👥 Group Management
.addgroup <url> — Add a group to post
.rmgroup <url> — Remove a group
.groups — List all your groups

⚙️ Settings
.interval <minutes> — Set posting interval (min: {min_interval})
.status — View your account status

❓ Help
.help — Show this help message

━━━━━━━━━━━━━━━━━━━

📌 Examples:
• .addgroup https://t.me/mygroup
• .addgroup @mygroup
• .interval 30

💡 Notes:
• You must be a member of the group to add it
• Maximum {max_groups} groups allowed
• Minimum interval is {min_interval} minutes
""".format(min_interval=MIN_INTERVAL_MINUTES, max_groups=MAX_GROUPS_PER_USER)
    
    await reply_to_command(client, message.chat_id, text)


async def handle_status(client: TelegramClient, user_id: int, message):
    """Handle .status command."""
    # Get session
    session = await get_session(user_id)
    
    # Get plan
    plan = await get_plan(user_id)
    
    # Get config
    config = await get_user_config(user_id)
    
    # Get groups
    group_count = await get_group_count(user_id)
    
    # Format plan info
    if plan:
        from datetime import datetime
        expires = plan.get("expires_at")
        if expires and expires > datetime.utcnow():
            days_left = (expires - datetime.utcnow()).days
            plan_status = f"✅ Active ({days_left} days left)"
            plan_type = plan.get("plan_type", "trial").title()
        else:
            plan_status = "❌ Expired"
            plan_type = "Expired"
    else:
        plan_status = "❌ No Plan"
        plan_type = "None"
    
    phone = session.get("phone", "Unknown") if session else "Unknown"
    interval = config.get("interval_min", 30)
    
    text = f"""
📊 Account Status

━━━━━━━━━━━━━━━━━━━

📱 Phone: {phone}
🔗 Status: ✅ Connected

📋 Plan: {plan_type}
⏰ Status: {plan_status}

👥 Groups: {group_count}/{MAX_GROUPS_PER_USER}
⏱ Interval: {interval} minutes
🌙 Night Mode: 00:00–06:00 IST

━━━━━━━━━━━━━━━━━━━

Use .help to see all commands.
"""
    await reply_to_command(client, message.chat_id, text)


async def handle_groups(client: TelegramClient, user_id: int, message):
    """Handle .groups command - list all groups."""
    groups = await get_user_groups(user_id)
    
    if not groups:
        await reply_to_command(client, message.chat_id, "📭 No groups added yet\n\nUse .addgroup <url> to add a group.")
        return
    
    text = f"👥 Your Groups ({len(groups)}/{MAX_GROUPS_PER_USER})\n\n"
    
    for i, group in enumerate(groups, 1):
        title = group.get("chat_title", "Unknown")
        enabled = "✅" if group.get("enabled", True) else "❌"
        text += f"{i}. {enabled} {title}\n"
    
    text += "\n━━━━━━━━━━━━━━━━━━━\n"
    text += "Use .rmgroup <url> to remove a group."
    
    await reply_to_command(client, message.chat_id, text)


async def handle_addgroup(client: TelegramClient, user_id: int, message, text: str):
    """Handle .addgroup <url> command."""
    # Parse the URL/username
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        await reply_to_command(client, message.chat_id, 
            "❌ Usage: .addgroup <url or @username>\n\n"
            "Examples:\n"
            "• .addgroup https://t.me/mygroup\n"
            "• .addgroup @mygroup"
        )
        return
    
    group_input = parts[1].strip()
    
    # Check group limit
    count = await get_group_count(user_id)
    if count >= MAX_GROUPS_PER_USER:
        await reply_to_command(client, message.chat_id,
            f"❌ Maximum groups reached!\n\n"
            f"You can only add up to {MAX_GROUPS_PER_USER} groups.\n"
            f"Remove a group with .rmgroup <url> first."
        )
        return
    
    # Parse group identifier
    group_identifier = parse_group_input(group_input)
    
    if not group_identifier:
        await reply_to_command(client, message.chat_id,
            "❌ Invalid group URL or username\n\n"
            "Use format like:\n"
            "• https://t.me/groupname\n"
            "• @groupname"
        )
        return
    
    await reply_to_command(client, message.chat_id, "🔄 Checking group...")
    
    try:
        # Get the entity (group/channel)
        try:
            entity = await client.get_entity(group_identifier)
        except (UsernameNotOccupiedError, UsernameInvalidError):
            await reply_to_command(client, message.chat_id, "❌ Group not found\n\nMake sure the username/link is correct.")
            return
        except (ChannelPrivateError, ChannelInvalidError):
            await reply_to_command(client, message.chat_id, "❌ Cannot access group\n\nMake sure you are a member of this group.")
            return
        except (InviteHashInvalidError, InviteHashExpiredError):
            await reply_to_command(client, message.chat_id, "❌ Invalid or expired invite link")
            return
        
        # Get chat ID and title
        chat_id = entity.id
        chat_title = getattr(entity, 'title', None) or getattr(entity, 'username', str(chat_id))
        
        # Save to database
        success = await add_group(user_id, chat_id, chat_title)
        
        if success:
            await reply_to_command(client, message.chat_id,
                f"✅ Group added successfully!\n\n"
                f"📌 {chat_title}\n"
                f"🆔 {chat_id}\n\n"
                f"Messages will be forwarded to this group."
            )
        else:
            await reply_to_command(client, message.chat_id,
                f"❌ Could not add group\n\n"
                f"You may have reached the maximum limit of {MAX_GROUPS_PER_USER} groups."
            )
        
    except Exception as e:
        logger.error(f"Error adding group: {e}")
        await reply_to_command(client, message.chat_id, f"❌ Error: {str(e)}")


async def handle_rmgroup(client: TelegramClient, user_id: int, message, text: str):
    """Handle .rmgroup <url> command."""
    # Parse the URL/username
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        await reply_to_command(client, message.chat_id,
            "❌ Usage: .rmgroup <url or @username>\n\n"
            "Use .groups to see your groups first."
        )
        return
    
    group_input = parts[1].strip()
    
    # Parse group identifier
    group_identifier = parse_group_input(group_input)
    
    if not group_identifier:
        await reply_to_command(client, message.chat_id, "❌ Invalid group URL or username")
        return
    
    try:
        # Resolve entity
        try:
            entity = await client.get_entity(group_identifier)
            chat_id = entity.id
            chat_title = getattr(entity, 'title', str(chat_id))
        except Exception:
            # Try to match by username in existing groups
            groups = await get_user_groups(user_id)
            matched = None
            search_term = group_identifier.lstrip("@").lower()
            for g in groups:
                if search_term in g.get("chat_title", "").lower():
                    matched = g
                    break
            
            if matched:
                chat_id = matched["chat_id"]
                chat_title = matched["chat_title"]
            else:
                await reply_to_command(client, message.chat_id,
                    "❌ Group not found in your list\n\n"
                    "Use .groups to see your groups."
                )
                return
        
        # Remove from database
        await remove_group(user_id, chat_id)
        
        await reply_to_command(client, message.chat_id, f"✅ Group removed!\n\n📌 {chat_title}")
        
    except Exception as e:
        logger.error(f"Error removing group: {e}")
        await reply_to_command(client, message.chat_id, f"❌ Error: {str(e)}")


async def handle_interval(client: TelegramClient, user_id: int, message, text: str):
    """Handle .interval <minutes> command."""
    # Parse the interval
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        config = await get_user_config(user_id)
        current = config.get("interval_min", 30)
        await reply_to_command(client, message.chat_id,
            f"⏱ Current Interval: {current} minutes\n\n"
            f"Usage: .interval <minutes>\n"
            f"Minimum: {MIN_INTERVAL_MINUTES} minutes\n\n"
            f"Example: .interval 30"
        )
        return
    
    try:
        interval = int(parts[1].strip())
    except ValueError:
        await reply_to_command(client, message.chat_id,
            f"❌ Invalid number\n\n"
            f"Please enter a valid number of minutes.\n"
            f"Example: .interval 30"
        )
        return
    
    # Validate interval
    if interval < MIN_INTERVAL_MINUTES:
        await reply_to_command(client, message.chat_id,
            f"❌ Interval too low\n\n"
            f"Minimum interval is {MIN_INTERVAL_MINUTES} minutes."
        )
        return
    
    if interval > 1440:  # 24 hours max
        await reply_to_command(client, message.chat_id,
            "❌ Interval too high\n\n"
            "Maximum interval is 1440 minutes (24 hours)."
        )
        return
    
    # Update config
    await update_user_config(user_id, interval_min=interval)
    
    await reply_to_command(client, message.chat_id,
        f"✅ Interval updated!\n\n"
        f"⏱ New interval: {interval} minutes\n\n"
        f"Messages will be forwarded every {interval} minutes."
    )


def parse_group_input(input_str: str) -> str:
    """Parse group URL or username to identifier."""
    input_str = input_str.strip()
    
    # Handle @username
    if input_str.startswith("@"):
        return input_str
    
    # Handle t.me links
    patterns = [
        r"(?:https?://)?t\.me/([a-zA-Z0-9_]+)",
        r"(?:https?://)?telegram\.me/([a-zA-Z0-9_]+)",
        r"(?:https?://)?t\.me/joinchat/([a-zA-Z0-9_-]+)",
    ]
    
    for pattern in patterns:
        match = re.match(pattern, input_str)
        if match:
            return match.group(1) if "joinchat" not in pattern else input_str
    
    # If it looks like a username without @
    if re.match(r"^[a-zA-Z0-9_]+$", input_str):
        return f"@{input_str}"
    
    return None
