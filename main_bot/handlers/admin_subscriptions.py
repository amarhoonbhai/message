"""
Admin Subscription Management Panel for Main Bot.
"""

from telegram import Update
import io
import csv
from datetime import datetime
from telegram.ext import ContextTypes, ConversationHandler

from models.plan import (
    get_subscription_stats, query_subscriptions, extend_plan, 
    reduce_plan, mark_plan_expired, delete_plan
)
from main_bot.utils.keyboards import (
    get_subscription_menu_keyboard, get_subscription_list_keyboard,
    get_subscription_user_details_keyboard
)
from config import OWNER_ID
from shared.utils import escape_markdown

def is_owner(user_id: int) -> bool:
    """Check if user is the owner."""
    return user_id == OWNER_ID

async def admin_sub_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the overall subscription stats and main menu."""
    query = update.callback_query
    user_id = update.effective_user.id
    
    if not is_owner(user_id):
        if query: await query.answer("⛔ Access denied", show_alert=True)
        return
        
    stats = await get_subscription_stats()
    
    text = f"""
💳 *SUBSCRIPTION MANAGEMENT*
══════════════════════════════

📊 *OVERVIEW STATS*
👥 Total Subscribed Users: {stats['total_subscribed']}
🟢 Active Subscriptions: {stats['active']}
🔴 Expired Subscriptions: {stats['expired']}
⏳ Expiring Soon (7d): {stats['expiring_soon']}
💎 Lifetime Users: {stats['lifetime']}

Select a filter to view user lists or export data:
"""
    
    if query:
        await query.answer()
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_subscription_menu_keyboard(),
        )
    else:
        await update.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_subscription_menu_keyboard(),
        )

async def admin_sub_list_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle displaying lists of subscriptions with pagination."""
    query = update.callback_query
    user_id = update.effective_user.id
    
    if not is_owner(user_id):
        await query.answer("⛔ Access denied", show_alert=True)
        return

    data = query.data.split(":")
    filter_type = data[1] if len(data) > 1 else "all"
    page = int(data[2]) if len(data) > 2 else 0
    
    limit = 5 # 5 items per page max to prevent huge messages
    skip = page * limit
    
    total, results = await query_subscriptions(filter_type=filter_type, skip=skip, limit=limit)
    total_pages = (total + limit - 1) // limit if total > 0 else 1
    
    if page >= total_pages: page = total_pages - 1
    if page < 0: page = 0
    
    await query.answer()

    if not results:
        text = f"📋 *Subscription Details* ({filter_type.upper().replace('_', ' ')})\n\nNo records found."
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_subscription_list_keyboard(filter_type, page, total_pages)
        )
        return

    text = f"📋 *Subscription Details* ({filter_type.upper().replace('_', ' ')})\n"
    text += f"Records: {skip+1} to min({skip+limit}, {total}) of {total}\n════════════════════════════\n\n"
    
    for plan in results:
        uinfo = plan.get("user_info", {})
        uid = plan["user_id"]
        uname = escape_markdown(uinfo.get("username", "Not Set"))
        fname = escape_markdown(uinfo.get("first_name", "Unknown"))
        ptype = plan.get("plan_type", "premium").title()
        
        start_date = plan.get("started_at", datetime.utcnow())
        expiry_date = plan.get("expires_at", datetime.utcnow())
        
        days_left = (expiry_date - datetime.utcnow()).days
        
        if plan.get("status") == "expired" or days_left < 0:
            status = "🔴 Expired"
            days_left = 0
        elif days_left <= 7:
            status = "🟡 Expiring Soon"
        elif days_left > 3000:
            status = "💎 Lifetime"
            days_left = "Unlimited"
        else:
            status = "🟢 Active"
            
        start_str = start_date.strftime("%d %b %Y")
        expiry_str = expiry_date.strftime("%d %b %Y") if str(days_left) != "Unlimited" else "Never"
        
        text += f"👤 *Username:* @{uname} ({fname})\n"
        text += f"🆔 *User ID:* `{uid}`\n"
        text += f"💎 *Plan:* {ptype}\n"
        text += f"📅 *Start:* {start_str}\n"
        text += f"⏳ *Expiry:* {expiry_str}\n"
        text += f"📌 *Days Left:* {days_left}\n"
        text += f"✅ *Status:* {status}\n\n"
        text += f"*(Use /subscription {uid} to edit)*\n"
        text += "〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️\n"

    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_subscription_list_keyboard(filter_type, page, total_pages)
    )

async def admin_sub_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline actions for a specific subscription."""
    query = update.callback_query
    if not is_owner(update.effective_user.id):
        await query.answer("⛔ Access denied", show_alert=True)
        return
        
    data = query.data.split(":")
    target_uid = int(data[1])
    action = data[2]
    value = int(data[3]) if len(data) > 3 else 0
    
    if action == "extend":
        await extend_plan(target_uid, value)
        await query.answer(f"✅ Extended by {value} days!")
    elif action == "reduce":
        await reduce_plan(target_uid, value)
        await query.answer(f"✅ Reduced by {value} days!")
    elif action == "expire":
        await mark_plan_expired(target_uid)
        await query.answer("🛑 Marked as expired!")
    elif action == "delete":
        await delete_plan(target_uid)
        await query.answer("🗑 Deleted subscription record!")
        
    # Re-render user details
    await display_subscription_user(update, context, target_uid, query=query)


async def display_subscription_user(update, context, target_uid: int, query=None):
    """Fetch and display a specific user's subscription panel."""
    total, results = await query_subscriptions(search_query=str(target_uid), limit=1)
    
    if not results:
        text = f"❌ No subscription found for User ID: `{target_uid}`"
        keyboard = get_subscription_list_keyboard("all", 0, 1)
    else:
        plan = results[0]
        uinfo = plan.get("user_info", {})
        uname = escape_markdown(uinfo.get("username", "Not Set"))
        fname = escape_markdown(uinfo.get("first_name", "Unknown"))
        ptype = plan.get("plan_type", "premium").title()
        
        start_date = plan.get("started_at", datetime.utcnow())
        expiry_date = plan.get("expires_at", datetime.utcnow())
        days_left = (expiry_date - datetime.utcnow()).days
        
        if plan.get("status") == "expired" or days_left < 0:
            status = "🔴 Expired"
            days_left = 0
        elif days_left <= 7:
            status = "🟡 Expiring Soon"
        elif days_left > 3000:
            status = "💎 Lifetime"
            days_left = "Unlimited"
        else:
            status = "🟢 Active"
            
        start_str = start_date.strftime("%d %b %Y")
        expiry_str = expiry_date.strftime("%d %b %Y") if str(days_left) != "Unlimited" else "Never"
        
        text = f"""
🛠 *SUBSCRIPTION CONTROLS*

👤 *Username:* @{uname} ({fname})
🆔 *User ID:* `{target_uid}`
💎 *Plan:* {ptype}
📅 *Start:* {start_str}
⏳ *Expiry:* {expiry_str}
📌 *Days Left:* {days_left}
✅ *Status:* {status}

Choose an action to modify this subscription:
"""
        keyboard = get_subscription_user_details_keyboard(target_uid)

    if query:
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)

async def admin_sub_export_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Export all subscription data as CSV."""
    query = update.callback_query
    if not is_owner(update.effective_user.id):
        await query.answer("⛔ Access denied", show_alert=True)
        return
        
    await query.answer("Generating CSV, please wait...")
    
    # Get all users (no limit)
    total, results = await query_subscriptions(limit=1000000)
    
    csv_file = io.StringIO()
    writer = csv.writer(csv_file)
    writer.writerow(["UserID", "Username", "FirstName", "LastName", "PlanType", "Status", "StartedAt", "ExpiresAt", "DaysLeft"])
    
    now = datetime.utcnow()
    for plan in results:
        uinfo = plan.get("user_info", {})
        uid = plan.get("user_id", "")
        uname = uinfo.get("username", "")
        fname = uinfo.get("first_name", "")
        lname = uinfo.get("last_name", "")
        ptype = plan.get("plan_type", "premium")
        pstatus = plan.get("status", "")
        start = plan.get("started_at", "").strftime("%Y-%m-%d %H:%M:%S") if plan.get("started_at") else ""
        end = plan.get("expires_at", "")
        
        if end:
            days_left = max(-1, (end - now).days)
            end_s = end.strftime("%Y-%m-%d %H:%M:%S")
        else:
            days_left = 0
            end_s = ""
            
        writer.writerow([uid, uname, fname, lname, ptype, pstatus, start, end_s, days_left])
    
    csv_bytes = csv_file.getvalue().encode('utf-8')
    csv_io = io.BytesIO(csv_bytes)
    csv_io.name = f"spinify_subscriptions_{datetime.now().strftime('%Y%m%d')}.csv"
    
    # Send document
    await context.bot.send_document(
        chat_id=update.effective_user.id,
        document=csv_io,
        caption=f"📊 Exported {total} subscription records."
    )

# --- COMMAND HANDLERS ---
async def cmd_all_subscriptions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_owner(update.effective_user.id): await admin_sub_menu_callback(update, context)

async def cmd_active_subscriptions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_owner(update.effective_user.id): 
        # Mock a callback query for 'active'
        query = type('obj', (object,), {'data':'adm_sub_list:active:0', 'answer': lambda *a,**k: None, 'edit_message_text': update.message.reply_text})()
        await admin_sub_list_callback(update=type('obj', (object,), {'callback_query': query, 'effective_user': update.effective_user})(), context=context)

async def cmd_expired_subscriptions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_owner(update.effective_user.id): 
        query = type('obj', (object,), {'data':'adm_sub_list:expired:0', 'answer': lambda *a,**k: None, 'edit_message_text': update.message.reply_text})()
        await admin_sub_list_callback(update=type('obj', (object,), {'callback_query': query, 'effective_user': update.effective_user})(), context=context)

async def cmd_expiring_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_owner(update.effective_user.id): 
        query = type('obj', (object,), {'data':'adm_sub_list:expiring_soon:0', 'answer': lambda *a,**k: None, 'edit_message_text': update.message.reply_text})()
        await admin_sub_list_callback(update=type('obj', (object,), {'callback_query': query, 'effective_user': update.effective_user})(), context=context)

async def cmd_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id): return
    if len(context.args) < 1:
        await update.message.reply_text("⚠️ *Usage:* `/subscription <User ID>`", parse_mode="Markdown")
        return
        
    try:
        uid = int(context.args[0])
        await display_subscription_user(update, context, uid)
    except ValueError:
        await update.message.reply_text("❌ User ID must be a number.")
