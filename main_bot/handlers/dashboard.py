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


async def show_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the main dashboard."""
    user_id = update.effective_user.id
    
    # Get user data
    sessions = await get_all_user_sessions(user_id)
    plan = await get_plan(user_id)
    config = await get_user_config(user_id)
    group_count = await get_group_count(user_id)
    
    # Build account list
    account_lines = ""
    if sessions:
        for s in sessions:
            status_icon = "●" if s.get("connected") else "○"
            phone = s.get("phone", "Unknown")
            stats = await get_account_stats(user_id, phone)
            
            last_active = format_last_active(stats["last_active"])
            rate = stats["success_rate"]
            
            # Professional formatting: [Status] Phone | Active: time | Success: %
            account_lines += f"   {status_icon} `{phone}`\n"
            account_lines += f"   └─ Active: {last_active} ▪ Rate: {rate}%\n"
    else:
        account_lines = "   ○ No accounts connected"
    
    # Plan status
    if plan:
        if plan.get("status") == "active":
            plan_type = plan.get("plan_type", "trial").title()
            days_left = (plan["expires_at"] - __import__("datetime").datetime.utcnow()).days
            plan_status = f"{plan_type} ({days_left} days left)"
        else:
            plan_status = "Expired ○"
    else:
        plan_status = "No Plan"
    
    interval = config.get("interval_min", MIN_INTERVAL_MINUTES)
    
    # Dynamic status icons
    has_connected = any(s.get("connected") for s in sessions) if sessions else False
    account_icon = "●" if has_connected else "○"
    plan_icon = "●" if plan and plan.get("status") == "active" else "○"
    
    dashboard_text = f"""
■ *DASHBOARD*
━━━━━━━━━━━━━━━━━━━━━━━━

● *ACCOUNTS*
{account_lines}

{plan_icon} *SUBSCRIPTION*
   ➤ {plan_status}

● *SETTINGS*
   ➤ Copy Mode: {"● ON" if config.get("copy_mode") else "○ OFF"}
   ➤ Shuffle Mode: {"● ON" if config.get("shuffle_mode") else "○ OFF"}
   ➤ Responder: {"● ON" if config.get("auto_reply_enabled") else "○ OFF"}
     └Msg: "{config.get("auto_reply_text", "")[:20]}..."
   ➤ Auto-forward: ● Active
   ➤ Interval: {interval} min
   ➤ Night Mode: 00:00-06:00

━━━━━━━━━━━━━━━━━━━━━━━━
▪ TIP: Send `.addgroup <url>` in Saved Messages!
▪ TIP: Send `.responder <msg>` to set auto-reply!
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
■ *Connect Your Telegram Account*

To send messages from your own account,
please connect securely via the Login Bot.

After successful login, you'll return here automatically ●
"""
    
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_add_account_keyboard(),
    )
