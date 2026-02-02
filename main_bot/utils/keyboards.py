"""
Inline keyboard builders for Main Bot.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import LOGIN_BOT_USERNAME, CHANNEL_USERNAME


def get_welcome_keyboard() -> InlineKeyboardMarkup:
    """Build welcome screen keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("➕ Add Account", callback_data="add_account"),
            InlineKeyboardButton("📊 Open Dashboard", callback_data="dashboard"),
        ],
        [
            InlineKeyboardButton("🎁 Free Trial / My Plan", callback_data="my_plan"),
            InlineKeyboardButton("🤝 Refer & Earn", callback_data="referral"),
        ],
        [
            InlineKeyboardButton("📌 Join @PHilobots", url=f"https://t.me/{CHANNEL_USERNAME}"),
            InlineKeyboardButton("❓ Help", callback_data="help"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_add_account_keyboard() -> InlineKeyboardMarkup:
    """Build add account screen keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("✅ Continue to Login Bot", url=f"https://t.me/{LOGIN_BOT_USERNAME}"),
        ],
        [
            InlineKeyboardButton("🏠 Home", callback_data="home"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_dashboard_keyboard() -> InlineKeyboardMarkup:
    """Build dashboard keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("👥 Manage Groups", callback_data="manage_groups"),
            InlineKeyboardButton("⏱ Interval Settings", callback_data="interval_settings"),
        ],
        [
            InlineKeyboardButton("🎁 My Plan", callback_data="my_plan"),
            InlineKeyboardButton("🤝 Refer & Earn", callback_data="referral"),
        ],
        [
            InlineKeyboardButton("🧾 Redeem Code", callback_data="redeem_code"),
            InlineKeyboardButton("❓ Help", callback_data="help"),
        ],
        [
            InlineKeyboardButton("📌 Join @PHilobots", url=f"https://t.me/{CHANNEL_USERNAME}"),
        ],
        [
            InlineKeyboardButton("🏠 Home", callback_data="home"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_groups_keyboard() -> InlineKeyboardMarkup:
    """Build manage groups keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("➕ Add Group", callback_data="add_group"),
            InlineKeyboardButton("📋 List Groups", callback_data="list_groups"),
        ],
        [
            InlineKeyboardButton("➖ Remove Group", callback_data="remove_group"),
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data="dashboard"),
            InlineKeyboardButton("🏠 Home", callback_data="home"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_groups_list_keyboard(groups: list) -> InlineKeyboardMarkup:
    """Build groups list with toggle buttons."""
    keyboard = []
    
    for group in groups:
        status = "✅" if group.get("enabled") else "❌"
        title = group.get("chat_title", "Unknown")[:20]
        chat_id = group.get("chat_id")
        
        keyboard.append([
            InlineKeyboardButton(
                f"{status} {title}",
                callback_data=f"toggle_group:{chat_id}"
            ),
            InlineKeyboardButton(
                "🗑",
                callback_data=f"delete_group:{chat_id}"
            ),
        ])
    
    keyboard.append([
        InlineKeyboardButton("🔙 Back", callback_data="manage_groups"),
        InlineKeyboardButton("🏠 Home", callback_data="home"),
    ])
    
    return InlineKeyboardMarkup(keyboard)


def get_interval_keyboard(current_interval: int) -> InlineKeyboardMarkup:
    """Build interval settings keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("20 min", callback_data="set_interval:20"),
            InlineKeyboardButton("30 min", callback_data="set_interval:30"),
            InlineKeyboardButton("45 min", callback_data="set_interval:45"),
        ],
        [
            InlineKeyboardButton("60 min", callback_data="set_interval:60"),
            InlineKeyboardButton("90 min", callback_data="set_interval:90"),
            InlineKeyboardButton("120 min", callback_data="set_interval:120"),
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data="dashboard"),
            InlineKeyboardButton("🏠 Home", callback_data="home"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_plan_keyboard() -> InlineKeyboardMarkup:
    """Build plan display keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("🧾 Redeem Code", callback_data="redeem_code"),
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data="dashboard"),
            InlineKeyboardButton("🏠 Home", callback_data="home"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_referral_keyboard(referral_link: str) -> InlineKeyboardMarkup:
    """Build referral screen keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("📤 Share Link", switch_inline_query=referral_link),
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data="dashboard"),
            InlineKeyboardButton("🏠 Home", callback_data="home"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_back_home_keyboard() -> InlineKeyboardMarkup:
    """Simple back and home keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("🔙 Back", callback_data="dashboard"),
            InlineKeyboardButton("🏠 Home", callback_data="home"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_home_keyboard() -> InlineKeyboardMarkup:
    """Just home button."""
    keyboard = [
        [
            InlineKeyboardButton("🏠 Home", callback_data="home"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_admin_keyboard() -> InlineKeyboardMarkup:
    """Build admin panel keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("📊 Stats", callback_data="admin_stats"),
            InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
        ],
        [
            InlineKeyboardButton("🎟 Generate Week Code", callback_data="gen_code:week"),
            InlineKeyboardButton("🎟 Generate Month Code", callback_data="gen_code:month"),
        ],
        [
            InlineKeyboardButton("👥 Users Overview", callback_data="admin_users"),
        ],
        [
            InlineKeyboardButton("🏠 Home", callback_data="home"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_broadcast_keyboard() -> InlineKeyboardMarkup:
    """Build broadcast target selection keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("📢 All Users", callback_data="broadcast:all"),
            InlineKeyboardButton("🔗 Connected", callback_data="broadcast:connected"),
        ],
        [
            InlineKeyboardButton("🎁 Trial", callback_data="broadcast:trial"),
            InlineKeyboardButton("💎 Paid", callback_data="broadcast:paid"),
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data="admin"),
            InlineKeyboardButton("🏠 Home", callback_data="home"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)
