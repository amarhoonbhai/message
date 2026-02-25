"""
Profile handler for Main Bot — consolidated user info screen.
"""

from telegram import Update
from telegram.ext import ContextTypes
from datetime import datetime

from db.models import get_user_profile_data
from main_bot.utils.keyboards import get_profile_keyboard
from config import (
    DEFAULT_INTERVAL_MINUTES, REFERRALS_NEEDED,
    MAIN_BOT_USERNAME, MAX_GROUPS_PER_USER
)


def _format_date(dt: datetime) -> str:
    """Format datetime as readable date string."""
    if not dt:
        return "N/A"
    return dt.strftime("%d %b %Y")


def _format_last_active(dt: datetime) -> str:
    """Format datetime as relative time."""
    if not dt:
        return "Never"
    now = datetime.utcnow()
    diff = now - dt
    if diff.total_seconds() < 60:
        return "Just now"
    if diff.total_seconds() < 3600:
        return f"{int(diff.total_seconds() // 60)}m ago"
    if diff.total_seconds() < 86400:
        return f"{int(diff.total_seconds() // 3600)}h ago"
    return f"{diff.days}d ago"


def _build_progress_bar(current: int, total: int, length: int = 10) -> str:
    """Build a text progress bar."""
    if total <= 0:
        return "░" * length
    filled = min(int(current / total * length), length)
    return "▓" * filled + "░" * (length - filled)


async def profile_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the user's full profile card."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "User"
    username = update.effective_user.username
    
    # Fetch aggregated profile data
    data = await get_user_profile_data(user_id)
    
    user = data["user"]
    plan = data["plan"]
    sessions = data["sessions"]
    config = data["config"]
    
    # ═══ User Info ═══
    member_since = _format_date(user.get("created_at")) if user else "Unknown"
    user_display = f"@{username}" if username else user_name
    
    # ═══ Plan Section ═══
    if plan:
        plan_type = plan.get("plan_type", "trial").title()
        expires = plan.get("expires_at")
        if plan.get("status") == "active" and expires and expires > datetime.utcnow():
            days_left = (expires - datetime.utcnow()).days
            hours_left = (expires - datetime.utcnow()).seconds // 3600
            expiry_str = expires.strftime("%d %b %Y, %I:%M %p")
            
            if plan_type.lower() == "trial":
                plan_badge = "🏅 TRIAL"
            else:
                plan_badge = "💎 PREMIUM"
            
            if days_left > 0:
                time_left = f"{days_left}d {hours_left}h"
            else:
                time_left = f"{hours_left}h"
            
            # Calculate plan age for progress bar
            created = plan.get("created_at", datetime.utcnow())
            total_secs = (expires - created).total_seconds()
            remaining_secs = (expires - datetime.utcnow()).total_seconds()
            used_pct = max(0, min(100, int((1 - remaining_secs / total_secs) * 100))) if total_secs > 0 else 0
            bar = _build_progress_bar(used_pct, 100)
            
            plan_section = f"""  ▸ {plan_badge} — {plan_type}
  ▸ 🟢 Active — {time_left} left
  ▸ 📅 Expires: {expiry_str}
  [{bar}] {used_pct}% used"""
        else:
            plan_section = "  ▸ 🔴 EXPIRED\n  ▸ Redeem a code to reactivate!"
    else:
        plan_section = "  ▸ ⚪ NO PLAN\n  ▸ Connect an account for 7 days FREE!"
    
    # ═══ Accounts Section ═══
    acc_count = len(sessions) if sessions else 0
    if sessions:
        acc_lines = []
        for s in sessions:
            phone = s.get("phone", "???")
            status = "🟢" if s.get("connected") else "🔴"
            sent = s.get("stats_total", 0)
            success = s.get("stats_success", 0)
            rate = round(success / sent * 100, 1) if sent > 0 else 0
            acc_lines.append(f"  {status} `{phone}` — {sent} sent ({rate}%)")
        acc_section = "\n".join(acc_lines)
    else:
        acc_section = "  ○ No accounts connected"
    
    # ═══ Groups Section ═══
    total_groups = data["total_groups"]
    enabled_groups = data["enabled_groups"]
    disabled = total_groups - enabled_groups
    groups_bar = _build_progress_bar(total_groups, MAX_GROUPS_PER_USER, 8)
    groups_section = f"  ▸ {enabled_groups} active"
    if disabled > 0:
        groups_section += f" ▪ {disabled} paused"
    groups_section += f"\n  [{groups_bar}] {total_groups}/{MAX_GROUPS_PER_USER} slots"
    
    # ═══ Settings Section ═══
    interval = config.get("interval_min", DEFAULT_INTERVAL_MINUTES)
    copy_icon = "🟢 ON" if config.get("copy_mode") else "⚫ OFF"
    shuffle_icon = "🟢 ON" if config.get("shuffle_mode") else "⚫ OFF"
    responder_icon = "🟢 ON" if config.get("auto_reply_enabled") else "⚫ OFF"
    reply_text = config.get("auto_reply_text", "")
    reply_preview = reply_text[:20] + "…" if len(reply_text) > 20 else reply_text
    
    # ═══ Referral Section ═══
    referral_code = user.get("referral_code", "N/A") if user else "N/A"
    referrals_count = user.get("referrals_count", 0) if user else 0
    bonus_applied = user.get("referral_bonus_applied", False) if user else False
    ref_dots = "🟢" * min(referrals_count, REFERRALS_NEEDED) + "⚪" * max(0, REFERRALS_NEEDED - referrals_count)
    
    if bonus_applied:
        ref_status = "🎉 Bonus Claimed!"
    elif referrals_count >= REFERRALS_NEEDED:
        ref_status = "🏆 Bonus Ready!"
    else:
        ref_status = f"{referrals_count}/{REFERRALS_NEEDED} friends"
    
    ref_link = f"https://t.me/{MAIN_BOT_USERNAME}?start=ref_{referral_code}"
    
    # ═══ Activity Section ═══
    total_sent = data["total_sent"]
    success_rate = data["success_rate"]
    last_active = _format_last_active(data["last_active"])
    
    # ═══ Build the full profile ═══
    text = f"""
👤 *MY PROFILE*
╔══════════════════════════╗
║    ★ {user_display} ★    ║
╚══════════════════════════╝

🆔 *USER INFO*
  ▸ ID: `{user_id}`
  ▸ Member Since: {member_since}

🏷️ *PLAN*
{plan_section}

📱 *ACCOUNTS* ({acc_count})
{acc_section}

📁 *GROUPS* ({total_groups})
{groups_section}

⚙️ *SETTINGS*
  ▸ Interval: {interval} min
  ▸ Copy Mode: {copy_icon}
  ▸ Shuffle: {shuffle_icon}
  ▸ Responder: {responder_icon}
  ▸ Reply: _{reply_preview}_

🔗 *REFERRAL*
  ▸ {ref_dots} {ref_status}
  ▸ Link: `{ref_link}`

📊 *ACTIVITY*
  ▸ Total Sent: {total_sent}
  ▸ Success Rate: {success_rate}%
  ▸ Last Active: {last_active}

━━━━━━━━━━━━━━━━━━━━━━━━━━━
💬 *SUPPORT:* @PHilobots
"""
    
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_profile_keyboard(),
    )
