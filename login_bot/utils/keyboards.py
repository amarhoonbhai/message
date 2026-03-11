"""
Inline keyboard builders for Login Bot.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import MAIN_BOT_USERNAME, CHANNEL_USERNAME


def get_login_welcome_keyboard() -> InlineKeyboardMarkup:
    """Build login welcome screen keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("➕ Add Account / Connect", callback_data="add_account"),
        ],
        [
            InlineKeyboardButton("📱 Manage Connected Accounts", callback_data="manage_accounts"),
        ],
        [
            InlineKeyboardButton("🔙 Back to Main Bot", url=f"https://t.me/{MAIN_BOT_USERNAME}"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_phone_input_keyboard() -> InlineKeyboardMarkup:
    """Keyboard shown during phone input."""
    keyboard = [
        [
            InlineKeyboardButton("❌ Cancel Process", callback_data="cancel"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_api_input_keyboard() -> InlineKeyboardMarkup:
    """Keyboard shown during API ID/Hash input."""
    keyboard = [
        [
            InlineKeyboardButton("❌ Cancel Process", callback_data="cancel"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)





def get_confirm_phone_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for phone confirmation."""
    keyboard = [
        [
            InlineKeyboardButton("📥 Send Verification Code", callback_data="send_otp"),
        ],
        [
            InlineKeyboardButton("✏️ Change Number", callback_data="edit_phone"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_otp_keypad(current_otp: str = "") -> InlineKeyboardMarkup:
    """
    Build OTP entry keypad.
    Shows current OTP as masked display.
    """
    # Display OTP digits or underscores
    display = ""
    for i in range(5):
        if i < len(current_otp):
            display += f"{current_otp[i]} "
        else:
            display += "_ "
    
    keyboard = [
        # Row 1: 1 2 3
        [
            InlineKeyboardButton("1", callback_data="otp:1"),
            InlineKeyboardButton("2", callback_data="otp:2"),
            InlineKeyboardButton("3", callback_data="otp:3"),
        ],
        # Row 2: 4 5 6
        [
            InlineKeyboardButton("4", callback_data="otp:4"),
            InlineKeyboardButton("5", callback_data="otp:5"),
            InlineKeyboardButton("6", callback_data="otp:6"),
        ],
        # Row 3: 7 8 9
        [
            InlineKeyboardButton("7", callback_data="otp:7"),
            InlineKeyboardButton("8", callback_data="otp:8"),
            InlineKeyboardButton("9", callback_data="otp:9"),
        ],
        # Row 4: ⌫ 0 🧹
        [
            InlineKeyboardButton("⌫ ", callback_data="otp:back"),
            InlineKeyboardButton("0", callback_data="otp:0"),
            InlineKeyboardButton("🗑️ ", callback_data="otp:clear"),
        ],
        # Row 5: Submit Cancel
        [
            InlineKeyboardButton("✅ LOGIN", callback_data="otp:submit"),
            InlineKeyboardButton("❌ CANCEL", callback_data="cancel"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_resend_otp_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for resending OTP."""
    keyboard = [
        [
            InlineKeyboardButton("🔄 Resend Code (SMS)", callback_data="resend_otp"),
        ],
        [
            InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_2fa_keyboard() -> InlineKeyboardMarkup:
    """Keyboard shown during 2FA input."""
    keyboard = [
        [
            InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_success_keyboard() -> InlineKeyboardMarkup:
    """Success screen keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("🚀 Go to Main Dashboard", url=f"https://t.me/{MAIN_BOT_USERNAME}?start=connected"),
        ],
        [
            InlineKeyboardButton("📌 Join Community", url=f"https://t.me/{CHANNEL_USERNAME}"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_manage_accounts_keyboard(accounts: list) -> InlineKeyboardMarkup:
    """Build list of accounts with buttons."""
    keyboard = []
    for acc in accounts:
        phone = acc.get("phone", "Unknown")
        status = "🟢" if acc.get("connected") else "🔴"
        keyboard.append([
            InlineKeyboardButton(f"{status} {phone}", callback_data=f"manage_acc:{phone}")
        ])
    
    keyboard.append([InlineKeyboardButton("➕ Add New Account", callback_data="add_account")])
    keyboard.append([InlineKeyboardButton("🔙 Back to Home", callback_data="login_home")])
    
    return InlineKeyboardMarkup(keyboard)


def get_account_options_keyboard(phone: str) -> InlineKeyboardMarkup:
    """Options for a specific account."""
    keyboard = [
        [
            InlineKeyboardButton("🔄 Re-login / Refresh", callback_data="add_account"),
            InlineKeyboardButton("🗑️ Disconnect", callback_data=f"disconnect_acc:{phone}"),
        ],
        [
            InlineKeyboardButton("🔙 Back to List", callback_data="manage_accounts"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_disconnect_confirm_keyboard(phone: str) -> InlineKeyboardMarkup:
    """Confirmation for disconnection."""
    keyboard = [
        [
            InlineKeyboardButton("✅ Yes, Disconnect", callback_data=f"confirm_disc_acc:{phone}"),
        ],
        [
            InlineKeyboardButton("❌ Cancel", callback_data=f"manage_acc:{phone}"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """Keyboard after cancellation."""
    keyboard = [
        [
            InlineKeyboardButton("🔄 Try Again", callback_data="add_account"),
        ],
        [
            InlineKeyboardButton("🔙 Back to Main Bot", url=f"https://t.me/{MAIN_BOT_USERNAME}"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)
