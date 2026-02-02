"""
Dashboard handler for Main Bot.
"""

from telegram import Update
from telegram.ext import ContextTypes

from db.models import get_session, get_plan, get_user_config, get_group_count
from main_bot.utils.keyboards import get_dashboard_keyboard, get_add_account_keyboard
from config import MIN_INTERVAL_MINUTES


async def show_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the main dashboard."""
    user_id = update.effective_user.id
    
    # Get user data
    session = await get_session(user_id)
    plan = await get_plan(user_id)
    config = await get_user_config(user_id)
    group_count = await get_group_count(user_id)
    
    # Build status strings
    if session and session.get("connected"):
        account_status = "Connected ✅"
    else:
        account_status = "Not Connected ❌"
    
    # Plan status
    if plan:
        if plan.get("status") == "active":
            plan_type = plan.get("plan_type", "trial").title()
            days_left = (plan["expires_at"] - __import__("datetime").datetime.utcnow()).days
            plan_status = f"{plan_type} ({days_left} days left)"
        else:
            plan_status = "Expired ❌"
    else:
        plan_status = "No Plan"
    
    interval = config.get("interval_min", MIN_INTERVAL_MINUTES)
    
    dashboard_text = f"""
📊 *Group Message Scheduler — Dashboard*

👤 *Account:* {account_status}
🎁 *Plan:* {plan_status}
🌙 *Night Mode:* 00:00–06:00 IST (Fixed)
📩 *Mode:* Auto-forward NEW Saved Messages ✅
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
🔐 *Connect Your Telegram Account*

To send messages from your own account,
please connect securely via the Login Bot.

After successful login, you'll return here automatically ✅
"""
    
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_add_account_keyboard(),
    )
