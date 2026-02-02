"""
Configuration module for Group Message Scheduler.
Loads all settings from environment variables.
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ============== Bot Tokens ==============
MAIN_BOT_TOKEN = os.getenv("MAIN_BOT_TOKEN", "")
LOGIN_BOT_TOKEN = os.getenv("LOGIN_BOT_TOKEN", "")

# ============== Bot Usernames ==============
MAIN_BOT_USERNAME = os.getenv("MAIN_BOT_USERNAME", "")
LOGIN_BOT_USERNAME = os.getenv("LOGIN_BOT_USERNAME", "spinifyLoginbot")

# ============== Telegram API ==============
def _safe_int(value: str, default: int = 0) -> int:
    """Safely parse integer from string."""
    try:
        return int(value) if value and value.isdigit() else default
    except (ValueError, TypeError):
        return default

API_ID = _safe_int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")

# ============== Owner/Admin ==============
OWNER_ID = _safe_int(os.getenv("OWNER_ID", "0"))

# ============== MongoDB ==============
MONGODB_URI = os.getenv(
    "MONGODB_URI",
    "mongodb+srv://Spinify:xKtH3qsMhOnTH2Pd@spinifybot.bxjgzoh.mongodb.net/spinify?retryWrites=true&w=majority&appName=SpinifyBot"
)

# ============== Channel ==============
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "PHilobots")

# ============== Scheduling Rules ==============
MAX_GROUPS_PER_USER = 15
GROUP_GAP_SECONDS = 90          # Delay between groups
MESSAGE_GAP_SECONDS = 500       # Delay between messages
MIN_INTERVAL_MINUTES = 20       # Minimum user interval
DEFAULT_INTERVAL_MINUTES = 30   # Default interval

# ============== Night Mode (IST) ==============
NIGHT_MODE_START_HOUR = 0       # 00:00 IST
NIGHT_MODE_END_HOUR = 6         # 06:00 IST
TIMEZONE = "Asia/Kolkata"

# ============== Plans ==============
TRIAL_DAYS = 7
REFERRAL_BONUS_DAYS = 7
REFERRALS_NEEDED = 3

PLAN_PRICES = {
    "week": 99,     # ₹99/week
    "month": 299,   # ₹299/month
}

PLAN_DURATIONS = {
    "week": 7,      # 7 days
    "month": 30,    # 30 days
}
