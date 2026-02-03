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
        await reply_to_command(client, message, f"Error: {str(e)}")
    
    return False


async def reply_to_command(client: TelegramClient, message, text: str):
    """Send a reply to the message that triggered the command."""
    await message.reply(text)


async def handle_help(client: TelegramClient, user_id: int, message):
    """Handle .help command with professional styling."""
    text = """AVAILABLE COMMANDS
━━━━━━━━━━━━━━━━━━━━
GROUP MANAGEMENT
▢ .addgroup <url> — Add group
▢ .rmgroup <url> — Remove group
▢ .groups — List groups

SETTINGS
▢ .interval <minutes> — Set interval (min {min_interval})
▢ .status — Account status

HELP
▢ .help — Show help
━━━━━━━━━━━━━━━━━━━━
EXAMPLES
▢ .addgroup https://t.me/mygroup
▢ .addgroup @mygroup
▢ .interval 30

NOTES
▢ Must be a group member
▢ Max {max_groups} groups allowed
▢ Minimum interval {min_interval} minutes
""".format(min_interval=MIN_INTERVAL_MINUTES, max_groups=MAX_GROUPS_PER_USER)
    
    await reply_to_command(client, message, text)


async def handle_status(client: TelegramClient, user_id: int, message):
    """Handle .status command with detailed group info."""
    # Get session
    session = await get_session(user_id)
    
    # Get plan
    plan = await get_plan(user_id)
    
    # Get config
    config = await get_user_config(user_id)
    
    # Get groups for diagonal count
    groups = await get_user_groups(user_id)
    total_groups = len(groups)
    enabled_groups = len([g for g in groups if g.get("enabled", True)])
    
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
    from config import DEFAULT_INTERVAL_MINUTES
    interval = config.get("interval_min", DEFAULT_INTERVAL_MINUTES)
    
    text = f"""📊 Account Status

━━━━━━━━━━━━━━━━━━━━

📱 Phone: {phone}
🔗 Status: ✅ Connected

📋 Plan: {plan_type}
⏰ Status: {plan_status}

👥 Groups: {enabled_groups}/{total_groups} (Max {MAX_GROUPS_PER_USER})
⏱ Interval: {interval} minutes
🌙 Night Mode: 00:00–06:00 IST

━━━━━━━━━━━━━━━━━━━━

Use .help to see all commands."""
    await reply_to_command(client, message, text)


async def handle_groups(client: TelegramClient, user_id: int, message):
    """Handle .groups command - list all groups."""
    groups = await get_user_groups(user_id)
    
    if not groups:
        await reply_to_command(client, message, "📭 No groups added yet\n\nUse .addgroup <url> to add a group.")
        return
    
    text = f"👥 Your Groups ({len(groups)}/{MAX_GROUPS_PER_USER})\n\n"
    
    for i, group in enumerate(groups, 1):
        title = group.get("chat_title", "Unknown")
        enabled = "✅" if group.get("enabled", True) else "❌"
        text += f"{i}. {enabled} {title}\n"
    
    text += "\n━━━━━━━━━━━━━━━━━━━\n"
    text += "Use .rmgroup <number> to remove a group."
    
    await reply_to_command(client, message, text)


async def handle_addgroup(client: TelegramClient, user_id: int, message, text: str):
    """Handle .addgroup <url> [url2] [url3] command - supports multiple groups."""
    # Parse URLs/usernames (split by spaces or newlines)
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        await reply_to_command(client, message, 
            "❌ Usage: .addgroup <url> [url2] [url3]...\n\n"
            "Examples:\n"
            "• .addgroup @group1\n"
            "• .addgroup @group1 @group2 @group3\n"
            "• .addgroup https://t.me/group1 https://t.me/group2"
        )
        return
    
    # Split input by spaces and newlines to get multiple groups
    group_inputs = parts[1].replace('\n', ' ').split()
    
    if not group_inputs:
        await reply_to_command(client, message, "❌ No groups provided")
        return
    
    # Check group limit
    count = await get_group_count(user_id)
    available_slots = MAX_GROUPS_PER_USER - count
    
    if available_slots <= 0:
        await reply_to_command(client, message,
            f"❌ Maximum groups reached!\n\n"
            f"You can only add up to {MAX_GROUPS_PER_USER} groups.\n"
            f"Remove a group with .rmgroup first."
        )
        return
    
    # Limit to available slots
    if len(group_inputs) > available_slots:
        group_inputs = group_inputs[:available_slots]
        await reply_to_command(client, message, 
            f"⚠️ Only processing {available_slots} group(s) due to limit..."
        )
    
    await reply_to_command(client, message, f"🔄 Checking {len(group_inputs)} group(s)...")
    
    added = []
    failed = []
    
    for group_input in group_inputs:
        group_input = group_input.strip()
        if not group_input:
            continue
        
        # Parse group identifier
        group_identifier = parse_group_input(group_input)
        
        if not group_identifier:
            failed.append((group_input, "Invalid URL"))
            continue
        
        try:
            # Get the entity (group/channel)
            entity = await client.get_entity(group_identifier)
            chat_id = entity.id
            chat_title = getattr(entity, 'title', None) or getattr(entity, 'username', str(chat_id))
            
            # Save to database
            success = await add_group(user_id, chat_id, chat_title)
            
            if success:
                added.append(chat_title)
            else:
                failed.append((group_input, "Already exists or limit reached"))
                
        except (UsernameNotOccupiedError, UsernameInvalidError):
            failed.append((group_input, "Not found"))
        except (ChannelPrivateError, ChannelInvalidError):
            failed.append((group_input, "Private/No access"))
        except (InviteHashInvalidError, InviteHashExpiredError):
            failed.append((group_input, "Invalid invite"))
        except Exception as e:
            failed.append((group_input, str(e)[:20]))
    
    # Build response
    response = ""
    
    if added:
        response += f"✅ Added {len(added)} group(s):\n"
        for title in added:
            response += f"  • {title}\n"
    
    if failed:
        response += f"\n❌ Failed {len(failed)}:\n"
        for name, reason in failed:
            response += f"  • {name[:15]}... - {reason}\n"
    
    if not response:
        response = "❌ No groups were added"
    
    await reply_to_command(client, message, response.strip())


async def handle_rmgroup(client: TelegramClient, user_id: int, message, text: str):
    """Handle .rmgroup <number or url> command."""
    # Parse the input
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        await reply_to_command(client, message,
            "❌ Usage: .rmgroup <number or url>\n\n"
            "Examples:\n"
            "• .rmgroup 1\n"
            "• .rmgroup @groupname\n\n"
            "Use .groups to see your groups first."
        )
        return
    
    group_input = parts[1].strip()
    
    # Get user's groups
    groups = await get_user_groups(user_id)
    
    if not groups:
        await reply_to_command(client, message, "📭 No groups to remove.\n\nUse .addgroup to add groups first.")
        return
    
    chat_id = None
    chat_title = None
    
    # Check if input is a number (remove by position)
    if group_input.isdigit():
        group_num = int(group_input)
        if 1 <= group_num <= len(groups):
            group = groups[group_num - 1]
            chat_id = group["chat_id"]
            chat_title = group.get("chat_title", "Unknown")
        else:
            await reply_to_command(client, message,
                f"❌ Invalid group number\n\n"
                f"You have {len(groups)} group(s). Use a number between 1 and {len(groups)}."
            )
            return
    else:
        # Try to parse as URL/username
        group_identifier = parse_group_input(group_input)
        
        if not group_identifier:
            await reply_to_command(client, message, "❌ Invalid group URL or username")
            return
        
        try:
            # Try to resolve entity
            entity = await client.get_entity(group_identifier)
            chat_id = entity.id
            chat_title = getattr(entity, 'title', str(chat_id))
        except Exception:
            # Try to match by name in existing groups
            search_term = group_identifier.lstrip("@").lower()
            for g in groups:
                if search_term in g.get("chat_title", "").lower():
                    chat_id = g["chat_id"]
                    chat_title = g["chat_title"]
                    break
            
            if not chat_id:
                await reply_to_command(client, message,
                    "❌ Group not found in your list\n\n"
                    "Use .groups to see your groups."
                )
                return
    
    try:
        # Remove from database
        await remove_group(user_id, chat_id)
        await reply_to_command(client, message, f"✅ Group removed!\n\n📌 {chat_title}")
        
    except Exception as e:
        logger.error(f"Error removing group: {e}")
        await reply_to_command(client, message, f"❌ Error: {str(e)}")


async def handle_interval(client: TelegramClient, user_id: int, message, text: str):
    """Handle .interval <minutes> command."""
    # Parse the interval
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        config = await get_user_config(user_id)
        current = config.get("interval_min", 30)
        await reply_to_command(client, message,
            f"⏱ Current Interval: {current} minutes\n\n"
            f"Usage: .interval <minutes>\n"
            f"Minimum: {MIN_INTERVAL_MINUTES} minutes\n\n"
            f"Example: .interval 30"
        )
        return
    
    try:
        interval = int(parts[1].strip())
    except ValueError:
        await reply_to_command(client, message,
            f"❌ Invalid number\n\n"
            f"Please enter a valid number of minutes.\n"
            f"Example: .interval 30"
        )
        return
    
    # Validate interval
    if interval < MIN_INTERVAL_MINUTES:
        await reply_to_command(client, message,
            f"❌ Interval too low\n\n"
            f"Minimum interval is {MIN_INTERVAL_MINUTES} minutes."
        )
        return
    
    if interval > 1440:  # 24 hours max
        await reply_to_command(client, message,
            "❌ Interval too high\n\n"
            "Maximum interval is 1440 minutes (24 hours)."
        )
        return
    
    # Update config
    await update_user_config(user_id, interval_min=interval)
    
    await reply_to_command(client, message,
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
    
    # Handle t.me links with + (newer invite links)
    if "t.me/+" in input_str or "telegram.me/+" in input_str:
        return input_str
    
    # Handle joinchat links
    if "joinchat/" in input_str:
        return input_str
    
    # Handle message links (extract chat identifier)
    # https://t.me/c/123456789/123 -> 123456789
    # https://t.me/groupname/123 -> groupname
    message_link_pattern = r"(?:https?://)?(?:t\.me|telegram\.me)/(?:c/)?([a-zA-Z0-9_-]+)/(\d+)"
    match = re.match(message_link_pattern, input_str)
    if match:
        return match.group(1)

    # Handle various domain variations and protocols
    patterns = [
        r"(?:https?://)?(?:t\.me|telegram\.me|telegram\.dog)/([a-zA-Z0-9_]+)",
        r"tg://resolve\?domain=([a-zA-Z0-9_]+)",
        r"tg://join\?invite=([a-zA-Z0-9_-]+)",
    ]
    
    for pattern in patterns:
        match = re.match(pattern, input_str)
        if match:
            if "invite=" in pattern:
                return f"https://t.me/+{match.group(1)}"
            return match.group(1)
    
    # If it looks like a numeric ID
    if re.match(r"^-?\d+$", input_str):
        return input_str

    # If it looks like a username without @
    if re.match(r"^[a-zA-Z0-9_]+$", input_str):
        return f"@{input_str}"
    
    return None
