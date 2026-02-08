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
# ============== Telegram API ==============
def _safe_int(value: str, default: int = 0) -> int:
    """Safely parse integer from string."""
    try:
        if not value:
            return default
        return int(value)
    except (ValueError, TypeError):
        return default

API_ID = _safe_int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")

# ============== Validation ==============
def validate_config():
    """Validate critical configuration on startup."""
    missing = []
    if not MAIN_BOT_TOKEN: missing.append("MAIN_BOT_TOKEN")
    if not LOGIN_BOT_TOKEN: missing.append("LOGIN_BOT_TOKEN")
    if API_ID == 0: missing.append("API_ID")
    if not API_HASH: missing.append("API_HASH")
    
    if missing:
        import sys
        print("\n" + "!"*50)
        print(f"CRITICAL ERROR: Missing configuration keys:\n{', '.join(missing)}")
        print("Please check your .env file.")
        print("!"*50 + "\n")
        sys.exit(1)

# Run validation
validate_config()

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
GROUP_GAP_SECONDS = 10          # Delay between groups (10 seconds - Safe)
MESSAGE_GAP_SECONDS = 120       # Delay between messages (2 minutes - Safe)
MIN_INTERVAL_MINUTES = 20       # Minimum user interval
DEFAULT_INTERVAL_MINUTES = 23   # Default interval (if user doesn't set .interval)

# ============== Night Mode (IST) ==============
NIGHT_MODE_START_HOUR = 0       # 00:00 IST
NIGHT_MODE_END_HOUR = 6         # 06:00 IST
TIMEZONE = "Asia/Kolkata"

# ============== Trial Bio Enforcement ==============
TRIAL_BIO_TEXT = "Powered by @AutoMessageSchedulerBot"
BIO_CHECK_INTERVAL = 600        # Check every 10 minutes

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
