"""
Plans display handler for Main Bot.
"""

from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes

from db.models import get_plan
from main_bot.utils.keyboards import get_plan_keyboard, get_back_home_keyboard
from config import PLAN_PRICES


def format_expiry_date(dt: datetime) -> str:
    if not dt:
        return "N/A"
    return dt.strftime("%d %b %Y, %I:%M %p UTC")


async def my_plan_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's plan status."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    plan = await get_plan(user_id)
    
    if not plan:
        text = """
💳 *SUBSCRIPTION & PLANS*

⚪ *STATUS:* NO ACTIVE PLAN

🚀 *UNLOCK PREMIUM AUTO-FORWARDING*
Connect your Telegram account to instantly receive *7 DAYS FREE TRIAL!*

💰 *PRICING TIERS*

📅 *WEEKLY PRO* — ₹99
└ 7 days of uninterrupted service

🏆 *MONTHLY ULTRA* — ₹299
└ 30 days — Best value!

💡 *TIP:* Have a promo code? Tap Redeem below!
"""
    else:
        plan_type = plan.get("plan_type", "trial").upper()
        status = plan.get("status", "unknown").upper()
        expires_at = plan.get("expires_at")
        
        if expires_at:
            now = datetime.utcnow()
            if expires_at > now:
                days_left = (expires_at - now).days
                hours_left = ((expires_at - now).seconds // 3600)
                
                if days_left > 0:
                    time_left = f"{days_left}d {hours_left}h"
                else:
                    time_left = f"{hours_left}h"
                
                status_icon = "🟢"
                status_text = "ACTIVE"
                time_display = f"⏳ Expires in: *{time_left}*"
                
                badge = "🏅" if plan_type == "TRIAL" else "💎"
                
                # Create visual progress bar
                max_days = 30 if plan_type == "MONTH" else 7
                progress = min(days_left / max_days, 1.0)
                filled = int(progress * 10)
                bar = "█" * filled + "▒" * (10 - filled)
            else:
                status_icon = "🔴"
                status_text = "EXPIRED"
                time_display = "⚠️ *Your plan has expired!*"
                bar = "▒" * 10
                badge = "⚠️"
        else:
            status_icon = "⚪"
            status_text = "UNKNOWN"
            time_display = ""
            bar = "▒" * 10
            badge = "❓"
            
        expiry_date = format_expiry_date(expires_at)
        
        text = f"""
💳 *SUBSCRIPTION DASHBOARD*

{status_icon} *STATUS:* {status_text}

📋 *CURRENT PLAN DETAILS*
{badge} *Type:* {plan_type}
{time_display}
📅 *Valid till:* {expiry_date}

[{bar}]

💰 *EXTEND YOUR SUBSCRIPTION*

📅 *WEEKLY PRO* — ₹99 (+7 days)
🏆 *MONTHLY ULTRA* — ₹299 (+30 days)

💡 invite 3 friends → *+7 days FREE!*
"""
    
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_plan_keyboard(),
    )
