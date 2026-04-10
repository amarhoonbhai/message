"""
Start and welcome handler for Main Bot.
"""

from telegram import Update
from telegram.ext import ContextTypes

from db.models import create_user, get_user, get_plan, get_all_user_sessions
from main_bot.utils.keyboards import get_welcome_keyboard, get_subscription_required_keyboard
from core.config import OWNER_ID
from shared.utils import escape_markdown


async def build_welcome_text(user) -> tuple[str, bool]:
    """Build personalized welcome text. Returns (text, is_premium)."""
    first_name = user.first_name or "User"
    last_name = user.last_name or ""
    full_name = escape_markdown(f"{first_name} {last_name}".strip())
    username = escape_markdown(f"@{user.username}" if user.username else "Not set")
    user_id = user.id

    # Get account and plan info
    plan = await get_plan(user_id)
    sessions = await get_all_user_sessions(user_id)
    accounts_count = len(sessions) if sessions else 0

    # Plan badge
    if plan and plan.get("status") == "active":
        import datetime
        days_left = (plan["expires_at"] - datetime.datetime.utcnow()).days
        plan_tag = f"💎 PREMIUM ({max(0, days_left)}d left)"
        is_premium = True
    elif plan:
        plan_tag = "🔴 EXPIRED"
        is_premium = False
    else:
        plan_tag = "⚪ No Active Plan"
        is_premium = False

    # Check for restricted view
    if not is_premium and user_id != OWNER_ID:
        text = f"""
⚡ *GROUP MESSAGE SCHEDULER* ⚡

*Welcome, {full_name}!*
*User ID:* `{user_id}`
*Plan Status:* {plan_tag}

⚠️ *ACCESS RESTRICTED*
This is a *Fully Premium Bot*. Only users with an active paid plan can access the automated messaging features.

🚀 *Key Benefits of Premium:*
• ✅ Link Multiple Accounts
• ✅ Auto-Forward Messages
• ✅ Anti-Flood Protection
• ✅ 24/7 Global Delivery

👇 *Choose an option below to activate your account:*
"""
        return text, False

    # Premium/Owner View
    text = f"""
⚡ *GROUP MESSAGE SCHEDULER* ⚡

*★ V3.3 — PRO ENGINE ★*

*Welcome, {full_name}!*
*Username:* {username}
*User ID:* `{user_id}`
*Accounts:* {accounts_count} connected
*Plan:* {plan_tag}

🎯 *AUTOMATE YOUR TELEGRAM ADS*

📤 *Auto-forward* to 100+ Groups
🛡️ *Smart Anti-Flood* Protection
🌙 *Auto Night Mode* (12AM-6AM)
📊 *Real-time* Dashboard
🔄 *Copy Mode & Shuffle* Mode
💬 *Auto-Responder* (DMs)
🔐 *Secure Encrypted* Sessions

⚙️ *HOW IT WORKS*

1️⃣ Connect your Telegram account
2️⃣ Add your target groups
3️⃣ Drop messages in *Saved Messages*
4️⃣ Sit back — we forward them! 🚀

👇 *TAP A BUTTON BELOW TO BEGIN*
"""
    return text, True


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command and deep links."""
    user = update.effective_user
    args = context.args

    # Check for connected deep link
    show_dashboard_link = False

    if args:
        arg = args[0]
        if arg == "connected":
            show_dashboard_link = True

    # Create or get user
    await create_user(user.id)
    from models.user import update_user_profile
    await update_user_profile(user.id, user.username, user.first_name, user.last_name)

    if show_dashboard_link:
        from main_bot.handlers.dashboard import show_dashboard
        await show_dashboard(update, context)
        return

    # Build personalized welcome
    welcome_text, is_premium = await build_welcome_text(user)
    
    # Use restricted keyboard if not premium
    if is_premium or user.id == OWNER_ID:
        keyboard = get_welcome_keyboard()
    else:
        keyboard = get_subscription_required_keyboard()

    await update.message.reply_text(
        welcome_text,
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


async def home_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle home button callback - return to welcome screen."""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    from models.user import update_user_profile
    await update_user_profile(user.id, user.username, user.first_name, user.last_name)
    
    welcome_text, is_premium = await build_welcome_text(user)
    
    # Use restricted keyboard if not premium
    if is_premium or user.id == OWNER_ID:
        keyboard = get_welcome_keyboard()
    else:
        keyboard = get_subscription_required_keyboard()

    await query.edit_message_text(
        welcome_text,
        parse_mode="Markdown",
        reply_markup=keyboard,
    )
