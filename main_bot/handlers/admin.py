"""
Admin/Owner panel handler for Main Bot.
"""

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from db.models import get_admin_stats, generate_redeem_code, get_all_users_for_broadcast
from main_bot.utils.keyboards import get_admin_keyboard, get_broadcast_keyboard, get_back_home_keyboard
from config import OWNER_ID


# Conversation states
WAITING_BROADCAST_MESSAGE = 1


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
🔐 *ADMIN PANEL*
╔══════════════════════════╗
║     ★ OWNER CONTROLS ★        ║
╚══════════════════════════╝

  Welcome, *Owner*! 👑

  Use the options below to manage
  your bot, users, and codes.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
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
🔐 *ADMIN PANEL*
╔══════════════════════════╗
║     ★ OWNER CONTROLS ★        ║
╚══════════════════════════╝

  Welcome, *Owner*! 👑

  Use the options below to manage
  your bot, users, and codes.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    
    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_admin_keyboard(),
    )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats command."""
    user_id = update.effective_user.id
    
    if not is_owner(user_id):
        await update.message.reply_text("⛔ Access denied")
        return
    
    stats = await get_admin_stats()
    
    # Calculate percentages
    total = stats['total_users'] or 1
    connected_pct = int((stats['connected_sessions'] / total) * 100)
    sends_total = stats['sends_24h'] or 1
    success_pct = int((stats['success_24h'] / sends_total) * 100) if sends_total > 0 else 0
    
    text = f"""
📊 *BOT STATISTICS*
╔══════════════════════════╗

👥 *USERS*
  ├─ 📊 Total: *{stats['total_users']}*
  ├─ 🔗 Connected: *{stats['connected_sessions']}* ({connected_pct}%)
  ├─ 🏅 Trial: *{stats['trial_active']}*
  ├─ 💎 Paid: *{stats['paid_active']}*
  └─ ⏰ Expired: *{stats['expired']}*

━━━━━━━━━━━━━━━━━━━━━━━━

📨 *SENDS (24h)*
  ├─ 📤 Total: *{stats['sends_24h']}*
  ├─ ✅ Success: *{stats['success_24h']}* ({success_pct}%)
  ├─ ❌ Failed: *{stats['failed_24h']}*
  └─ 🗑️ Groups Removed: *{stats['groups_removed_24h']}*

╚══════════════════════════╝
"""
    
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
📢 *BROADCAST*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Select the target audience:
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
    
    stats = await get_admin_stats()
    
    # Calculate percentages
    total = stats['total_users'] or 1
    connected_pct = int((stats['connected_sessions'] / total) * 100)
    sends_total = stats['sends_24h'] or 1
    success_pct = int((stats['success_24h'] / sends_total) * 100) if sends_total > 0 else 0
    
    text = f"""
📊 *BOT STATISTICS*
╔══════════════════════════╗

👥 *USERS*
  ├─ 📊 Total: *{stats['total_users']}*
  ├─ 🔗 Connected: *{stats['connected_sessions']}* ({connected_pct}%)
  ├─ 🏅 Trial: *{stats['trial_active']}*
  ├─ 💎 Paid: *{stats['paid_active']}*
  └─ ⏰ Expired: *{stats['expired']}*

━━━━━━━━━━━━━━━━━━━━━━━━

📨 *SENDS (24h)*
  ├─ 📤 Total: *{stats['sends_24h']}*
  ├─ ✅ Success: *{stats['success_24h']}* ({success_pct}%)
  ├─ ❌ Failed: *{stats['failed_24h']}*
  └─ 🗑️ Groups Removed: *{stats['groups_removed_24h']}*

╚══════════════════════════╝
"""
    
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
📢 *BROADCAST*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Select the target audience:
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
📢 *Broadcast to: {target.title()}*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Now send me the message to broadcast.

  ✅ Text, photos, documents
  ❌ /cancel to abort
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
    
    target = context.user_data.get("broadcast_target", "all")
    message = update.message
    
    # Get target users
    user_ids = await get_all_users_for_broadcast(target)
    
    success = 0
    failed = 0
    
    status_msg = await message.reply_text(f"📤 Broadcasting to {len(user_ids)} users...")
    
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
    
    total = success + failed
    pct = int((success / total) * 100) if total > 0 else 0
    
    await status_msg.edit_text(
        f"✅ *Broadcast Complete*\n\n"
        f"  ▸ Sent: *{success}* ({pct}%)\n"
        f"  ▸ Failed: *{failed}*\n"
        f"  ▸ Target: *{target.title()}*",
        parse_mode="Markdown",
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
    
    await query.answer()
    
    days = 7 if plan_type == "week" else 30
    
    text = f"""
🎟 *CODE GENERATED*
╔══════════════════════════╗

📋 Code: `{code}`

╚══════════════════════════╝

  ▸ Type: *{plan_type.title()}*
  ▸ Duration: *{days} days*
  ▸ Usage: *Single-use*

_Share this code with a user._
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
            "Usage: /generate <week|month>\n\nExample: /generate week"
        )
        return
    
    plan_type = context.args[0].lower()
    
    if plan_type not in ["week", "month"]:
        await update.message.reply_text("Invalid plan type. Use: week or month")
        return
    
    code = await generate_redeem_code(plan_type)
    days = 7 if plan_type == "week" else 30
    
    await update.message.reply_text(
        f"🎟 *CODE GENERATED*\n\n"
        f"📋 Code: `{code}`\n"
        f"📦 Type: *{plan_type.title()}*\n"
        f"📅 Duration: *{days} days*",
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
    
    # Calculate percentages
    total = stats['total_users'] or 1
    connected_pct = int((stats['connected_sessions'] / total) * 100)
    
    text = f"""
👥 *USERS OVERVIEW*
╔══════════════════════════╗

📊 *Total Users:* {stats['total_users']}

╚══════════════════════════╝

  ├─ 🔗 Connected: *{stats['connected_sessions']}* ({connected_pct}%)
  ├─ 🏅 Trial: *{stats['trial_active']}*
  ├─ 💎 Paid: *{stats['paid_active']}*
  └─ ⏰ Expired: *{stats['expired']}*

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 Use /broadcast to message users.
"""
    
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_admin_keyboard(),
    )
