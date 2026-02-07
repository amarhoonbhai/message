"""
Start and welcome handler for Main Bot.
"""

from telegram import Update
from telegram.ext import ContextTypes

from db.models import create_user, get_user, get_session, get_user_by_referral_code
from main_bot.utils.keyboards import get_welcome_keyboard


WELCOME_TEXT = """
■ *GROUP MESSAGE SCHEDULER* ■
━━━━━━━━━━━━━━━━━━━━━━━━━━━

● *POWER YOUR TELEGRAM ADS*

  ➤ Auto-forward to *15+ Groups*
  ➤ Smart delays ▪ Anti-flood
  ➤ Night mode ▪ Full automation

━━━━ *FEATURES* ━━━━

  ○ Instant Forwarding
  ○ 60s Safe Delays
  ○ Night Mode (0-6 AM)
  ○ Real-time Dashboard
  ○ Secure Sessions

━━━━━━━━━━━━━━━━━━━━━━━━━━━

▼ *SELECT AN OPTION BELOW*
"""


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command and deep links."""
    user = update.effective_user
    args = context.args
    
    # Check for referral or connected deep link
    referred_by = None
    show_dashboard = False
    
    if args:
        arg = args[0]
        if arg.startswith("ref_"):
            referred_by = arg[4:]  # Extract referral code
        elif arg == "connected":
            show_dashboard = True
    
    # Create or get user
    await create_user(user.id, referred_by=referred_by)
    
    if show_dashboard:
        # User just connected, show dashboard
        from main_bot.handlers.dashboard import show_dashboard
        await show_dashboard(update, context)
        return
    
    # Show welcome screen
    await update.message.reply_text(
        WELCOME_TEXT,
        parse_mode="Markdown",
        reply_markup=get_welcome_keyboard(),
    )


async def home_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle home button callback - return to welcome screen."""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        WELCOME_TEXT,
        parse_mode="Markdown",
        reply_markup=get_welcome_keyboard(),
    )
