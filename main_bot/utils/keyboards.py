"""
Inline keyboard builders for Main Bot.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import LOGIN_BOT_USERNAME, CHANNEL_USERNAME, SUPPORT_URL


def get_welcome_keyboard() -> InlineKeyboardMarkup:
    """Build welcome screen keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("➕ Add Account", callback_data="add_account"),
            InlineKeyboardButton("📊 Open Dashboard", callback_data="dashboard"),
        ],
        [
            InlineKeyboardButton("🎁 My Plan", callback_data="my_plan"),
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
        ],
        [
            InlineKeyboardButton("🧾 Redeem Promo Code", callback_data="redeem_code"),
            InlineKeyboardButton("📘 Commands Map", callback_data="help"),
        ],
        [
            InlineKeyboardButton("🔄 Toggle Send Mode", callback_data="toggle_send_mode"),
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
            InlineKeyboardButton("💎 WEEKLY (₹99)", callback_data="buy_plan:week"),
            InlineKeyboardButton("🏆 MONTHLY (₹299)", callback_data="buy_plan:month"),
        ],
        [
            InlineKeyboardButton("🌟 3 MONTHS (₹799)", callback_data="buy_plan:3month"),
        ],
        [
            InlineKeyboardButton("👑 6 MONTHS (₹1499)", callback_data="buy_plan:6month"),
            InlineKeyboardButton("☄️ 1 YEAR (₹2499)", callback_data="buy_plan:1year"),
        ],
        [
            InlineKeyboardButton("🧾 Redeem Promo Code", callback_data="redeem_code"),
        ],
        [
            InlineKeyboardButton("👨‍💻 Contact Support", url=SUPPORT_URL),
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data="dashboard"),
            InlineKeyboardButton("🏠 Home", callback_data="home"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_admin_upgrade_keyboard(target_user_id: int) -> InlineKeyboardMarkup:
    """Build admin upgrade selection keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("💎 1 Week", callback_data=f"adm_upgr:{target_user_id}:week"),
            InlineKeyboardButton("🏆 1 Month", callback_data=f"adm_upgr:{target_user_id}:month"),
        ],
        [
            InlineKeyboardButton("🌟 3 Months", callback_data=f"adm_upgr:{target_user_id}:3month"),
            InlineKeyboardButton("👑 6 Months", callback_data=f"adm_upgr:{target_user_id}:6month"),
        ],
        [
            InlineKeyboardButton("☄️ 1 Year", callback_data=f"adm_upgr:{target_user_id}:1year"),
        ],
        [
            InlineKeyboardButton("🔙 Back to Admin", callback_data="admin"),
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
            InlineKeyboardButton("🩺 Health Monitor", callback_data="admin_health"),
            InlineKeyboardButton("📊 Live Stats", callback_data="admin_stats"),
        ],
        [
            InlineKeyboardButton("📢 Global Blast", callback_data="admin_broadcast"),
        ],
        [
            InlineKeyboardButton("🎟 1 Week", callback_data="gen_code:week"),
            InlineKeyboardButton("🎟 1 Month", callback_data="gen_code:month"),
            InlineKeyboardButton("🎟 3 Month", callback_data="gen_code:3month"),
        ],
        [
            InlineKeyboardButton("🎟 6 Month", callback_data="gen_code:6month"),
            InlineKeyboardButton("🎟 1 Year", callback_data="gen_code:1year"),
        ],
        [
            InlineKeyboardButton("⚡ Quick Upgrade User", callback_data="admin_upgrade_init"),
        ],
        [
            InlineKeyboardButton("👥 User Database", callback_data="admin_users"),
            InlineKeyboardButton("🌙 Night Mode", callback_data="admin_nightmode"),
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

def get_profile_keyboard() -> InlineKeyboardMarkup:
    """Build profile screen keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("⚙️ Manage Accounts", callback_data="accounts_list"),
        ],
        [
            InlineKeyboardButton("🎁 My Plan", callback_data="my_plan"),
        ],
        [
            InlineKeyboardButton("🔙 Back to Dashboard", callback_data="dashboard"),
            InlineKeyboardButton("🏠 Home", callback_data="home"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_night_mode_settings_keyboard() -> InlineKeyboardMarkup:
    """Build keyboard for global night mode settings."""
    keyboard = [
        [
            InlineKeyboardButton("🔴 FORCE ON", callback_data="set_nightmode:on"),
            InlineKeyboardButton("🟢 FORCE OFF", callback_data="set_nightmode:off"),
        ],
        [
            InlineKeyboardButton("⏳ AUTO (Schedule)", callback_data="set_nightmode:auto"),
        ],
        [
            InlineKeyboardButton("🔙 Back to Admin", callback_data="admin_stats"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


