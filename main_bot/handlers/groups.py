"""
Groups management handler for Main Bot.
"""

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters

from db.models import add_group, get_user_groups, remove_group, toggle_group, get_group_count
from main_bot.utils.keyboards import (
    get_groups_keyboard, get_groups_list_keyboard, get_back_home_keyboard
)
from config import MAX_GROUPS_PER_USER


# Conversation states
WAITING_GROUP_LINK = 1


async def manage_groups_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show manage groups menu."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    group_count = await get_group_count(user_id)
    
    text = f"""
👥 *Manage Groups*

You have *{group_count} / {MAX_GROUPS_PER_USER}* groups configured.

Use the buttons below to add, view, or remove groups.
"""
    
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_groups_keyboard(),
    )


async def add_group_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start add group flow."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    group_count = await get_group_count(user_id)
    
    if group_count >= MAX_GROUPS_PER_USER:
        await query.edit_message_text(
            f"❌ *Maximum Groups Reached*\n\nYou already have {MAX_GROUPS_PER_USER} groups.\nRemove a group first to add a new one.",
            parse_mode="Markdown",
            reply_markup=get_back_home_keyboard(),
        )
        return ConversationHandler.END
    
    text = """
➕ *Add a Group*

Send me the group/channel username or link.

Examples:
• @groupname
• https://t.me/groupname
• https://t.me/+invitelink

⚠️ Make sure the bot or your connected account has permission to post.
"""
    
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_back_home_keyboard(),
    )
    
    context.user_data["waiting_for"] = "group_link"
    return WAITING_GROUP_LINK


async def receive_group_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process received group link."""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    # Parse group identifier
    group_identifier = text
    
    # Remove common prefixes
    if text.startswith("https://t.me/"):
        group_identifier = text.replace("https://t.me/", "")
    elif text.startswith("@"):
        group_identifier = text[1:]
    
    # For now, store the identifier as-is
    # In production, resolve to chat_id using Telethon
    
    try:
        # TODO: Resolve to actual chat_id using user's session
        # For now, use a placeholder
        chat_id = hash(group_identifier) % 10000000000
        chat_title = group_identifier[:30]
        
        success = await add_group(user_id, chat_id, chat_title)
        
        if success:
            group_count = await get_group_count(user_id)
            await update.message.reply_text(
                f"✅ *Group Added Successfully!*\n\n"
                f"📋 *Title:* {chat_title}\n"
                f"👥 *Total Groups:* {group_count} / {MAX_GROUPS_PER_USER}",
                parse_mode="Markdown",
                reply_markup=get_back_home_keyboard(),
            )
        else:
            await update.message.reply_text(
                f"❌ *Cannot Add Group*\n\nYou've reached the maximum of {MAX_GROUPS_PER_USER} groups.",
                parse_mode="Markdown",
                reply_markup=get_back_home_keyboard(),
            )
    except Exception as e:
        await update.message.reply_text(
            f"❌ *Error Adding Group*\n\n{str(e)}",
            parse_mode="Markdown",
            reply_markup=get_back_home_keyboard(),
        )
    
    context.user_data.pop("waiting_for", None)
    return ConversationHandler.END


async def list_groups_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show list of user's groups."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    groups = await get_user_groups(user_id)
    
    if not groups:
        await query.edit_message_text(
            "📋 *Your Groups*\n\nNo groups added yet.\nUse ➕ Add Group to get started.",
            parse_mode="Markdown",
            reply_markup=get_back_home_keyboard(),
        )
        return
    
    text = "📋 *Your Groups*\n\n"
    text += "Tap a group to toggle it on/off.\n"
    text += "Tap 🗑 to remove a group.\n"
    
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_groups_list_keyboard(groups),
    )


async def toggle_group_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle group enabled status."""
    query = update.callback_query
    data = query.data
    
    chat_id = int(data.split(":")[1])
    user_id = update.effective_user.id
    
    # Get current state and toggle
    groups = await get_user_groups(user_id)
    current_group = next((g for g in groups if g["chat_id"] == chat_id), None)
    
    if current_group:
        new_state = not current_group.get("enabled", True)
        await toggle_group(user_id, chat_id, new_state)
        
        status = "enabled ✅" if new_state else "disabled ❌"
        await query.answer(f"Group {status}")
    
    # Refresh list
    await list_groups_callback(update, context)


async def delete_group_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete a group."""
    query = update.callback_query
    data = query.data
    
    chat_id = int(data.split(":")[1])
    user_id = update.effective_user.id
    
    await remove_group(user_id, chat_id)
    await query.answer("Group removed ✅")
    
    # Refresh list
    await list_groups_callback(update, context)


async def remove_group_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show remove group instruction."""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "➖ *Remove a Group*\n\n"
        "Go to 📋 List Groups and tap 🗑 next to the group you want to remove.",
        parse_mode="Markdown",
        reply_markup=get_back_home_keyboard(),
    )
