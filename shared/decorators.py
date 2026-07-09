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


def require_channel_join(func):
    """
    Decorator to restrict access to users who have joined the official channel.
    Bypasses check for owner.
    """
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if not user:
            return await func(update, context, *args, **kwargs)
            
        user_id = user.id
        
        # 1. Bypass check for owner
        if user_id == OWNER_ID:
            return await func(update, context, *args, **kwargs)
            
        from config import CHANNEL_USERNAME
        if not CHANNEL_USERNAME:
            return await func(update, context, *args, **kwargs)
            
        channel = CHANNEL_USERNAME.strip()
        if not channel.startswith("@"):
            channel = f"@{channel}"
            
        is_joined = False
        try:
            member = await context.bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status in ["member", "creator", "administrator", "restricted"]:
                is_joined = True
        except Exception as e:
            # If we fail to check, default to False to force joining
            import logging
            logging.getLogger(__name__).warning(f"Error checking channel membership for user {user_id}: {e}")
            is_joined = False
            
        if is_joined:
            return await func(update, context, *args, **kwargs)
            
        # 2. Access denied - send join channel prompt
        text = f"""
⚠️ *MEMBERSHIP REQUIRED*

To use the **Spinify Ads Bot**, you must be a member of our official channel: **{channel}**.

📢 *Join to receive updates, guides, and support!*

👇 *Please join the channel and click 'Joined ✅' below:*
"""
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{CHANNEL_USERNAME}")],
            [InlineKeyboardButton("Joined ✅", callback_data="check_channel_join")]
        ])
        
        if update.callback_query:
            await update.callback_query.answer("Membership required!", show_alert=True)
            await update.callback_query.edit_message_text(
                text,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
        else:
            await update.message.reply_text(
                text,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
        return None
        
    return wrapper

