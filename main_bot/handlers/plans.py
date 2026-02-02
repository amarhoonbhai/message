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
🎁 *Your Plan*

You don't have an active plan yet.

*How to get started:*
1️⃣ Connect your account to get a *7-day free trial*
2️⃣ Or redeem a code if you have one

*Pricing:*
• Weekly: ₹99
• Monthly: ₹299
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
                
                status_emoji = "✅"
                status_text = f"Active ({time_left} left)"
            else:
                status_emoji = "❌"
                status_text = "Expired"
        else:
            status_emoji = "❓"
            status_text = "Unknown"
        
        text = f"""
🎁 *Your Plan*

📋 *Type:* {plan_type}
{status_emoji} *Status:* {status_text}

*Extend your plan:*
• Weekly: ₹99 (+7 days)
• Monthly: ₹299 (+30 days)

Use 🧾 Redeem Code if you have a code.
Or invite 3 friends to earn +7 free days! 🤝
"""
    
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_plan_keyboard(),
    )
