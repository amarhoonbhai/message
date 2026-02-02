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
    
    # Progress bar
    progress = min(referrals_count, REFERRALS_NEEDED)
    bar = "🟢" * progress + "⚪" * (REFERRALS_NEEDED - progress)
    
    if bonus_applied:
        bonus_text = f"✅ *Bonus claimed!* +{REFERRAL_BONUS_DAYS} days added!"
    elif referrals_count >= REFERRALS_NEEDED:
        bonus_text = f"🎉 *Bonus earned!* +{REFERRAL_BONUS_DAYS} days!"
    else:
        remaining = REFERRALS_NEEDED - referrals_count
        bonus_text = f"Invite *{remaining} more* to earn +{REFERRAL_BONUS_DAYS} days!"
    
    text = f"""
🤝 *Refer & Earn*

Share your referral link and earn free days!

📊 *Your Progress:*
{bar}  ({referrals_count}/{REFERRALS_NEEDED})

{bonus_text}

🔗 *Your Referral Link:*
`{referral_link}`

*How it works:*
1️⃣ Share your link with friends
2️⃣ They join and connect their account
3️⃣ After {REFERRALS_NEEDED} referrals, you get +{REFERRAL_BONUS_DAYS} days free!
"""
    
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_referral_keyboard(referral_link),
    )
