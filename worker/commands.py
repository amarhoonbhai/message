"""
Command handler for processing dot commands from user's Saved Messages.
Commands are sent by user to their own Saved Messages and processed by Worker.
"""

import logging
import re
from typing import Optional, List
from telethon import TelegramClient
from telethon.errors import (
    ChannelPrivateError,
    ChannelInvalidError,
    UsernameNotOccupiedError,
    UsernameInvalidError,
    InviteHashInvalidError,
    InviteHashExpiredError,
)
from telethon.tl.types import InputPeerSelf, InputPeerChannel, InputPeerChat, Channel, Chat, DialogFilter
from telethon.tl.functions.messages import GetDialogFiltersRequest
from telethon.tl.functions.chatlists import CheckChatlistInviteRequest, JoinChatlistInviteRequest

from core.config import MAX_GROUPS_PER_USER, MIN_INTERVAL_MINUTES
from models.session import get_session
from models.user import get_user_config, update_user_config
from models.group import get_user_groups, add_group, remove_group, get_group_count, toggle_group
from db.models import get_account_stats, get_recent_failed_logs
from models.plan import get_plan
from worker.utils import is_night_mode

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
            await handle_status(client, user_id, message, text)
            return True
        elif cmd == ".stats":
            await handle_stats(client, user_id, message)
            return True
        elif cmd == ".userstatus":
            await handle_userstatus(client, user_id, message, text)
            return True
        elif cmd == ".addplan":
            await handle_addplan(client, user_id, message, text)
            return True
        elif cmd == ".rmpaused":
            await handle_rmpaused(client, user_id, message)
            return True
        elif cmd == ".groups":
            await handle_groups(client, user_id, message)
            return True
        elif cmd == ".resume" or cmd == ".unpause":
            await handle_resume(client, user_id, message)
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
        elif cmd == ".nightmode":
            await handle_nightmode(client, user_id, message, text)
            return True
        elif cmd == ".folders":
            await handle_folders(client, user_id, message)
            return True
        elif cmd == ".addfolder":
            await handle_addfolder(client, user_id, message, text)
            return True
    except Exception as e:
        logger.error(f"[User {user_id}] Command error: {e}")
        await reply_to_command(client, message, f"Error: {str(e)}")
    
    return False


async def reply_to_command(client: TelegramClient, message, text: str):
    """Send a reply to the message that triggered the command, auto-delete after 30s."""
    import asyncio
    reply = await message.reply(text)
    
    async def _auto_delete():
        await asyncio.sleep(30)
        try:
            await reply.delete()
            await message.delete()
        except Exception:
            pass  # Message may already be deleted
    
    asyncio.create_task(_auto_delete())


async def handle_help(client: TelegramClient, user_id: int, message):
    """Handle .help command with professional styling."""
    from core.config import MIN_INTERVAL_MINUTES
    text = (
        "📘 *BOT WORKER COMMANDS* 📘\n\n"
        "👥 *GROUP MANAGEMENT*\n"
        "🔸 `.addgroup <url>` — Add to forward list\n"
        "🔸 `.addfolder <name>` — Add all groups from folder\n"
        "🔸 `.rmgroup <url/idx>` — Remove from list\n"
        "🔸 `.groups` — Show your active groups\n"
        "🔸 `.folders` — List your Telegram folders\n\n"
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
        "🔸 `.userstatus <id>` — Check any user's plan\n"
        "🔸 `.addplan <id> <week/month/days>` — Grant plan\n"
        "🔸 `.nightmode on/off/auto` — Global control\n\n"
        "💡 *PRO TIP:* You can add multiple groups at once!\n"
        "Example: `.addgroup @group1 @group2`"
    ).format(min=MIN_INTERVAL_MINUTES)
    
    await reply_to_command(client, message, text)


async def handle_status(client: TelegramClient, user_id: int, message, text: str = ""):
    """Handle .status command with detailed information for THIS or ANOTHER account."""
    from core.config import OWNER_ID
    
    target_user_id = user_id
    parts = text.split()
    
    # Owner can check other users: .status <user_id>
    if len(parts) > 1 and user_id == OWNER_ID:
        try:
            target_user_id = int(parts[1])
        except ValueError:
            pass # Use self if invalid ID
            
    # Get specifically this account's session
    phone = getattr(client, 'phone', None)
    session = await get_session(target_user_id, phone if target_user_id == user_id else None)
    
    # Get plan (User-wide)
    plan = await get_plan(target_user_id)
    
    # Get config (User-wide)
    config = await get_user_config(target_user_id)
    
    # Get groups (all groups for this user)
    groups = await get_user_groups(target_user_id)
    total_groups = len(groups)
    enabled_groups = len([g for g in groups if g.get("enabled", True)])
    
    # Format plan info
    if plan:
        from datetime import datetime
        expires = plan.get("expires_at")
        if expires and expires > datetime.utcnow():
            days_left = (expires - datetime.utcnow()).days
            hours_left = ((expires - datetime.utcnow()).seconds // 3600)
            plan_type = plan.get("plan_type", "premium").title()
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
    
    phone_display = session.get("phone", "Unknown") if session else ("Owner Check" if target_user_id != user_id else "Unknown")
    from core.config import DEFAULT_INTERVAL_MINUTES
    interval = config.get("interval_min", DEFAULT_INTERVAL_MINUTES)
    
    # Setting indicators
    send_mode = config.get("send_mode", "sequential").title()
    
    total_reach = sum(g.get("member_count", 0) for g in groups)
    
    header = "📊 *WORKER DIAGNOSTICS*" if target_user_id == user_id else f"📊 *USER PROFILE: {target_user_id}*"
    
    text = f"""{header}
    
📱 *ACCOUNT PROFILE*
├ Phone: {phone_display}
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
└ 📢 Potential Reach: {total_reach:,} members

Type `.help` for available commands
"""
    await reply_to_command(client, message, text)
    
async def handle_stats(client: TelegramClient, user_id: int, message):
    """Handle .stats command - show activity and sender health."""
    from db.models import get_account_stats, get_recent_failed_logs
    
    phone = getattr(client, 'phone', 'Unknown')
    stats = await get_account_stats(user_id, phone)
    recent_fails = await get_recent_failed_logs(user_id, phone, limit=5)
    
    today_sent = stats.get("today_sent", 0)
    today_success = stats.get("today_success", 0)
    today_rate = stats.get("today_rate", 0)
    total_sent = stats.get("total_sent", 0)
    overall_rate = stats.get("success_rate", 0)
    
    # Activity Level Badge
    if today_sent > 100: activity = "🔥 HIGH"
    elif today_sent > 10: activity = "⚡ ACTIVE"
    elif today_sent > 0: activity = "🟢 STABLE"
    else: activity = "⚪ IDLE"
    
    text = f"📈 *SENDER ACTIVITY: {phone}*\n"
    text += f"══════════════════════════\n\n"
    
    text += f"📊 *TODAY'S METRICS*\n"
    text += f"├ Activity: {activity}\n"
    text += f"├ Transmitted: {today_sent} ads\n"
    text += f"├ Successful: {today_success}\n"
    text += f"└ Success Rate: {today_rate}%\n\n"
    
    text += f"🏆 *OVERALL HEALTH*\n"
    text += f"├ Lifetime Transmissions: {total_sent}\n"
    text += f"└ Overall Delivery Rate: {overall_rate}%\n\n"
    
    if recent_fails:
        text += f"⚠️ *RECENT FAILURES*\n"
        for fail in recent_fails:
            reason = fail.get("error", "Unknown").split(":")[0][:20]
            ts = fail.get("sent_at")
            time_str = ts.strftime("%H:%M") if ts else "??"
            text += f"├ `{time_str}` — {reason}\n"
        text += "└ _Check logs for full details_\n\n"
    
    text += f"💡 Activity is tracked per account.\n"
    
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
        group_identifier, topic_id = parse_group_input(group_input)
        
        if not group_identifier:
            failed.append((group_input, "Invalid URL"))
            continue
        
        try:
            # Get the entity (group/channel)
            entity = await client.get_entity(group_identifier)
            chat_id = entity.id
            chat_title = getattr(entity, 'title', None) or getattr(entity, 'username', str(chat_id))
            
            # Get member count
            member_count = 0
            try:
                from telethon.tl.functions.channels import GetFullChannelRequest
                full_chat = await client(GetFullChannelRequest(entity))
                member_count = full_chat.full_chat.participants_count
            except Exception:
                pass
                
            # Save to database
            # Link to the current account's phone for multi-account support
            success = await add_group(
                user_id, chat_id, chat_title, 
                account_phone=getattr(client, 'phone', None), 
                member_count=member_count,
                topic_id=topic_id
            )
            
            if success:
                display_name = f"{chat_title}" + (f" (Topic {topic_id})" if topic_id else "")
                added.append(display_name)
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
    """Handle .rmgroup <number or url> [number2] ... command. Supports batch removal."""
    parts = text.split()
    if len(parts) < 2:
        await reply_to_command(client, message,
            "○ Usage: .rmgroup <number or url> [idx2] [idx3]...\n\n"
            "Examples:\n"
            "  ◦ .rmgroup 1\n"
            "  ◦ .rmgroup 1 5 10 @groupname\n\n"
            "▪ Use .groups to see your groups first."
        )
        return
    
    inputs = parts[1:]
    
    # Get user's groups (ALL groups to match numbering in .groups)
    groups = await get_user_groups(user_id)
    
    if not groups:
        await reply_to_command(client, message, "○ You have no groups in your list.")
        return
    
    removed_titles = []
    failed_inputs = []
    
    for item in inputs:
        chat_id = None
        chat_title = None
        
        # Check if index number
        if item.isdigit():
            idx = int(item)
            if 1 <= idx <= len(groups):
                group = groups[idx - 1]
                chat_id = group["chat_id"]
                chat_title = group.get("chat_title", "Unknown")
            else:
                failed_inputs.append(f"{item} (Out of range)")
                continue
        else:
            # Try to resolve url/username
            group_identifier = parse_group_input(item)
            if not group_identifier:
                failed_inputs.append(f"{item} (Invalid URL)")
                continue
                
            try:
                # Resolve entity or match by username/title in existing list
                try:
                    entity = await client.get_entity(group_identifier)
                    chat_id = entity.id
                except Exception:
                    pass
                
                # Match in existing list
                search = group_identifier.lstrip("@").lower()
                for g in groups:
                    if chat_id and g["chat_id"] == chat_id:
                        chat_id = g["chat_id"]
                        chat_title = g["chat_title"]
                        break
                    if search in g.get("chat_title", "").lower() or (g.get("chat_id") and str(g["chat_id"]) == search):
                        chat_id = g["chat_id"]
                        chat_title = g["chat_title"]
                        break
            except Exception:
                failed_inputs.append(f"{item} (Not found)")
                continue
        
        if chat_id:
            try:
                await remove_group(user_id, chat_id)
                removed_titles.append(chat_title or f"Chat {chat_id}")
            except Exception as e:
                failed_inputs.append(f"{item} ({str(e)[:15]})")
    
    # Build response
    resp = ""
    if removed_titles:
        resp += f"✅ Removed {len(removed_titles)} group(s):\n"
        for t in removed_titles:
            resp += f"  ▸ {t}\n"
            
    if failed_inputs:
        resp += f"\n❌ Failed to remove:\n"
        for f in failed_inputs:
            resp += f"  ▸ {f}\n"
            
    if not resp:
        resp = "○ No groups were removed."
    else:
        remaining = await get_group_count(user_id)
        resp += f"\n📁 Remaining: {remaining}/{MAX_GROUPS_PER_USER} slots."
        
    await reply_to_command(client, message, resp.strip())


async def handle_resume(client: TelegramClient, user_id: int, message):
    """Handle .resume command to re-enable all paused groups."""
    from models.group import resume_user_groups
    count = await resume_user_groups(user_id)
    
    if count > 0:
        await reply_to_command(client, message, f"✅ Resumed {count} group(s)!\nWorker will pick them up in the next cycle. ⚡")
    else:
        await reply_to_command(client, message, "⚪ No paused groups found to resume.")


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


async def handle_userstatus(client: TelegramClient, user_id: int, message, text: str):
    """Owner command: .userstatus <user_id>"""
    from core.config import OWNER_ID
    if user_id != OWNER_ID:
        await reply_to_command(client, message, "❌ Reserved for owner.")
        return
        
    parts = text.split()
    if len(parts) < 2:
        await reply_to_command(client, message, "○ Usage: .userstatus <user_id>")
        return
        
    try:
        target_id = int(parts[1])
        await handle_status(client, user_id, message, f".status {target_id}")
    except ValueError:
        await reply_to_command(client, message, "○ Invalid User ID.")

async def handle_addplan(client: TelegramClient, user_id: int, message, text: str):
    """Owner command: .addplan <user_id> <week/month/days>"""
    from core.config import OWNER_ID
    if user_id != OWNER_ID:
        await reply_to_command(client, message, "❌ Reserved for owner.")
        return
        
    parts = text.split()
    if len(parts) < 3:
        await reply_to_command(client, message, "○ Usage: .addplan <user_id> <week|month|3month|6month|1year|days>")
        return
        
    try:
        target_id = int(parts[1])
        duration_input = parts[2].lower()
        
        from models.plan import extend_plan, activate_plan
        from core.config import PLAN_DURATIONS
        
        if duration_input in PLAN_DURATIONS:
            await activate_plan(target_id, duration_input)
            days = PLAN_DURATIONS[duration_input]
        else:
            try:
                days = int(duration_input)
                await extend_plan(target_id, days)
            except ValueError:
                await reply_to_command(client, message, "○ Invalid duration. Use: week, month, 3month, 6month, 1year, or number of days.")
                return
                
        await reply_to_command(client, message, 
            f"✅ Plan upgraded for user {target_id}!\n"
            f"  ▸ +{days} days premium added."
        )
    except Exception as e:
        await reply_to_command(client, message, f"❌ Error: {str(e)}")

async def handle_rmpaused(client: TelegramClient, user_id: int, message):
    """Remove all paused groups."""
    groups = await get_user_groups(user_id)
    paused = [g for g in groups if not g.get("enabled", True)]
    
    if not paused:
        await reply_to_command(client, message, "⚪ No paused groups to remove.")
        return
        
    count = 0
    for g in paused:
        await remove_group(user_id, g["chat_id"])
        count += 1
        
    await reply_to_command(client, message, f"✅ Removed {count} paused group(s).")

def parse_group_input(input_str: str) -> tuple[str, Optional[int]]:
    """Parse group URL or username to identifier and optional topic ID."""
    input_str = input_str.strip()
    
    # Handle @username
    if input_str.startswith("@"):
        return input_str, None
    
    # Handle t.me links with + (newer invite links)
    if "t.me/+" in input_str or "telegram.me/+" in input_str:
        return input_str, None
    
    # Handle joinchat links
    if "joinchat/" in input_str:
        return input_str, None
    
    # Handle topic links (most important for forums)
    # https://t.me/c/12345/678 (678 is topic) or https://t.me/username/678
    topic_match = re.search(r"t\.me/(?:c/)?([a-zA-Z0-9_+%-]+)/(\d+)$", input_str)
    if topic_match:
        ident = topic_match.group(1)
        if "/c/" in input_str and ident.isdigit():
            ident = f"-100{ident}"
        elif not ident.startswith("-100") and ident.isdigit():
            ident = f"-100{ident}"
        return ident, int(topic_match.group(2))

    # Basic URL cleaning
    if "t.me/" in input_str:
        ident = input_str.split('/')[-1].split('?')[0]
        return ident, None
        
    return input_str, None
    # https://t.me/groupname/123 -> groupname
    message_link_pattern = r"(?:https?://)?(?:t\.me|telegram\.me)/(?:c/)?([a-zA-Z0-9_-]+)/(\d+)"
    match = re.match(message_link_pattern, input_str)
    if match:
        return match.group(1)

    # Handle various domain variations and protocols
    patterns = [
        r"(?:https?://)?(?:t\.me|telegram\.me|telegram\.dog)/([a-zA-Z0-9_]+)",
        r"(?:https?://)?(?:t\.me|telegram\.me)/addlist/([a-zA-Z0-9_-]+)",
        r"tg://resolve\?domain=([a-zA-Z0-9_]+)",
        r"tg://join\?invite=([a-zA-Z0-9_-]+)",
    ]
    
    for pattern in patterns:
        match = re.match(pattern, input_str)
        if match:
            if "invite=" in pattern:
                return f"https://t.me/+{match.group(1)}"
            if "addlist/" in pattern:
                return f"addlist:{match.group(1)}"
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
    # Fix: Import is_night_mode from worker.utils instead of send_logic
    from worker.utils import is_night_mode as check_night_mode
    
    settings = await get_global_settings()
    force = settings.get("night_mode_force", "auto")
    active = await check_night_mode()
    
    if force == "on":
        return "🔴 FORCED ON"
    if force == "off":
         return "🟢 FORCED OFF"
    
    return "🌙 Active (00-06 IST)" if active else "☀️ Inactive (Daytime)"


async def handle_folders(client: TelegramClient, user_id: int, message):
    """List all Telegram chat folders (filters)."""
    try:
        from telethon.tl.functions.messages import GetDialogFiltersRequest
        filters = await client(GetDialogFiltersRequest())
        
        if not filters:
            await reply_to_command(client, message, "📁 No folders found on your account.")
            return
            
        text = "📁 *YOUR TELEGRAM FOLDERS*\n"
        text += "══════════════════════════\n\n"
        
        count = 0
        for f in filters:
            if hasattr(f, 'title') and f.title:
                text += f"▪ `{f.title}`\n"
                count += 1
                
        if count == 0:
            await reply_to_command(client, message, "📁 No custom folders found.")
            return
            
        text += f"\n💡 Use `.addfolder <name>` to add all groups from a folder."
        await reply_to_command(client, message, text)
        
    except Exception as e:
        logger.error(f"Error fetching folders: {e}")
        await reply_to_command(client, message, f"❌ Error: {str(e)}")


async def handle_addfolder(client: TelegramClient, user_id: int, message, text: str):
    """Add all groups from a specific Telegram folder or Share Link."""
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        await reply_to_command(client, message, "○ Usage: `.addfolder <folder_name OR share_link>`\n\nExample: `.addfolder Crypto` or `.addfolder t.me/addlist/...`")
        return
        
    folder_input = parts[1].strip()
    
    # 1. Handle Share Links (Chatlists)
    if "t.me/addlist" in folder_input or "telegram.me/addlist" in folder_input:
        await handle_addlist_link(client, user_id, message, folder_input)
        return

    await reply_to_command(client, message, f"🔍 Searching for folder: `{folder_input}`...")
    
    try:
        filters = await client(GetDialogFiltersRequest())
        
        target_filter = None
        for f in filters:
            if hasattr(f, 'title') and f.title and f.title.lower() == folder_input.lower():
                target_filter = f
                break
                
        if not target_filter:
            await reply_to_command(client, message, f"❌ Folder `{folder_input}` not found.\n\nType `.folders` to see all available folders.")
            return
            
        # 2. Get peers from filter
        peers = getattr(target_filter, 'include_peers', [])
        
        # 3. IF NO EXPLICIT PEERS, handle FLAGS (e.g. "Groups" folder)
        if not peers:
            await reply_to_command(client, message, f"📂 Folder `{folder_input}` uses categories. Scanning dialogs...")
            peers = await fetch_peers_by_flags(client, target_filter)
            
        if not peers:
            await reply_to_command(client, message, f"⚪ Folder `{folder_input}` is empty or contains no supported groups.")
            return
            
        await process_folder_peers(client, user_id, message, folder_input, peers)
        
    except Exception as e:
        logger.error(f"Error adding folder: {e}")
        await reply_to_command(client, message, f"❌ Error: {str(e)}")

async def handle_addlist_link(client: TelegramClient, user_id: int, message, link: str):
    """Import groups from a shared folder link (Chatlist)."""
    try:
        from telethon.tl.functions.chatlists import CheckChatlistInviteRequest, JoinChatlistInviteRequest
        
        # Extract slug correctly (handle queries or trailing slashes)
        import re
        slug_match = re.search(r"addlist/([a-zA-Z0-9_-]+)", link)
        if not slug_match:
            await reply_to_command(client, message, f"❌ Invalid shared folder link.")
            return
            
        slug = slug_match.group(1)
        await reply_to_command(client, message, f"🔗 Checking shared folder link...")
        
        # Check the invite
        invite = await client(CheckChatlistInviteRequest(slug))
        
        # Handle both ChatlistInvite (new) and ChatlistInviteAlready (already joined)
        # Both have a 'chatlist' attribute but it contains different types of objects
        from telethon.tl.types.chatlists import ChatlistInviteAlready
        
        title = "Shared Folder"
        peers = []
        
        if hasattr(invite, 'chatlist'):
            title = getattr(invite.chatlist, 'title', "Shared Folder")
        
        # ChatlistInvite has 'peers'
        # ChatlistInviteAlready has 'already_peers'
        peers = getattr(invite, 'peers', []) or getattr(invite, 'already_peers', [])
        
        if not peers:
            await reply_to_command(client, message, f"⚪ Shared folder `{title}` is empty or already fully synced.")
            return
            
        await reply_to_command(client, message, f"📂 Found {len(peers)} items in shared folder `{title}`.\nImporting...")
        
        # Only Join if it's a new invite
        if not isinstance(invite, ChatlistInviteAlready):
            await client(JoinChatlistInviteRequest(slug, peers))
        
        # Now process like a folder
        await process_folder_peers(client, user_id, message, title, peers)
        
    except Exception as e:
        logger.error(f"Error adding chatlist: {e}")
        await reply_to_command(client, message, f"❌ Chatlist Error: {str(e)}")

async def fetch_peers_by_flags(client: TelegramClient, f: DialogFilter) -> list:
    """Fetch all peers matching a DialogFilter's flags."""
    peers = []
    try:
        async for dialog in client.iter_dialogs(limit=500):
            entity = dialog.entity
            is_group = isinstance(entity, (Chat, Channel)) and not getattr(entity, 'broadcast', False)
            is_broadcast = isinstance(entity, Channel) and getattr(entity, 'broadcast', False)
            
            # Match flags
            match = False
            if f.groups and (is_group or is_broadcast): match = True
            if f.broadcasts and is_broadcast: match = True
            if f.contacts and getattr(entity, 'contact', False): match = True
            if f.non_contacts and not getattr(entity, 'contact', False) and not getattr(entity, 'bot', False) and not entity.is_self: match = True
            
            # Exclusions (basic)
            if match:
                if f.exclude_muted and dialog.dialog.notify_settings.silent: match = False
                if f.exclude_read and dialog.unread_count == 0: match = False
                if f.exclude_archived and dialog.archived: match = False
                
            if match:
                peers.append(entity)
    except Exception as e:
        logger.warning(f"Error fetching peers by flags: {e}")
    return peers

async def process_folder_peers(client, user_id, message, folder_name, peers):
    """Common logic to resolve and add multiple peers from a foldery source."""
    # Check current group count
    count = await get_group_count(user_id)
    available_slots = MAX_GROUPS_PER_USER - count
    
    if available_slots <= 0:
        await reply_to_command(client, message, f"❌ Maximum groups ({MAX_GROUPS_PER_USER}) reached.")
        return
        
    added = []
    failed = []
    
    # Limit to available slots
    to_process = peers
    if len(peers) > available_slots:
        to_process = peers[:available_slots]
        await reply_to_command(client, message, f"⚠️ Only {available_slots} slots available. Skipping remaining {len(peers)-available_slots}...")
        
    for peer in to_process:
        try:
            # Resolve entity if it's not already resolved
            if isinstance(peer, (Channel, Chat)):
                entity = peer
            else:
                entity = await client.get_entity(peer)
            
            # We only want groups or channels
            if not isinstance(entity, (Channel, Chat)):
                continue
                
            chat_id = entity.id
            chat_title = entity.title
            
            # Get member count
            member_count = 0
            try:
                from telethon.tl.functions.channels import GetFullChannelRequest
                full_chat = await client(GetFullChannelRequest(entity))
                member_count = full_chat.full_chat.participants_count
            except Exception:
                pass
            
            success = await add_group(user_id, chat_id, chat_title, account_phone=getattr(client, 'phone', None), member_count=member_count)
            if success:
                added.append(chat_title)
            else:
                failed.append(chat_title)
                
        except Exception as e:
            logger.warning(f"Failed to add peer: {e}")
            
    # Final response
    res = f"✅ *IMPORT COMPLETE*\n"
    res += f"📁 Source: `{folder_name}`\n"
    res += f"🎯 Added: {len(added)}\n"
    
    if failed:
        res += f"❌ Skip (exists): {len(failed)}\n"
        
    new_total = await get_group_count(user_id)
    res += f"\nTotal Groups: {new_total}/{MAX_GROUPS_PER_USER}"
    
    await reply_to_command(client, message, res)
