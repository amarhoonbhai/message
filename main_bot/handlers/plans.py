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
Connect your Telegram account to get started!

📅 *WEEKLY PRO* — ₹99
🏆 *MONTHLY ULTRA* — ₹299
🌟 *3 MONTHS* — ₹799
👑 *6 MONTHS* — ₹1499
☄️ *1 YEAR* — ₹2499

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
                
                badge = "💎"
                
                # Create visual progress bar
                from config import PLAN_DURATIONS
                max_days = PLAN_DURATIONS.get(plan.get("tier", "month"), 30)
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
🌟 *3 MONTHS* — ₹799 (+90 days)
👑 *6 MONTHS* — ₹1499 (+180 days)
☄️ *1 YEAR* — ₹2499 (+365 days)
"""
    
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_plan_keyboard(),
    )


async def buy_plan_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle buy plan button clicks."""
    query = update.callback_query
    await query.answer()
    
    plan_type = query.data.split(":")[1]
    price = PLAN_PRICES.get(plan_type, 0)
    
    from config import PLAN_DURATIONS
    days = PLAN_DURATIONS.get(plan_type, 0)
    
    text = f"""
💳 *UPGRADE TO {plan_type.upper()} PRO*
══════════════════════════════

💎 *Tier:* {plan_type.upper()}
💰 *Price:* ₹{price}
⏳ *Validity:* {days} Days

🚀 *HOW TO ACTIVATE:*
1. Send ₹{price} via UPI to: `spinify@ybl`
2. Take a screenshot of the transaction.
3. Send the screenshot to @spinify along with your User ID: `{update.effective_user.id}`

_Your plan will be activated within 30 minutes of verification._
"""
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_back_home_keyboard()
    )
