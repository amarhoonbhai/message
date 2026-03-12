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

from core.config import MAX_GROUPS_PER_USER, MIN_INTERVAL_MINUTES
from models.session import get_session
from models.user import get_user_config, update_user_config
from models.group import get_user_groups, add_group, remove_group, get_group_count, toggle_group
from models.plan import get_plan

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
        elif cmd == ".shuffle":
            await handle_shuffle(client, user_id, message, text)
            return True
        elif cmd == ".copymode":
            await handle_copymode(client, user_id, message, text)
            return True
        elif cmd == ".sendmode":
            await handle_sendmode(client, user_id, message, text)
            return True
        elif cmd == ".responder":
            await handle_responder(client, user_id, message, text)
            return True
        elif cmd == ".ping":
            await reply_to_command(client, message, "● Pong! Worker is active ⚡")
            return True
        elif cmd == ".stats":
            await handle_status(client, user_id, message)
            return True
        elif cmd == ".nightmode":
            await handle_nightmode(client, user_id, message, text)
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
    from core.config import MIN_INTERVAL_MINUTES
    text = (
        "📘 *BOT WORKER COMMANDS* 📘\n\n"
        "👥 *GROUP MANAGEMENT*\n"
        "🔸 `.addgroup <url>` — Add to forward list\n"
        "🔸 `.rmgroup <url/idx>` — Remove from list\n"
        "🔸 `.groups` — Show your active groups\n\n"
        "⚙️ *SETTINGS*\n"
        "🔸 `.interval <min>` — Set loop delay (min: {min}m)\n"
        "🔸 `.shuffle on/off` — Randomize loop order\n"
        "🔸 `.copymode on/off` — Send as fresh message\n"
        "🔸 `.sendmode <seq/rot/rand>` — Message distribution\n"
        "🔸 `.responder <msg>` — Set auto-reply for DMs\n"
        "🔸 `.responder off` — Disable auto-reply\n\n"
        "⚡ *DIAGNOSTICS*\n"
        "🔸 `.ping` — Check if worker is alive\n\n"
        "👑 *OWNER COMMANDS*\n"
        "🔸 `.nightmode on/off/auto` — Global control\n\n"
        "💡 *PRO TIP:* You can add multiple groups at once!\n"
        "Example: `.addgroup @group1 @group2`"
    ).format(min=MIN_INTERVAL_MINUTES)
    
    await reply_to_command(client, message, text)


async def handle_status(client: TelegramClient, user_id: int, message):
    """Handle .status command with detailed information for THIS account."""
    # Get specifically this account's session
    phone = getattr(client, 'phone', None)
    session = await get_session(user_id, phone)
    
    # Get plan (User-wide)
    plan = await get_plan(user_id)
    
    # Get config (User-wide)
    config = await get_user_config(user_id)
    
    # Get groups (all groups for this user)
    groups = await get_user_groups(user_id)
    total_groups = len(groups)
    enabled_groups = len([g for g in groups if g.get("enabled", True)])
    
    # Format plan info
    if plan:
        from datetime import datetime
        expires = plan.get("expires_at")
        if expires and expires > datetime.utcnow():
            days_left = (expires - datetime.utcnow()).days
            hours_left = ((expires - datetime.utcnow()).seconds // 3600)
            plan_type = plan.get("plan_type", "trial").title()
            if plan_type.lower() == "trial":
                plan_badge = "🏅 TRIAL"
            else:
                plan_badge = "💎 PREMIUM"
            if days_left > 0:
                plan_status = f"🟢 Active — {days_left}d {hours_left}h left"
            else:
                plan_status = f"🟢 Active — {hours_left}h left"
        else:
            plan_status = "🔴 Expired"
            plan_badge = "⚠️ EXPIRED"
            plan_type = "Expired"
    else:
        plan_status = "⚪ No Plan"
        plan_badge = "❌ NONE"
        plan_type = "None"
    
    phone = session.get("phone", "Unknown") if session else "Unknown"
    from core.config import DEFAULT_INTERVAL_MINUTES
    interval = config.get("interval_min", DEFAULT_INTERVAL_MINUTES)
    
    # Setting indicators
    copy_icon = "🟢 ON" if config.get("copy_mode") else "⚫ OFF"
    shuffle_icon = "🟢 ON" if config.get("shuffle_mode") else "⚫ OFF"
    send_mode = config.get("send_mode", "sequential").title()
    responder_icon = "🟢 ON" if config.get("auto_reply_enabled") else "⚫ OFF"
    
    text = f"""📊 *WORKER DIAGNOSTICS* 📊

📱 *ACCOUNT PROFILE*
├ Phone: {phone}
└ Status: 🟢 Connected

🏷️ *PLAN INFO*
├ Tier: {plan_type}
└ Status: {plan_status.replace('🟢', '●').replace('🔴', '○')}

⚡ *LIVE SETTINGS*
├ Interval: {interval}m
├ Send Mode: {send_mode}
├ Shuffle: {"🟢 ON" if config.get("shuffle_mode") else "⚫ OFF"}
├ Copy Mode: {"🟢 ON" if config.get("copy_mode") else "⚫ OFF"}
├ Auto-Responder: {"🟢 ON" if config.get("auto_reply_enabled") else "⚫ OFF"}
└ Night Mode: {await get_night_mode_label()}

👥 *GROUPS ({enabled_groups}/{total_groups})*

Type `.help` for available commands
"""
    await reply_to_command(client, message, text)


async def handle_groups(client: TelegramClient, user_id: int, message):
    """Handle .groups command - list groups for THIS account."""
    phone = getattr(client, 'phone', None)
    groups = await get_user_groups(user_id)
    
    if not groups:
        await reply_to_command(client, message, 
            f"📁 GROUPS — {phone}\n"
            f"══════════════════════════\n\n"
            f"⚪ No groups added yet.\n\n"
            f"💡 Use .addgroup <url> to add one."
        )
        return
    
    enabled = len([g for g in groups if g.get("enabled", True)])
    text = f"📁 GROUPS — {phone}\n"
    text += f"══════════════════════════\n\n"
    text += f"🟢 {enabled} active \u25aa {len(groups) - enabled} paused \u25aa {len(groups)}/{MAX_GROUPS_PER_USER} slots\n\n"
    
    for i, group in enumerate(groups, 1):
        title = group.get("chat_title", "Unknown")
        enabled = group.get("enabled", True)
        reason = group.get("pause_reason")
        
        if enabled:
            icon = "🟢"
            status_suffix = ""
        else:
            icon = "🔴"
            status_suffix = f" (Paused: {reason})" if reason else " (Paused)"
            
        text += f"  {i}. {icon} {title}{status_suffix}\n"
    
    text += f"\n══════════════════════════\n"
    text += "💡 .rmgroup <number> to remove."
    
    await reply_to_command(client, message, text)


async def handle_addgroup(client: TelegramClient, user_id: int, message, text: str):
    """Handle .addgroup <url> [url2] [url3] command - supports multiple groups."""
    # Parse URLs/usernames (split by spaces or newlines)
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        await reply_to_command(client, message, 
            "○ Usage: .addgroup <url> [url2] [url3]...\n\n"
            "Examples:\n"
            "  ◦ .addgroup @group1\n"
            "  ◦ .addgroup @group1 @group2 @group3\n"
            "  ◦ .addgroup https://t.me/group1 https://t.me/group2"
        )
        return
    
    # Split input by spaces and newlines to get multiple groups
    group_inputs = parts[1].replace('\n', ' ').split()
    
    if not group_inputs:
        await reply_to_command(client, message, "○ No groups provided")
        return
    
    # Check group limit
    count = await get_group_count(user_id)
    available_slots = MAX_GROUPS_PER_USER - count
    
    if available_slots <= 0:
        await reply_to_command(client, message,
            f"○ Maximum groups reached!\n\n"
            f"You can only add up to {MAX_GROUPS_PER_USER} groups.\n"
            f"Remove a group with .rmgroup first."
        )
        return
    
    # Limit to available slots
    if len(group_inputs) > available_slots:
        group_inputs = group_inputs[:available_slots]
        await reply_to_command(client, message, 
            f"▪ Only processing {available_slots} group(s) due to limit..."
        )
    
    await reply_to_command(client, message, f"➤ Checking {len(group_inputs)} group(s)...")
    
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
            # Link to the current account's phone for multi-account support
            success = await add_group(user_id, chat_id, chat_title, account_phone=getattr(client, 'phone', None))
            
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
            response += f"  ▸ 🟢 {title}\n"
    
    if failed:
        response += f"\n❌ Failed {len(failed)}:\n"
        for name, reason in failed:
            response += f"  ▸ 🔴 {name[:15]}... — {reason}\n"
    
    if not response:
        response = "⚪ No groups were added."
    
    # Add current count
    new_count = await get_group_count(user_id)
    response += f"\n📁 Total: {new_count}/{MAX_GROUPS_PER_USER} slots used."
    
    await reply_to_command(client, message, response.strip())


async def handle_rmgroup(client: TelegramClient, user_id: int, message, text: str):
    """Handle .rmgroup <number or url> command."""
    # Parse the input
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        await reply_to_command(client, message,
            "○ Usage: .rmgroup <number or url>\n\n"
            "Examples:\n"
            "  ◦ .rmgroup 1\n"
            "  ◦ .rmgroup @groupname\n\n"
            "▪ Use .groups to see your groups first."
        )
        return
    
    group_input = parts[1].strip()
    
    # Get user's groups FOR THIS ACCOUNT
    phone = getattr(client, 'phone', None)
    groups = await get_user_groups(user_id, phone=phone)
    
    if not groups:
        await reply_to_command(client, message, 
            f"○ No groups found for this account ({phone}).\n\n"
            "▪ Use .addgroup to add groups first."
        )
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
                f"○ Invalid group number\n\n"
                f"You have {len(groups)} group(s). Use a number between 1 and {len(groups)}."
            )
            return
    else:
        # Try to parse as URL/username
        group_identifier = parse_group_input(group_input)
        
        if not group_identifier:
            await reply_to_command(client, message, "○ Invalid group URL or username")
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
                    "○ Group not found in your list\n\n"
                    "▪ Use .groups to see your groups."
                )
                return
    
    try:
        # Remove from database
        await remove_group(user_id, chat_id)
        remaining = await get_group_count(user_id)
        await reply_to_command(client, message, 
            f"✅ Group removed!\n\n"
            f"  ▸ {chat_title}\n\n"
            f"📁 Remaining: {remaining}/{MAX_GROUPS_PER_USER} slots."
        )
        
    except Exception as e:
        logger.error(f"Error removing group: {e}")
        await reply_to_command(client, message, f"❌ Error: {str(e)}")


async def handle_interval(client: TelegramClient, user_id: int, message, text: str):
    """Handle .interval <minutes> command."""
    # Parse the interval
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        config = await get_user_config(user_id)
        current = config.get("interval_min", MIN_INTERVAL_MINUTES)
        await reply_to_command(client, message,
            f"➤ Current Interval: {current} minutes\n\n"
            f"Usage: .interval <minutes>\n"
            f"Minimum: {MIN_INTERVAL_MINUTES} minutes\n\n"
            f"Example: .interval 30"
        )
        return
    
    try:
        interval = int(parts[1].strip())
    except ValueError:
        await reply_to_command(client, message,
            f"○ Invalid number\n\n"
            f"Please enter a valid number of minutes.\n"
            f"Example: .interval 30"
        )
        return
    
    # Validate interval
    if interval < MIN_INTERVAL_MINUTES:
        await reply_to_command(client, message,
            f"○ Interval too low\n\n"
            f"Minimum interval is {MIN_INTERVAL_MINUTES} minutes."
        )
        return
    
    if interval > 1440:  # 24 hours max
        await reply_to_command(client, message,
            "○ Interval too high\n\n"
            "Maximum interval is 1440 minutes (24 hours)."
        )
        return
    
    # Update config
    await update_user_config(user_id, interval_min=interval)
    
    await reply_to_command(client, message,
        f"● Interval updated!\n\n"
        f"➤ New interval: {interval} minutes\n\n"
        f"Messages will be forwarded every {interval} minutes."
    )


async def handle_shuffle(client: TelegramClient, user_id: int, message, text: str):
    """Handle .shuffle on/off command."""
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        config = await get_user_config(user_id)
        current = "ON" if config.get("shuffle_mode", False) else "OFF"
        await reply_to_command(client, message,
            f"➤ Shuffle Mode: {current}\n\n"
            f"Usage: .shuffle on/off\n"
            f"Randomizes group order each cycle."
        )
        return
    
    val = parts[1].strip().lower()
    enable = val == "on"
    
    await update_user_config(user_id, shuffle_mode=enable)
    status_text = "ENABLED ●" if enable else "DISABLED ○"
    
    await reply_to_command(client, message,
        f"■ Shuffle Mode {status_text}\n\n"
        f"Groups will now be {'randomized' if enable else 'sent in order'} each cycle."
    )


async def handle_copymode(client: TelegramClient, user_id: int, message, text: str):
    """Handle .copymode on/off command."""
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        config = await get_user_config(user_id)
        current = "ON" if config.get("copy_mode", False) else "OFF"
        await reply_to_command(client, message,
            f"➤ Copy Mode: {current}\n\n"
            f"Usage: .copymode on/off\n"
            f"Sends as new message instead of forwarding."
        )
        return
    
    val = parts[1].strip().lower()
    enable = val == "on"
    
    await update_user_config(user_id, copy_mode=enable)
    status_text = "ENABLED ●" if enable else "DISABLED ○"
    
    await reply_to_command(client, message,
        f"■ Copy Mode {status_text}\n\n"
        f"Messages will now be {'sent as new copies' if enable else 'forwarded normally'}."
    )


async def handle_sendmode(client: TelegramClient, user_id: int, message, text: str):
    """Handle .sendmode <sequential/rotate/random> command."""
    parts = text.split(maxsplit=1)
    config = await get_user_config(user_id)
    current = config.get("send_mode", "sequential")
    
    if len(parts) < 2:
        await reply_to_command(client, message,
            f"➤ Send Mode: {current.title()}\n\n"
            f"Usage: .sendmode <mode>\n"
            f"Modes:\n"
            f"  ◦ sequential: Ad 1 to all groups, then Ad 2...\n"
            f"  ◦ rotate: Grp 1 gets Ad 1, Grp 2 gets Ad 2...\n"
            f"  ◦ random: Random ad sent to each group"
        )
        return
    
    val = parts[1].strip().lower()
    if val in ["seq", "sequential"]:
        val = "sequential"
    elif val in ["rot", "rotate"]:
        val = "rotate"
    elif val in ["rand", "random"]:
        val = "random"
    else:
        await reply_to_command(client, message, "○ Invalid mode! Choose: sequential, rotate, or random.")
        return
    
    await update_user_config(user_id, send_mode=val)
    
    await reply_to_command(client, message,
        f"■ Send Mode Updated: {val.title()} ●\n\n"
        f"Message distribution pattern changed."
    )


async def handle_responder(client: TelegramClient, user_id: int, message, text: str):
    """Handle .responder on/off or .responder <message>."""
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        config = await get_user_config(user_id)
        current = "ON" if config.get("auto_reply_enabled", False) else "OFF"
        await reply_to_command(client, message,
            f"➤ Auto-Responder: {current}\n\n"
            f"Usage:\n"
            f"  .responder on/off\n"
            f"  .responder <your message>\n\n"
            f"Current message:\n"
            f"\"{config.get('auto_reply_text')}\""
        )
        return
    
    val = parts[1].strip()
    
    if val.lower() == "on":
        await update_user_config(user_id, auto_reply_enabled=True)
        await reply_to_command(client, message, "■ Auto-Responder ENABLED ●")
    elif val.lower() == "off":
        await update_user_config(user_id, auto_reply_enabled=False)
        await reply_to_command(client, message, "■ Auto-Responder DISABLED ○")
    else:
        # Set message
        await update_user_config(user_id, auto_reply_text=val, auto_reply_enabled=True)
        await reply_to_command(client, message, 
            f"● Auto-Responder set and ENABLED!\n\n"
            f"➤ New message: {val}"
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
async def handle_nightmode(client: TelegramClient, user_id: int, message, text: str):
    """Handle .nightmode on/off/auto command (Owner only)."""
    from core.config import OWNER_ID
    if user_id != OWNER_ID:
        await reply_to_command(client, message, "❌ This command is restricted to the BOT OWNER.")
        return
        
    parts = text.split()
    if len(parts) < 2:
        from models.job import get_global_settings
        settings = await get_global_settings()
        current = settings.get("night_mode_force", "auto").upper()
        await reply_to_command(client, message, 
            f"🌙 GLOBAL NIGHT MODE\n\n"
            f"➤ Current: {current}\n\n"
            f"Usage: .nightmode <on/off/auto>\n"
            f"  ◦ `on`: Force night mode NOW\n"
            f"  ◦ `off`: Disable night mode NOW\n"
            f"  ◦ `auto`: Use standard 00:00-06:00 IST"
        )
        return
        
    val = parts[1].lower()
    if val not in ["on", "off", "auto"]:
        await reply_to_command(client, message, "❌ Use: .nightmode on/off/auto")
        return
        
    from models.job import update_global_settings
    await update_global_settings(night_mode_force=val)
    
    await reply_to_command(client, message, 
        f"✅ GLOBAL NIGHT MODE updated to: *{val.upper()}*\n\n"
        f"This change affects all accounts globally."
    )

async def get_night_mode_label() -> str:
    """Helper to get a human-friendly night mode status label."""
    from models.job import get_global_settings
    from services.worker.send_logic import is_night_mode
    
    settings = await get_global_settings()
    force = settings.get("night_mode_force", "auto")
    active = await is_night_mode()
    
    if force == "on":
        return "🔴 FORCED ON"
    if force == "off":
         return "🟢 FORCED OFF"
    
    return "🌙 Active (00-06 IST)" if active else "☀️ Inactive (Daytime)"
