"""
Plans display handler for Main Bot.
"""

from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes

from db.models import get_plan
from main_bot.utils.keyboards import get_plan_keyboard, get_back_home_keyboard
from config import PLAN_PRICES


async def my_plan_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's plan status."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    plan = await get_plan(user_id)
    
    if not plan:
        text = """
🏷️ *MY PLAN*
╔══════════════════════════╗

⚪ *STATUS:* No Active Plan

╚══════════════════════════╝

🚀 *GET STARTED*

  ➳ Connect your account
     → Get *7 DAYS FREE!* 🎉
  ➳ Or redeem a premium code

━━━━ 💰 *PRICING* 💰 ━━━━

  ┌─────────────────────────┐
  │  📅 *WEEKLY*  — ₹99  (+7 days)  │
  │  📅 *MONTHLY* — ₹299 (+30 days) │
  └─────────────────────────┘

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 Invite 3 friends → *+7 days FREE!*
"""
    else:
        plan_type = plan.get("plan_type", "trial").title()
        status = plan.get("status", "unknown").title()
        expires_at = plan.get("expires_at")
        
        if expires_at:
            now = datetime.utcnow()
            if expires_at > now:
                days_left = (expires_at - now).days
                hours_left = ((expires_at - now).seconds // 3600)
                expiry_date = expires_at.strftime("%d %b %Y, %I:%M %p")
                
                if days_left > 0:
                    time_left = f"{days_left}d {hours_left}h"
                else:
                    time_left = f"{hours_left}h"
                
                status_icon = "🟢"
                status_text = "ACTIVE"
                
                # Plan badge
                if plan_type.lower() == "trial":
                    plan_badge = "🏅 TRIAL"
                else:
                    plan_badge = "💎 PREMIUM"
                
                # Visual progress bar
                max_days = 30 if plan_type.lower() == "month" else 7
                progress = min(days_left / max_days, 1.0)
                filled = int(progress * 10)
                bar = "▓" * filled + "░" * (10 - filled)
                percent = int(progress * 100)
            else:
                status_icon = "🔴"
                status_text = "EXPIRED"
                plan_badge = "⚠️ EXPIRED"
                time_left = "Expired"
                expiry_date = expires_at.strftime("%d %b %Y, %I:%M %p")
                bar = "░" * 10
                percent = 0
        else:
            status_icon = "⚪"
            status_text = "Unknown"
            plan_badge = "❓ Unknown"
            time_left = "N/A"
            expiry_date = "N/A"
            bar = "░" * 10
            percent = 0
        
        text = f"""
🏷️ *MY PLAN*
╔══════════════════════════╗

{status_icon} *{plan_badge}*

╚══════════════════════════╝

📋 *PLAN DETAILS*

  ▸ Type: *{plan_type}*
  ▸ Status: *{status_text}*
  ▸ Time Left: *{time_left}*
  ▸ Expires: _{expiry_date}_

  [{bar}] {percent}%

━━━━ 💰 *EXTEND PLAN* 💰 ━━━━

  ┌─────────────────────────┐
  │  📅 *WEEKLY*  — ₹99  (+7 days)  │
  │  📅 *MONTHLY* — ₹299 (+30 days) │
  └─────────────────────────┘

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 Invite 3 friends → *+7 days FREE!*
"""
    
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_plan_keyboard(),
    )
