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
🎁 *YOUR PLAN*
━━━━━━━━━━━━━━━━━━━━━━━━

🔴 *STATUS:* No active plan

🚀 *GET STARTED*

➳ Connect your account
   → Get *7 DAYS FREE!*
➳ Or redeem a code

━━━━ 💰 *PRICING* 💰 ━━━━

❊ *WEEKLY* — ₹99
❊ *MONTHLY* — ₹299
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
                
                if days_left > 0:
                    time_left = f"{days_left} days"
                else:
                    time_left = f"{hours_left} hours"
                
                status_icon = "🟢"
                status_text = "ACTIVE"
                time_display = f"⏳ Expires in: {time_left}"
                
                # Create visual progress bar
                max_days = 30 if plan_type.lower() == "month" else 7
                progress = min(days_left / max_days, 1.0)
                filled = int(progress * 10)
                bar = "▓" * filled + "░" * (10 - filled)
            else:
                status_icon = "🔴"
                status_text = "EXPIRED"
                time_display = "⚠️ Plan has expired!"
                bar = "░" * 10
        else:
            status_icon = "⚪"
            status_text = "Unknown"
            time_display = ""
            bar = "░" * 10
        
        text = f"""
🎁 *YOUR PLAN*
━━━━━━━━━━━━━━━━━━━━━━━━

{status_icon} *STATUS:* {status_text}

📋 *CURRENT PLAN*

🏷️ Type: {plan_type}
{time_display}
[{bar}]

━━━━ 💰 *EXTEND PLAN* 💰 ━━━━

📅 *WEEKLY* — ₹99 (+7 days)
📅 *MONTHLY* — ₹299 (+30 days)

━━━━━━━━━━━━━━━━━━━━━━━━
💡 Invite 3 friends → *+7 days FREE!*
"""
    
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_plan_keyboard(),
    )
