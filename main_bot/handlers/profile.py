"""
Profile handler for Main Bot.
Displays user profile with Telegram info, plan, and account statistics.
"""

from telegram import Update
from telegram.ext import ContextTypes

from db.models import get_user_profile_data, get_plan
from main_bot.utils.keyboards import get_profile_keyboard
from main_bot.utils.helpers import escape_markdown
import datetime


async def profile_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle profile button callback — show user profile card."""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    user_id = user.id
    first_name = user.first_name or "User"
    last_name = user.last_name or ""
    username = escape_markdown(f"@{user.username}" if user.username else "Not set")
    full_name = escape_markdown(f"{first_name} {last_name}".strip())

    # Fetch aggregated profile data
    data = await get_user_profile_data(user_id)

    # Plan info
    plan = data.get("plan")
    if plan and plan.get("status") == "active":
        plan_type = plan.get("plan_type", "trial").title()
        days_left = (plan["expires_at"] - datetime.datetime.utcnow()).days
        hours_left = (plan["expires_at"] - datetime.datetime.utcnow()).seconds // 3600

        if plan_type.lower() == "trial":
            plan_badge = "TRIAL"
        else:
            plan_badge = "PREMIUM"

        if days_left > 0:
            plan_line = f"{plan_badge} -- {days_left}d {hours_left}h left"
        else:
            plan_line = f"{plan_badge} -- {hours_left}h left"
    elif plan:
        plan_line = "EXPIRED"
    else:
        plan_line = "No Plan"

    # Sessions
    sessions = data.get("sessions", [])
    accounts_count = len(sessions)

    # Stats
    total_sent = data.get("total_sent", 0)
    success_rate = data.get("success_rate", 0)
    total_groups = data.get("total_groups", 0)
    enabled_groups = data.get("enabled_groups", 0)

    # Config
    config = data.get("config", {})
    copy_mode = "ON" if config.get("copy_mode") else "OFF"
    shuffle_mode = "ON" if config.get("shuffle_mode") else "OFF"
    responder = "ON" if config.get("auto_reply_enabled") else "OFF"

    # Referral
    user_data = data.get("user")
    referral_code = user_data.get("referral_code", "N/A") if user_data else "N/A"
    referrals_count = user_data.get("referrals_count", 0) if user_data else 0

    profile_text = f"""
*YOUR PROFILE*

*Name:* {full_name}
*Username:* {username}
*User ID:* `{user_id}`

*SUBSCRIPTION*
  Plan: {plan_line}

*ACCOUNTS:* {accounts_count} connected
*GROUPS:* {enabled_groups}/{total_groups} active

*FORWARDING STATS*
  Total Sent: {total_sent}
  Success Rate: {success_rate}%

*SETTINGS*
  Copy Mode: {copy_mode}
  Shuffle: {shuffle_mode}
  Responder: {responder}

*REFERRALS*
  Code: `{referral_code}`
  Invited: {referrals_count} users
"""

    await query.edit_message_text(
        profile_text,
        parse_mode="Markdown",
        reply_markup=get_profile_keyboard(),
    )
