"""
Admin/Owner panel handler for Main Bot.
"""

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from db.models import (
    get_admin_stats, generate_redeem_code, get_all_users_for_broadcast,
    get_global_settings, update_global_settings
)
from main_bot.utils.keyboards import (
    get_admin_keyboard, get_broadcast_keyboard, get_back_home_keyboard,
    get_night_mode_settings_keyboard, get_admin_upgrade_keyboard
)
from config import OWNER_ID, PLAN_DURATIONS
from shared.utils import escape_markdown
from db.models import extend_plan, activate_plan, get_plan


# Conversation states
WAITING_BROADCAST_MESSAGE = 1
WAITING_UPGRADE_USER_ID = 2


def is_owner(user_id: int) -> bool:
    """Check if user is the owner."""
    return user_id == OWNER_ID


async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show admin panel."""
    query = update.callback_query
    user_id = update.effective_user.id
    
    if not is_owner(user_id):
        await query.answer("⛔ Access denied", show_alert=True)
        return
    
    await query.answer()
    
    text = """
👑 *ADMINISTRATOR TERMINAL*

Welcome to the command center.
Manage users, track live statistics, and broadcast announcements directly below.
"""
    
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_admin_keyboard(),
    )


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /admin command."""
    user_id = update.effective_user.id
    
    if not is_owner(user_id):
        await update.message.reply_text("⛔ Access denied")
        return
    
    text = """
👑 *ADMINISTRATOR TERMINAL*
══════════════════════════════

Welcome to the command center.
Manage users, track live statistics, and 
broadcast announcements directly below.
"""
    
    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_admin_keyboard(),
    )


async def get_stats_text():
    stats = await get_admin_stats()
    
    total = stats['sends_24h']
    success = stats['success_24h']
    success_rate = stats.get('avg_success_rate', round((success/total*100) if total > 0 else 0, 1))

    return f"""
📊 *GLOBAL SYSTEM STATISTICS*

👥 *USER METRICS*
├ Total Users: {stats['total_users']}
├ Active Sessions: {stats['connected_sessions']}
├ Premium Active: {stats['paid_active']}
├ Trial Active: {stats['trial_active']}
└ Expired Plans: {stats['expired']}

📨 *PERFORMANCE (LAST 24H)*
├ Messages Attempted: {total}
├ Messages Delivered: {success}
├ Success Rate: {success_rate}%
└ Failures: {stats['failed_24h']}

📁 *GROUP HEALTH*
├ Total Groups: {stats.get('total_groups', 'N/A')}
├ Currently Failing: {stats.get('groups_failing', 0)} ⚠️
└ Removed/Flagged (24h): {stats.get('groups_removed_24h', 0)}

🛡️ *SYSTEM*
├ Auto-Remove: After 24h of failures
└ Status: 🟢 Operational

_Data is live and accurate as of now._
"""

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats command."""
    user_id = update.effective_user.id
    
    if not is_owner(user_id):
        await update.message.reply_text("⛔ Access denied")
        return
    
    text = await get_stats_text()
    
    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_admin_keyboard(),
    )


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /broadcast command."""
    user_id = update.effective_user.id
    
    if not is_owner(user_id):
        await update.message.reply_text("⛔ Access denied")
        return
    
    text = """
📢 *GLOBAL BROADCAST SYSTEM*
══════════════════════════════

Select your target audience below to 
initiate the broadcast sequence:
"""
    
    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_broadcast_keyboard(),
    )


async def admin_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show bot statistics."""
    query = update.callback_query
    user_id = update.effective_user.id
    
    if not is_owner(user_id):
        await query.answer("⛔ Access denied", show_alert=True)
        return
    
    await query.answer()
    
    text = await get_stats_text()
    
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_admin_keyboard(),
    )

async def admin_health_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show session health overview."""
    query = update.callback_query
    user_id = update.effective_user.id
    
    if not is_owner(user_id):
        await query.answer("⛔ Access denied", show_alert=True)
        return
    
    await query.answer()
    
    from db.models import get_all_connected_sessions, get_plan
    sessions = await get_all_connected_sessions()
    
    text = "🩺 *SESSION HEALTH MONITOR*\n\n"
    
    active_sessions_count = 0
    if sessions:
        for s in sessions:
            user_id = s.get("user_id")
            if not user_id: continue
            
            # Only show users with an active plan
            plan = await get_plan(user_id)
            if not plan or plan.get("status") != "active":
                continue
                
            active_sessions_count += 1
            phone = s.get("phone", "Unknown")
            status = s.get("worker_status", "Off")
            streak = s.get("error_streak", 0)
            
            icon = "🟢"
            if streak > 5: icon = "🔴"
            elif streak > 0: icon = "🟡"
            
            text += f"{icon} `{phone}` | {status} | Errors: {streak}\n"
            
    if active_sessions_count == 0:
        text += "_No active sessions found._"
    
    text += "\n*Status Legend:*\n🟢 Healthy | 🟡 Unstable | 🔴 Critical"
    
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_admin_keyboard(),
    )



async def admin_broadcast_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show broadcast options."""
    query = update.callback_query
    user_id = update.effective_user.id
    
    if not is_owner(user_id):
        await query.answer("⛔ Access denied", show_alert=True)
        return
    
    await query.answer()
    
    text = """
📢 *GLOBAL BROADCAST SYSTEM*
══════════════════════════════

Select your target audience below to 
initiate the broadcast sequence:
"""
    
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_broadcast_keyboard(),
    )


async def broadcast_target_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle broadcast target selection."""
    query = update.callback_query
    user_id = update.effective_user.id
    
    if not is_owner(user_id):
        await query.answer("⛔ Access denied", show_alert=True)
        return
    
    target = query.data.split(":")[1]
    context.user_data["broadcast_target"] = target
    
    await query.answer()
    
    text = f"""
📢 *BROADCAST TARGET: {target.upper()}*

Awaiting transmission payload...
Send me the exact message you want to blast.

*Supports:* Text, Photos, Videos, Documents
*Abort:* Type `/cancel` anytime to stop.
"""
    
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_back_home_keyboard(),
    )
    
    context.user_data["waiting_for"] = "broadcast_message"
    return WAITING_BROADCAST_MESSAGE


async def receive_broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process and send broadcast message."""
    user_id = update.effective_user.id
    
    if not is_owner(user_id):
        return ConversationHandler.END
        
    if update.message.text == "/cancel":
        await update.message.reply_text("Broadcast cancelled.", reply_markup=get_back_home_keyboard())
        context.user_data.pop("waiting_for", None)
        context.user_data.pop("broadcast_target", None)
        return ConversationHandler.END
    
    target = context.user_data.get("broadcast_target", "all")
    message = update.message
    
    # Get target users
    user_ids = await get_all_users_for_broadcast(target)
    
    success = 0
    failed = 0
    
    status_msg = await message.reply_text(f"📤 *Initiating broadcast to {len(user_ids)} users...*", parse_mode="Markdown")
    
    for uid in user_ids:
        try:
            if message.text:
                # Try without parse_mode first (safer for plain text with special chars)
                try:
                    await context.bot.send_message(
                        uid, 
                        message.text, 
                        parse_mode="Markdown",
                        disable_web_page_preview=False
                    )
                except Exception:
                    # Fallback: send without Markdown if it fails
                    await context.bot.send_message(
                        uid, 
                        message.text,
                        disable_web_page_preview=False
                    )
            elif message.photo:
                await context.bot.send_photo(
                    uid,
                    message.photo[-1].file_id,
                    caption=message.caption
                )
            elif message.video:
                await context.bot.send_video(
                    uid,
                    message.video.file_id,
                    caption=message.caption
                )
            elif message.animation:
                await context.bot.send_animation(
                    uid,
                    message.animation.file_id,
                    caption=message.caption
                )
            elif message.sticker:
                await context.bot.send_sticker(uid, message.sticker.file_id)
            elif message.voice:
                await context.bot.send_voice(
                    uid,
                    message.voice.file_id,
                    caption=message.caption
                )
            elif message.audio:
                await context.bot.send_audio(
                    uid,
                    message.audio.file_id,
                    caption=message.caption
                )
            elif message.video_note:
                await context.bot.send_video_note(uid, message.video_note.file_id)
            elif message.document:
                await context.bot.send_document(
                    uid,
                    message.document.file_id,
                    caption=message.caption
                )
            else:
                # Fallback: copy the message directly for any other type
                await context.bot.copy_message(
                    chat_id=uid,
                    from_chat_id=message.chat_id,
                    message_id=message.message_id
                )
            success += 1
        except Exception as e:
            failed += 1
            # Log first few failures for debugging
            if failed <= 3:
                import logging
                logging.warning(f"Broadcast failed for {uid}: {e}")
    
    await status_msg.edit_text(
        f"✅ *BROADCAST COMPLETE*\n\n"
        f"🎯 *Delivered:* {success}\n"
        f"❌ *Failed:* {failed}",
        parse_mode="Markdown",
        reply_markup=get_back_home_keyboard()
    )
    
    context.user_data.pop("waiting_for", None)
    context.user_data.pop("broadcast_target", None)
    return ConversationHandler.END


async def gen_code_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate a redeem code."""
    query = update.callback_query
    user_id = update.effective_user.id
    
    if not is_owner(user_id):
        await query.answer("⛔ Access denied", show_alert=True)
        return
    
    plan_type = query.data.split(":")[1]
    
    code = await generate_redeem_code(plan_type)
    escaped_code = escape_markdown(code)
    
    await query.answer()
    
    days = 7 if plan_type == "week" else 30
    
    text = f"""
🎟 *NEW PROMO CODE GENERATED*

✅ *Payload ready for distribution.*

📋 *Access Code:* `{escaped_code}`
📦 *Tier:* {plan_type.upper()} PRO
📅 *Duration:* {days} Days Lifetime
🔒 *Scope:* Single-use only

*Instructions:* User must post `/redeem {escaped_code}`
"""
    
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_admin_keyboard(),
    )


async def generate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /generate <week|month> command."""
    user_id = update.effective_user.id
    
    if not is_owner(user_id):
        await update.message.reply_text("⛔ Access denied")
        return
    
    if not context.args:
        await update.message.reply_text(
            "⚠️ *Usage:* `/generate <week/month>`\n\nExample: `/generate week`",
            parse_mode="Markdown"
        )
        return
    
    plan_type = context.args[0].lower()
    
    if plan_type not in ["week", "month"]:
        await update.message.reply_text("Invalid tier. Use: *week* or *month*", parse_mode="Markdown")
        return
    
    code = await generate_redeem_code(plan_type)
    escaped_code = escape_markdown(code)
    days = 7 if plan_type == "week" else 30
    
    await update.message.reply_text(
        f"🎟 *NEW PROMO CODE GENERATED*\n\n"
        f"📋 *Access Code:* `{escaped_code}`\n"
        f"📦 *Tier:* {plan_type.upper()} PRO\n"
        f"📅 *Duration:* {days} Days",
        parse_mode="Markdown",
    )


async def admin_users_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show users overview."""
    query = update.callback_query
    user_id = update.effective_user.id
    
    if not is_owner(user_id):
        await query.answer("⛔ Access denied", show_alert=True)
        return
    
    await query.answer()
    
    stats = await get_admin_stats()
    
    text = f"""
👥 *GLOBAL USER DATABASE*

📊 *Total Registered Users:* {stats['total_users']}

*SEGMENTATION ANALYSIS:*
├ 🔗 Active API Sessions: {stats['connected_sessions']}
├ 🎁 Free Trials Running: {stats['trial_active']}
├ 💎 Premium Subs Active: {stats['paid_active']}
└ ⏰ Expired Memberships: {stats['expired']}

_Pro Tip: Use the Broadcast system to target specific segments._
"""
    
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_admin_keyboard(),
    )
async def admin_nightmode_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show global night mode settings."""
    query = update.callback_query
    user_id = update.effective_user.id
    
    if not is_owner(user_id):
        await query.answer("⛔ Access denied", show_alert=True)
        return
    
    await query.answer()
    
    settings = await get_global_settings()
    current = settings.get("night_mode_force", "auto").upper()
    
    text = f"""
🌙 *GLOBAL NIGHT MODE CONTROL*
══════════════════════════════

*Current State:* `{current}`

Select a mode button below to override the system-wide night mode behavior:

🔴 *FORCE ON:* Pauses all bots immediately.
🟢 *FORCE OFF:* Disables night mode pause entirely.
⏳ *AUTO (Schedule):* Resumes 00:00-06:00 IST logic.

_This change affects all accounts globally._
"""
    
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_night_mode_settings_keyboard(),
    )


async def set_nightmode_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Update global night mode setting via callback."""
    query = update.callback_query
    user_id = update.effective_user.id
    
    if not is_owner(user_id):
        await query.answer("⛔ Access denied", show_alert=True)
        return
    
    mode = query.data.split(":")[1]
    await update_global_settings(night_mode_force=mode)
    
    await query.answer(f"✅ Night Mode updated to {mode.upper()}", show_alert=True)
    await admin_nightmode_callback(update, context)


async def nightmode_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /nightmode command from owner."""
    user_id = update.effective_user.id
    
    if not is_owner(user_id):
        await update.message.reply_text("⛔ Access denied")
        return
    
    settings = await get_global_settings()
    current = settings.get("night_mode_force", "auto").upper()
    
    text = f"""
🌙 *GLOBAL NIGHT MODE CONTROL*
══════════════════════════════

*Current State:* `{current}`

Select a mode button below to override the system-wide night mode behavior.
"""
    
    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_night_mode_settings_keyboard(),
    )
async def admin_upgrade_init_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the upgrade process (ask for User ID)."""
    query = update.callback_query
    
    if not is_owner(update.effective_user.id):
        await query.answer("⛔ Access denied", show_alert=True)
        return ConversationHandler.END
    
    await query.answer()
    await query.edit_message_text(
        "⚡ *ADMIN UPGRADE TOOL*\n\n"
        "Please send the *Telegram User ID* of the user you wish to upgrade.\n\n"
        "_Example: 123456789_\n\n"
        "Type /cancel to abort.",
        parse_mode="Markdown",
        reply_markup=get_back_home_keyboard()
    )
    return WAITING_UPGRADE_USER_ID

async def receive_upgrade_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive User ID and show options."""
    if not is_owner(update.effective_user.id): return ConversationHandler.END
    
    text = update.message.text
    if text == "/cancel":
        await update.message.reply_text("Cancelled.", reply_markup=get_back_home_keyboard())
        return ConversationHandler.END
        
    try:
        target_uid = int(text)
        plan = await get_plan(target_uid)
        
        status = "No Plan"
        if plan:
            status = plan.get("plan_type", "trial").upper()
            
        await update.message.reply_text(
            f"👤 *USER:* `{target_uid}`\n"
            f"📊 *CURRENT:* `{status}`\n\n"
            "Select the upgrade tier below:",
            parse_mode="Markdown",
            reply_markup=get_admin_upgrade_keyboard(target_uid)
        )
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ Invalid ID. Please send a numeric User ID.")
        return WAITING_UPGRADE_USER_ID

async def admin_upgrade_perform_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Execute the upgrade."""
    query = update.callback_query
    if not is_owner(update.effective_user.id):
        await query.answer("⛔ Access denied", show_alert=True)
        return
    
    data = query.data.split(":")
    target_uid = int(data[1])
    tier = data[2]
    
    await query.answer(f"Upgrading {target_uid} to {tier.upper()}...")
    
    await activate_plan(target_uid, tier)
    days = PLAN_DURATIONS.get(tier, 0)
    
    await query.edit_message_text(
        f"✅ *SUCCESSFULLY UPGRADED*\n\n"
        f"👤 *User:* `{target_uid}`\n"
        f"📦 *Tier:* {tier.upper()}\n"
        f"📅 *Added:* {days} Days\n\n"
        "_The user has been notified via their dashboard._",
        parse_mode="Markdown",
        reply_markup=get_admin_keyboard()
    )
    
    # Try to notify the user
    try:
        await context.bot.send_message(
            target_uid,
            f"🎊 *PLAN UPGRADED!*\n\n"
            f"The administrator has granted you **{days} days** of **{tier.upper()}** access.\n"
            "Enjoy uninterrupted service!",
            parse_mode="Markdown"
        )
    except: pass

async def upgrade_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /upgrade <user_id> <week/month>."""
    if not is_owner(update.effective_user.id): return
    
    if len(context.args) < 2:
        await update.message.reply_text("⚠️ *Usage:* `/upgrade <user_id> <week|month>`")
        return
        
    try:
        uid = int(context.args[0])
        tier = context.args[1].lower()
        if tier not in ["week", "month"]: raise ValueError()
        
        await activate_plan(uid, tier)
        days = PLAN_DURATIONS[tier]
        
        await update.message.reply_text(f"✅ User `{uid}` upgraded to {tier.upper()} ({days} days).")
        
        try:
            await context.bot.send_message(uid, f"🎊 *PLAN UPGRADED!*\n\nGranted **{days} days** of **{tier.upper()}**.")
        except: pass
    except:
        await update.message.reply_text("❌ Invalid arguments. Example: `/upgrade 123456 week`")
