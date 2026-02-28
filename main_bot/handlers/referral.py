"""
Referral handler for Main Bot.
"""

from telegram import Update
from telegram.ext import ContextTypes

from db.models import get_user
from main_bot.utils.keyboards import get_referral_keyboard, get_back_home_keyboard
from config import MAIN_BOT_USERNAME, REFERRALS_NEEDED, REFERRAL_BONUS_DAYS


async def referral_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show referral screen."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    user = await get_user(user_id)
    
    if not user:
        await query.edit_message_text(
            "❌ Please start the bot first using /start",
            reply_markup=get_back_home_keyboard(),
        )
        return
    
    referral_code = user.get("referral_code", "")
    referrals_count = user.get("referrals_count", 0)
    bonus_applied = user.get("referral_bonus_applied", False)
    
    referral_link = f"https://t.me/{MAIN_BOT_USERNAME}?start=ref_{referral_code}"
    
    if bonus_applied:
        bonus_text = f"✅ *Bonus Claimed!* +{REFERRAL_BONUS_DAYS} days added."
    elif referrals_count >= REFERRALS_NEEDED:
        bonus_text = f"🎉 *Target Met!* +{REFERRAL_BONUS_DAYS} days unlocked!"
    else:
        remaining = REFERRALS_NEEDED - referrals_count
        bonus_text = f"Invite *{remaining} more* friend(s) to unlock!"
    
    # Enhanced progress bar
    filled_blocks = min(referrals_count, REFERRALS_NEEDED)
    empty_blocks = REFERRALS_NEEDED - filled_blocks
    progress_bar = "🟢" * filled_blocks + "⚪" * empty_blocks
    percentage = int((referrals_count / REFERRALS_NEEDED) * 100) if REFERRALS_NEEDED > 0 else 0
    
    text = f"""
🤝 *REFER & EARN PROGRAM*

Earn free premium days by inviting your friends to use Group Message Scheduler!

📊 *YOUR PROGRESS*
► {progress_bar} *{percentage}%*
► *{referrals_count}/{REFERRALS_NEEDED}* friends joined

📌 {bonus_text}

🔗 *YOUR UNIQUE INVITE LINK*
`{referral_link}`

📖 *HOW IT WORKS*
1️⃣ Share the link above with friends
2️⃣ They start the bot using your link
3️⃣ You instantly get *+{REFERRAL_BONUS_DAYS} FREE DAYS* when {REFERRALS_NEEDED} friends join!

🎁 *REWARD:* {REFERRAL_BONUS_DAYS} Days of Premium Auto-Forwarding!
"""
    
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_referral_keyboard(referral_link),
    )
