"""
Start and welcome handler for Main Bot.
"""

from typing import Optional
from telegram import Update
from telegram.ext import ContextTypes

from db.models import create_user, get_plan, get_all_user_sessions
from main_bot.utils.keyboards import get_welcome_keyboard
from core.config import OWNER_ID
from shared.utils import escape_markdown
from shared.decorators import require_channel_join


async def get_user_profile_photo(bot, user_id: int) -> Optional[str]:
    """Fetch the user's profile photo file ID, if available."""
    try:
        photos = await bot.get_user_profile_photos(user_id=user_id, limit=1)
        if photos and photos.total_count > 0:
            # Get largest photo size
            return photos.photos[0][-1].file_id
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Failed to fetch profile photo for user {user_id}: {e}")
    return None


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
    else:
        plan_tag = "⚪ Free User"
        is_premium = False

    # Premium/Owner/Free View
    text = f"""
⚡ *GROUP MESSAGE SCHEDULER* ⚡
🤖 *Welcome, {full_name}!*

👤 *Profile Info:*
├─ 🆔 *User ID:* `{user_id}`
├─ 🌐 *Username:* {username}
├─ 💳 *Plan:* {plan_tag}
└─ 📱 *Sessions:* `{accounts_count}` connected

🎯 *PRO AUTOMATION ENGINE:*
🚀 *Auto-forward Ads* to 100+ target groups!
🛡️ *Smart Anti-Flood* protection built-in.
🌙 *Night Mode schedule* automatically applied.
📊 *Real-time Dashboard* & session management.

⚙️ *QUICK START GUIDE:*
1️⃣ Link your account via *Login Bot*.
2️⃣ Add target groups (use `.addgroup` in Saved Messages).
3️⃣ Send your ad messages to *Saved Messages*.
4️⃣ Sit back — we automate the forwarding! 📤

👇 _Tap the buttons below to control the bot:_
"""
    return text, is_premium


@require_channel_join
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
    keyboard = get_welcome_keyboard()

    photo_file_id = await get_user_profile_photo(context.bot, user.id)

    if photo_file_id:
        await update.message.reply_photo(
            photo=photo_file_id,
            caption=welcome_text,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    else:
        await update.message.reply_text(
            welcome_text,
            parse_mode="Markdown",
            reply_markup=keyboard,
        )


@require_channel_join
async def home_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle home button callback - return to welcome screen."""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    from models.user import update_user_profile
    await update_user_profile(user.id, user.username, user.first_name, user.last_name)
    
    welcome_text, is_premium = await build_welcome_text(user)
    keyboard = get_welcome_keyboard()

    photo_file_id = await get_user_profile_photo(context.bot, user.id)

    if photo_file_id:
        try:
            await query.message.delete()
        except Exception:
            pass
        await context.bot.send_photo(
            chat_id=user.id,
            photo=photo_file_id,
            caption=welcome_text,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    else:
        try:
            await query.edit_message_text(
                welcome_text,
                parse_mode="Markdown",
                reply_markup=keyboard,
            )
        except Exception:
            await context.bot.send_message(
                chat_id=user.id,
                text=welcome_text,
                parse_mode="Markdown",
                reply_markup=keyboard
            )


async def check_channel_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle callback for Joined verification button."""
    query = update.callback_query
    user_id = update.effective_user.id
    
    from config import CHANNEL_USERNAME, OWNER_ID
    channel = CHANNEL_USERNAME.strip()
    if not channel.startswith("@"):
        channel = f"@{channel}"
        
    is_joined = False
    if user_id == OWNER_ID:
        is_joined = True
    else:
        try:
            member = await context.bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status in ["member", "creator", "administrator", "restricted"]:
                is_joined = True
        except Exception as e:
            is_joined = False
            
    if is_joined:
        await query.answer("✅ Verification successful!", show_alert=True)
        await home_callback(update, context)
    else:
        await query.answer(f"❌ You have not joined {channel} yet. Please join and try again.", show_alert=True)
