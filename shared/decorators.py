"""
Subscription check decorators for Group Message Scheduler.
"""

from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes

from core.config import OWNER_ID
from models.plan import is_plan_active
from main_bot.utils.keyboards import get_subscription_required_keyboard

def require_premium(func):
    """
    Decorator to restrict access to premium-only features.
    Allows access if user is the owner OR has an active plan.
    """
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        
        # 1. Bypass check for owner
        if user_id == OWNER_ID:
            return await func(update, context, *args, **kwargs)
            
        # 2. Check if plan is active
        active = await is_plan_active(user_id)
        if active:
            return await func(update, context, *args, **kwargs)
            
        # 3. Access denied - send subscription required message
        text = """
⚠️ *PREMIUM ACCESS REQUIRED* ⚠️

This feature is reserved for *Paid Subscribers* only. To continue using the bot, please purchase a plan or redeem a promo code.

💎 *Perks of Premium:*
• Unlimited group messaging
• 24/7 automated delivery
• Multi-account support
• Anti-flood protection

👇 *Choose an option below to unlock:*
"""
        # If it's a callback query
        if update.callback_query:
            await update.callback_query.answer("Subscription required!", show_alert=True)
            await update.callback_query.edit_message_text(
                text,
                parse_mode="Markdown",
                reply_markup=get_subscription_required_keyboard()
            )
        else:
            # If it's a command
            await update.message.reply_text(
                text,
                parse_mode="Markdown",
                reply_markup=get_subscription_required_keyboard()
            )
        return None
        
    return wrapper
