"""
Redeem code handler for Main Bot.
"""

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from db.models import redeem_code
from main_bot.utils.keyboards import get_back_home_keyboard


# Conversation states
WAITING_CODE = 1


async def redeem_code_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start redeem code flow."""
    query = update.callback_query
    await query.answer()
    
    text = """
🧾 *Redeem Code*

Enter your redemption code below.

Codes are case-insensitive.
"""
    
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_back_home_keyboard(),
    )
    
    context.user_data["waiting_for"] = "redeem_code"
    return WAITING_CODE


async def receive_redeem_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process received redeem code."""
    user_id = update.effective_user.id
    code = update.message.text.strip()
    
    success, message = await redeem_code(user_id, code)
    
    await update.message.reply_text(
        message,
        parse_mode="Markdown",
        reply_markup=get_back_home_keyboard(),
    )
    
    context.user_data.pop("waiting_for", None)
    return ConversationHandler.END


async def redeem_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /redeem <CODE> command."""
    user_id = update.effective_user.id
    
    if not context.args:
        await update.message.reply_text(
            "Usage: /redeem <CODE>\n\nExample: /redeem ABC123XYZ",
            reply_markup=get_back_home_keyboard(),
        )
        return
    
    code = context.args[0].strip()
    success, message = await redeem_code(user_id, code)
    
    await update.message.reply_text(
        message,
        parse_mode="Markdown",
        reply_markup=get_back_home_keyboard(),
    )
