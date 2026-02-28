"""
Dashboard handler for Main Bot.
"""

from telegram import Update
from telegram.ext import ContextTypes

from db.models import get_all_user_sessions, get_plan, get_user_config, get_group_count, get_account_stats
from main_bot.utils.keyboards import get_dashboard_keyboard, get_add_account_keyboard
from config import MIN_INTERVAL_MINUTES
import datetime


def format_last_active(dt: datetime.datetime) -> str:
    """Format datetime as relative 'N m/h/d ago'."""
    if not dt:
        return "Never"
    
    now = datetime.datetime.utcnow()
    diff = now - dt
    
    if diff.total_seconds() < 60:
        return "Just now"
    if diff.total_seconds() < 3600:
        return f"{int(diff.total_seconds() // 60)}m ago"
    if diff.total_seconds() < 86400:
        return f"{int(diff.total_seconds() // 3600)}h ago"
    
    return f"{diff.days}d ago"


def format_expiry_date(dt: datetime.datetime) -> str:
    """Format expiry date as a readable string."""
    if not dt:
        return "N/A"
    return dt.strftime("%d %b %Y, %I:%M %p")


async def show_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the main dashboard."""
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "User"
    
    # Get user data
    sessions = await get_all_user_sessions(user_id)
    plan = await get_plan(user_id)
    config = await get_user_config(user_id)
    group_count = await get_group_count(user_id)
    
    # ═══ Build account section ═══
    account_section = ""
    total_sends = 0
    if sessions:
        for idx, s in enumerate(sessions, 1):
            status_icon = "🟢" if s.get("connected") else "🔴"
            phone = s.get("phone", "Unknown")
            stats = await get_account_stats(user_id, phone)
            
            last_active = format_last_active(stats["last_active"])
            rate = stats["success_rate"]
            sends = stats.get("total_sent", 0)
            total_sends += sends
            
            account_section += f"  {status_icon} `{phone}`\n"
            account_section += f"     ├─ 📊 Sent: {sends} ▪ Rate: {rate}%\n"
            account_section += f"     └─ ⏱️ Active: {last_active}\n"
    else:
        account_section = "  ○ No accounts connected\n  └─ Tap *Add Account* below"
    
    # ═══ Plan badge ═══
    if plan:
        if plan.get("status") == "active":
            plan_type = plan.get("plan_type", "trial").title()
            days_left = (plan["expires_at"] - datetime.datetime.utcnow()).days
            hours_left = ((plan["expires_at"] - datetime.datetime.utcnow()).seconds // 3600)
            expiry_date = format_expiry_date(plan["expires_at"])
            
            if plan_type.lower() == "trial":
                plan_badge = "🏅 TRIAL"
            else:
                plan_badge = "💎 PREMIUM"
            
            if days_left > 0:
                plan_status = f"{plan_badge} ▪ {days_left}d {hours_left}h left"
            else:
                plan_status = f"{plan_badge} ▪ {hours_left}h left"
            
            plan_line2 = f"     └─ 📅 Expires: {expiry_date}"
        else:
            plan_status = "🔴 EXPIRED"
            plan_line2 = "     └─ Redeem a code to reactivate!"
    else:
        plan_status = "⚪ NO PLAN"
        plan_line2 = "     └─ Connect an account for *7 days FREE!*"
    
    # ═══ Forwarding status ═══
    has_connected = any(s.get("connected") for s in sessions) if sessions else False
    if has_connected and group_count > 0 and plan and plan.get("status") == "active":
        fwd_status = "🟢 *ACTIVE*"
    elif has_connected and group_count == 0:
        fwd_status = "🟡 *NO GROUPS*"
    elif not has_connected:
        fwd_status = "🔴 *NO ACCOUNT*"
    else:
        fwd_status = "🔴 *PAUSED*"
    
    interval = config.get("interval_min", MIN_INTERVAL_MINUTES)
    
    # ═══ Settings section ═══
    copy_icon = "🟢" if config.get("copy_mode") else "⚫"
    shuffle_icon = "🟢" if config.get("shuffle_mode") else "⚫"
    responder_icon = "🟢" if config.get("auto_reply_enabled") else "⚫"
    reply_text = config.get("auto_reply_text", "")
    reply_preview = reply_text[:25] + "..." if len(reply_text) > 25 else reply_text
    
    dashboard_text = f"""
📊 *DASHBOARD* — {user_name}

📱 *ACCOUNTS* ({len(sessions) if sessions else 0})
{account_section}

🏷️ *SUBSCRIPTION*
  ➤ {plan_status}
{plan_line2}

📤 *FORWARDING:* {fwd_status}
  ➤ Groups: {group_count} ▪ Total Sent: {total_sends}
  ➤ Interval: {interval} min ▪ Night: 12-6 AM

⚙️ *SETTINGS*
  {copy_icon} Copy Mode ▪ {shuffle_icon} Shuffle
  {responder_icon} Responder: _{reply_preview}_

💡 *TIP:* Send `.addgroup <url>` in Saved Messages!
"""
    
    # Determine how to respond
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            dashboard_text,
            parse_mode="Markdown",
            reply_markup=get_dashboard_keyboard(),
        )
    else:
        await update.message.reply_text(
            dashboard_text,
            parse_mode="Markdown",
            reply_markup=get_dashboard_keyboard(),
        )


async def dashboard_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle dashboard callback."""
    await show_dashboard(update, context)


async def add_account_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show add account screen."""
    query = update.callback_query
    await query.answer()
    
    text = """
🔗 *CONNECT YOUR ACCOUNT*

Securely link your Telegram account
to start auto-forwarding messages.

✅ 256-bit encrypted session
✅ Your API credentials only
✅ Disconnect anytime

👇 *Tap below to continue to Login Bot*
"""
    
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_add_account_keyboard(),
    )
