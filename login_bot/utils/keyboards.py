"""
Inline keyboard builders for Login Bot.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import MAIN_BOT_USERNAME, CHANNEL_USERNAME


def get_login_welcome_keyboard() -> InlineKeyboardMarkup:
    """Build login welcome screen keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("📱 Add Account", callback_data="add_account"),
        ],
        [
            InlineKeyboardButton("📖 Help", callback_data="help"),
            InlineKeyboardButton("🔙 Back to Main Bot", url=f"https://t.me/{MAIN_BOT_USERNAME}"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_phone_input_keyboard() -> InlineKeyboardMarkup:
    """Keyboard shown during phone input."""
    keyboard = [
        [
            InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_api_input_keyboard() -> InlineKeyboardMarkup:
    """Keyboard shown during API ID/Hash input."""
    keyboard = [
        [
            InlineKeyboardButton("📖 How to get API?", url="https://my.telegram.org"),
        ],
        [
            InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_confirm_phone_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for phone confirmation."""
    keyboard = [
        [
            InlineKeyboardButton("✅ Send OTP", callback_data="send_otp"),
        ],
        [
            InlineKeyboardButton("✏️ Edit Number", callback_data="edit_phone"),
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
            InlineKeyboardButton("⌫ Back", callback_data="otp:back"),
            InlineKeyboardButton("0", callback_data="otp:0"),
            InlineKeyboardButton("🧹 Clear", callback_data="otp:clear"),
        ],
        # Row 5: Submit Cancel
        [
            InlineKeyboardButton("✅ Submit", callback_data="otp:submit"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_resend_otp_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for resending OTP."""
    keyboard = [
        [
            InlineKeyboardButton("🔄 Resend OTP", callback_data="resend_otp"),
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
            InlineKeyboardButton("🚀 Go to Dashboard", url=f"https://t.me/{MAIN_BOT_USERNAME}?start=connected"),
        ],
        [
            InlineKeyboardButton("📌 Join @PHilobots", url=f"https://t.me/{CHANNEL_USERNAME}"),
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
