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
    
    # Visual progress dots
    filled = min(referrals_count, REFERRALS_NEEDED)
    empty = REFERRALS_NEEDED - filled
    progress_dots = "🟢" * filled + "⚪" * empty
    
    # Progress bar
    progress_bar = "▓" * filled + "░" * empty
    percentage = int((referrals_count / REFERRALS_NEEDED) * 100) if REFERRALS_NEEDED > 0 else 0
    percentage = min(percentage, 100)
    
    # Bonus status
    if bonus_applied:
        bonus_text = f"✅ *Bonus claimed!* +{REFERRAL_BONUS_DAYS} days added!"
        reward_icon = "🎊"
    elif referrals_count >= REFERRALS_NEEDED:
        bonus_text = f"🎉 *Bonus earned!* +{REFERRAL_BONUS_DAYS} days!"
        reward_icon = "🏆"
    else:
        remaining = REFERRALS_NEEDED - referrals_count
        bonus_text = f"Invite *{remaining} more* to earn +{REFERRAL_BONUS_DAYS} days!"
        reward_icon = "🎯"
    
    text = f"""
🤝 *REFER & EARN*
╔══════════════════════════╗

{reward_icon} *YOUR PROGRESS*

  {progress_dots}
  [{progress_bar}] *{percentage}%*

  👥 *{referrals_count}/{REFERRALS_NEEDED}* friends invited
  {bonus_text}

╚══════════════════════════╝

━━━━ 🔗 *YOUR LINK* 🔗 ━━━━

  `{referral_link}`

  _Tap to copy • Share with friends!_

━━━━ 📖 *HOW IT WORKS* ━━━━

  1️⃣ Share your referral link
  2️⃣ Friends join & connect account
  3️⃣ Get *+{REFERRAL_BONUS_DAYS} FREE days!* 🎁

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎁 *REWARD:* {REFERRAL_BONUS_DAYS} FREE premium days!
"""
    
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_referral_keyboard(referral_link),
    )
