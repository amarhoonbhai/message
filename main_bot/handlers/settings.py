"""
Interval settings handler for Main Bot.
"""

from telegram import Update
from telegram.ext import ContextTypes

from db.models import get_user_config, update_user_config
from main_bot.utils.keyboards import get_interval_keyboard, get_back_home_keyboard
from config import MIN_INTERVAL_MINUTES


async def interval_settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show interval settings."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    config = await get_user_config(user_id)
    current_interval = config.get("interval_min", MIN_INTERVAL_MINUTES)
    
    text = f"""
⏱ *Interval Settings*

Current interval: *{current_interval} minutes*

This is how often the worker checks for new Saved Messages
and forwards them to your groups.

*Minimum:* 20 minutes
*Recommended:* 30-60 minutes

Select your preferred interval:
"""
    
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_interval_keyboard(current_interval),
    )


async def set_interval_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set new interval value."""
    query = update.callback_query
    data = query.data
    
    new_interval = int(data.split(":")[1])
    user_id = update.effective_user.id
    
    # Ensure minimum interval
    if new_interval < MIN_INTERVAL_MINUTES:
        new_interval = MIN_INTERVAL_MINUTES
    
    await update_user_config(user_id, interval_min=new_interval)
    
    await query.answer(f"Interval set to {new_interval} minutes ✅")
    
    # Refresh settings screen
    await interval_settings_callback(update, context)
