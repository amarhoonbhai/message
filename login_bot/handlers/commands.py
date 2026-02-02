"""
Dot command handlers for Login Bot.
Commands: .addgroup, .rmgroup, .status, .interval, .help
"""

import logging
import re
from telegram import Update
from telegram.ext import ContextTypes
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import (
    ChannelPrivateError,
    ChannelInvalidError,
    UsernameNotOccupiedError,
    UsernameInvalidError,
    InviteHashInvalidError,
    InviteHashExpiredError,
)

from config import MAX_GROUPS_PER_USER, MIN_INTERVAL_MINUTES, MAIN_BOT_USERNAME
from db.models import (
    get_session, get_user_groups, add_group, remove_group,
    get_user_config, update_user_config, get_plan, get_group_count
)

logger = logging.getLogger(__name__)


async def get_user_client(user_id: int) -> TelegramClient:
    """Get Telethon client for user."""
    session_data = await get_session(user_id)
    
    if not session_data or not session_data.get("connected"):
        return None
    
    session_string = session_data.get("session_string")
    api_id = session_data.get("api_id")
    api_hash = session_data.get("api_hash")
    
    if not session_string or not api_id or not api_hash:
        return None
    
    client = TelegramClient(
        StringSession(session_string),
        api_id,
        api_hash,
        device_model="Group Message Scheduler",
        system_version="1.0",
        app_version="1.0"
    )
    
    return client


async def handle_help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle .help command."""
    text = """
📚 *Available Commands*

━━━━━━━━━━━━━━━━━━━

👥 *Group Management*
`.addgroup <url>` — Add a group to post
`.rmgroup <url>` — Remove a group
`.groups` — List all your groups

⚙️ *Settings*
`.interval <minutes>` — Set posting interval (min: 20)
`.status` — View your account status

❓ *Help*
`.help` — Show this help message

━━━━━━━━━━━━━━━━━━━

📌 *Examples:*
• `.addgroup https://t.me/mygroup`
• `.addgroup @mygroup`
• `.interval 30`

💡 *Notes:*
• You must be a member of the group to add it
• Maximum {max_groups} groups allowed
• Minimum interval is {min_interval} minutes
""".format(max_groups=MAX_GROUPS_PER_USER, min_interval=MIN_INTERVAL_MINUTES)
    
    await update.message.reply_text(text, parse_mode="Markdown")


async def handle_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle .status command."""
    user_id = update.effective_user.id
    
    # Get session
    session = await get_session(user_id)
    
    if not session or not session.get("connected"):
        await update.message.reply_text(
            "❌ *No account connected*\n\n"
            "Use /start to connect your account first.",
            parse_mode="Markdown"
        )
        return
    
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
    
    phone = session.get("phone", "Unknown")
    interval = config.get("interval_min", 30)
    
    text = f"""
📊 *Account Status*

━━━━━━━━━━━━━━━━━━━

📱 *Phone:* `{phone}`
🔗 *Status:* ✅ Connected

📋 *Plan:* {plan_type}
⏰ *Status:* {plan_status}

👥 *Groups:* {group_count}/{MAX_GROUPS_PER_USER}
⏱ *Interval:* {interval} minutes
🌙 *Night Mode:* 00:00–06:00 IST

━━━━━━━━━━━━━━━━━━━

Use `.help` to see all commands.
"""
    
    await update.message.reply_text(text, parse_mode="Markdown")


async def handle_groups_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle .groups command - list all groups."""
    user_id = update.effective_user.id
    
    session = await get_session(user_id)
    if not session or not session.get("connected"):
        await update.message.reply_text("❌ Connect your account first with /start")
        return
    
    groups = await get_user_groups(user_id)
    
    if not groups:
        await update.message.reply_text(
            "📭 *No groups added yet*\n\n"
            "Use `.addgroup <url>` to add a group.",
            parse_mode="Markdown"
        )
        return
    
    text = f"👥 *Your Groups ({len(groups)}/{MAX_GROUPS_PER_USER})*\n\n"
    
    for i, group in enumerate(groups, 1):
        title = group.get("chat_title", "Unknown")
        enabled = "✅" if group.get("enabled", True) else "❌"
        text += f"{i}. {enabled} {title}\n"
    
    text += "\n━━━━━━━━━━━━━━━━━━━\n"
    text += "Use `.rmgroup <url>` to remove a group."
    
    await update.message.reply_text(text, parse_mode="Markdown")


async def handle_addgroup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle .addgroup <url> command."""
    user_id = update.effective_user.id
    message_text = update.message.text.strip()
    
    # Parse the URL/username
    parts = message_text.split(maxsplit=1)
    if len(parts) < 2:
        await update.message.reply_text(
            "❌ *Usage:* `.addgroup <url or @username>`\n\n"
            "Examples:\n"
            "• `.addgroup https://t.me/mygroup`\n"
            "• `.addgroup @mygroup`",
            parse_mode="Markdown"
        )
        return
    
    group_input = parts[1].strip()
    
    # Check session
    session = await get_session(user_id)
    if not session or not session.get("connected"):
        await update.message.reply_text("❌ Connect your account first with /start")
        return
    
    # Check group limit
    count = await get_group_count(user_id)
    if count >= MAX_GROUPS_PER_USER:
        await update.message.reply_text(
            f"❌ *Maximum groups reached!*\n\n"
            f"You can only add up to {MAX_GROUPS_PER_USER} groups.\n"
            f"Remove a group with `.rmgroup <url>` first.",
            parse_mode="Markdown"
        )
        return
    
    # Parse group identifier
    group_identifier = parse_group_input(group_input)
    
    if not group_identifier:
        await update.message.reply_text(
            "❌ *Invalid group URL or username*\n\n"
            "Use format like:\n"
            "• `https://t.me/groupname`\n"
            "• `@groupname`",
            parse_mode="Markdown"
        )
        return
    
    await update.message.reply_text("🔄 Checking group...")
    
    # Get client and verify membership
    client = await get_user_client(user_id)
    
    if not client:
        await update.message.reply_text("❌ Could not connect to your account. Try reconnecting.")
        return
    
    try:
        await client.connect()
        
        if not await client.is_user_authorized():
            await update.message.reply_text("❌ Session expired. Please reconnect with /start")
            return
        
        # Get the entity (group/channel)
        try:
            entity = await client.get_entity(group_identifier)
        except (UsernameNotOccupiedError, UsernameInvalidError):
            await update.message.reply_text(
                "❌ *Group not found*\n\n"
                "Make sure the username/link is correct.",
                parse_mode="Markdown"
            )
            return
        except (ChannelPrivateError, ChannelInvalidError):
            await update.message.reply_text(
                "❌ *Cannot access group*\n\n"
                "Make sure you are a member of this group.",
                parse_mode="Markdown"
            )
            return
        except (InviteHashInvalidError, InviteHashExpiredError):
            await update.message.reply_text(
                "❌ *Invalid or expired invite link*",
                parse_mode="Markdown"
            )
            return
        
        # Get chat ID and title
        chat_id = entity.id
        chat_title = getattr(entity, 'title', None) or getattr(entity, 'username', str(chat_id))
        
        # Save to database
        success = await add_group(user_id, chat_id, chat_title)
        
        if success:
            await update.message.reply_text(
                f"✅ *Group added successfully!*\n\n"
                f"📌 {chat_title}\n"
                f"🆔 `{chat_id}`\n\n"
                f"Messages will be forwarded to this group.",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                f"❌ *Could not add group*\n\n"
                f"You may have reached the maximum limit of {MAX_GROUPS_PER_USER} groups.",
                parse_mode="Markdown"
            )
        
    except Exception as e:
        logger.error(f"Error adding group: {e}")
        await update.message.reply_text(f"❌ *Error:* {str(e)}", parse_mode="Markdown")
    finally:
        await client.disconnect()


async def handle_rmgroup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle .rmgroup <url> command."""
    user_id = update.effective_user.id
    message_text = update.message.text.strip()
    
    # Parse the URL/username
    parts = message_text.split(maxsplit=1)
    if len(parts) < 2:
        await update.message.reply_text(
            "❌ *Usage:* `.rmgroup <url or @username>`\n\n"
            "Use `.groups` to see your groups first.",
            parse_mode="Markdown"
        )
        return
    
    group_input = parts[1].strip()
    
    # Check session
    session = await get_session(user_id)
    if not session or not session.get("connected"):
        await update.message.reply_text("❌ Connect your account first with /start")
        return
    
    # Parse group identifier
    group_identifier = parse_group_input(group_input)
    
    if not group_identifier:
        await update.message.reply_text(
            "❌ *Invalid group URL or username*",
            parse_mode="Markdown"
        )
        return
    
    # Get client to resolve the group
    client = await get_user_client(user_id)
    
    if not client:
        await update.message.reply_text("❌ Could not connect to your account.")
        return
    
    try:
        await client.connect()
        
        if not await client.is_user_authorized():
            await update.message.reply_text("❌ Session expired. Please reconnect with /start")
            return
        
        # Resolve entity
        try:
            entity = await client.get_entity(group_identifier)
            chat_id = entity.id
            chat_title = getattr(entity, 'title', str(chat_id))
        except Exception:
            # Try to match by username in existing groups
            groups = await get_user_groups(user_id)
            matched = None
            for g in groups:
                if group_identifier.lower() in g.get("chat_title", "").lower():
                    matched = g
                    break
            
            if matched:
                chat_id = matched["chat_id"]
                chat_title = matched["chat_title"]
            else:
                await update.message.reply_text(
                    "❌ *Group not found in your list*\n\n"
                    "Use `.groups` to see your groups.",
                    parse_mode="Markdown"
                )
                return
        
        # Remove from database
        await remove_group(user_id, chat_id)
        
        await update.message.reply_text(
            f"✅ *Group removed!*\n\n"
            f"📌 {chat_title}",
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Error removing group: {e}")
        await update.message.reply_text(f"❌ *Error:* {str(e)}", parse_mode="Markdown")
    finally:
        await client.disconnect()


async def handle_interval_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle .interval <minutes> command."""
    user_id = update.effective_user.id
    message_text = update.message.text.strip()
    
    # Parse the interval
    parts = message_text.split(maxsplit=1)
    if len(parts) < 2:
        config = await get_user_config(user_id)
        current = config.get("interval_min", 30)
        await update.message.reply_text(
            f"⏱ *Current Interval:* {current} minutes\n\n"
            f"*Usage:* `.interval <minutes>`\n"
            f"Minimum: {MIN_INTERVAL_MINUTES} minutes\n\n"
            f"Example: `.interval 30`",
            parse_mode="Markdown"
        )
        return
    
    try:
        interval = int(parts[1].strip())
    except ValueError:
        await update.message.reply_text(
            f"❌ *Invalid number*\n\n"
            f"Please enter a valid number of minutes.\n"
            f"Example: `.interval 30`",
            parse_mode="Markdown"
        )
        return
    
    # Check session
    session = await get_session(user_id)
    if not session or not session.get("connected"):
        await update.message.reply_text("❌ Connect your account first with /start")
        return
    
    # Validate interval
    if interval < MIN_INTERVAL_MINUTES:
        await update.message.reply_text(
            f"❌ *Interval too low*\n\n"
            f"Minimum interval is {MIN_INTERVAL_MINUTES} minutes.",
            parse_mode="Markdown"
        )
        return
    
    if interval > 1440:  # 24 hours max
        await update.message.reply_text(
            "❌ *Interval too high*\n\n"
            "Maximum interval is 1440 minutes (24 hours).",
            parse_mode="Markdown"
        )
        return
    
    # Update config
    await update_user_config(user_id, interval_min=interval)
    
    await update.message.reply_text(
        f"✅ *Interval updated!*\n\n"
        f"⏱ New interval: {interval} minutes\n\n"
        f"Messages will be forwarded every {interval} minutes.",
        parse_mode="Markdown"
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


async def handle_dot_commands(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Handle dot commands. Returns True if a command was handled.
    """
    if not update.message or not update.message.text:
        return False
    
    text = update.message.text.strip().lower()
    
    if text.startswith(".help"):
        await handle_help_command(update, context)
        return True
    elif text.startswith(".status"):
        await handle_status_command(update, context)
        return True
    elif text.startswith(".groups"):
        await handle_groups_command(update, context)
        return True
    elif text.startswith(".addgroup"):
        await handle_addgroup_command(update, context)
        return True
    elif text.startswith(".rmgroup"):
        await handle_rmgroup_command(update, context)
        return True
    elif text.startswith(".interval"):
        await handle_interval_command(update, context)
        return True
    
    return False
