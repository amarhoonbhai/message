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
            InlineKeyboardButton("🎁 My Plan", callback_data="my_plan"),
            InlineKeyboardButton("🤝 Refer & Earn", callback_data="referral"),
        ],
        [
            InlineKeyboardButton("📌 Join Community", url=f"https://t.me/{CHANNEL_USERNAME}"),
            InlineKeyboardButton("📘 Help & Docs", callback_data="help"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_add_account_keyboard() -> InlineKeyboardMarkup:
    """Build add account screen keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("🚀 Continue to Login Bot", url=f"https://t.me/{LOGIN_BOT_USERNAME}"),
        ],
        [
            InlineKeyboardButton("🏠 Back to Home", callback_data="home"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_dashboard_keyboard() -> InlineKeyboardMarkup:
    """Build dashboard keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("➕ Add Account", callback_data="add_account"),
            InlineKeyboardButton("⚙️ Manage Accounts", callback_data="accounts_list"),
        ],
        [
            InlineKeyboardButton("🎁 My Plan / Status", callback_data="my_plan"),
            InlineKeyboardButton("🤝 Refer & Earn", callback_data="referral"),
        ],
        [
            InlineKeyboardButton("🧾 Redeem Promo Code", callback_data="redeem_code"),
            InlineKeyboardButton("📘 Commands Map", callback_data="help"),
        ],
        [
            InlineKeyboardButton("🏠 Back to Home", callback_data="home"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_account_selection_keyboard(sessions: list) -> InlineKeyboardMarkup:
    """Build keyboard with list of accounts for selection."""
    keyboard = []
    
    for s in sessions:
        phone = s.get("phone", "Unknown")
        status = "🟢" if s.get("connected") else "🔴"
        keyboard.append([InlineKeyboardButton(f"{status} {phone}", callback_data=f"manage_account:{phone}")])
    
    keyboard.append([InlineKeyboardButton("➕ Add Another Account", callback_data="add_account")])
    keyboard.append([InlineKeyboardButton("🔙 Back to Dashboard", callback_data="dashboard")])
    
    return InlineKeyboardMarkup(keyboard)


def get_plan_keyboard() -> InlineKeyboardMarkup:
    """Build plan display keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("🧾 Redeem Promo Code", callback_data="redeem_code"),
        ],
        [
            InlineKeyboardButton("👨‍💻 Contact Support to Upgrade", url="https://t.me/spinify"),
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
            InlineKeyboardButton("📤 Share Link with Friends", switch_inline_query=referral_link),
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
            InlineKeyboardButton("🔙 Go Back", callback_data="dashboard"),
            InlineKeyboardButton("🏠 Main Menu", callback_data="home"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_home_keyboard() -> InlineKeyboardMarkup:
    """Just home button."""
    keyboard = [
        [
            InlineKeyboardButton("🏠 Main Menu", callback_data="home"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_admin_keyboard() -> InlineKeyboardMarkup:
    """Build admin panel keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("📊 Live Stats", callback_data="admin_stats"),
            InlineKeyboardButton("📢 Global Blast", callback_data="admin_broadcast"),
        ],
        [
            InlineKeyboardButton("🎟 Give 1 Week", callback_data="gen_code:week"),
            InlineKeyboardButton("🎟 Give 1 Month", callback_data="gen_code:month"),
        ],
        [
            InlineKeyboardButton("👥 User Database", callback_data="admin_users"),
        ],
        [
            InlineKeyboardButton("🏠 Main Menu", callback_data="home"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_broadcast_keyboard() -> InlineKeyboardMarkup:
    """Build broadcast target selection keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("📢 All Users", callback_data="broadcast:all"),
            InlineKeyboardButton("🔗 Active APIs", callback_data="broadcast:connected"),
        ],
        [
            InlineKeyboardButton("🎁 Trial Group", callback_data="broadcast:trial"),
            InlineKeyboardButton("💎 Premium Base", callback_data="broadcast:paid"),
        ],
        [
            InlineKeyboardButton("🔙 Back to Tools", callback_data="admin"),
            InlineKeyboardButton("🏠 Home", callback_data="home"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_manage_account_keyboard(phone: str) -> InlineKeyboardMarkup:
    """Build manage account keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("🔌 Disconnect Session", callback_data=f"disconnect_account:{phone}"),
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data="accounts_list"),
            InlineKeyboardButton("🏠 Home", callback_data="home"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_confirm_disconnect_keyboard(phone: str) -> InlineKeyboardMarkup:
    """Build disconnect confirmation keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("✅ CONFIRM: WIPE IT", callback_data=f"confirm_disconnect:{phone}"),
        ],
        [
            InlineKeyboardButton("❌ CANCEL", callback_data=f"manage_account:{phone}"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)
