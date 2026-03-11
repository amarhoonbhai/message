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
API_ID = 22458350
API_HASH = "15a5967ac713da91a8751791020dbaf8"

def _safe_int(value: str, default: int = 0) -> int:
    """Safely parse integer from string."""
    try:
        if not value:
            return default
        return int(value)
    except (ValueError, TypeError):
        return default

# ============== Validation ==============
def validate_config():
    """Validate critical configuration on startup."""
    missing = []
    if not MAIN_BOT_TOKEN or "main_bot_token" in MAIN_BOT_TOKEN.lower(): 
        missing.append("MAIN_BOT_TOKEN")
    if not LOGIN_BOT_TOKEN or "login_bot_token" in LOGIN_BOT_TOKEN.lower(): 
        missing.append("LOGIN_BOT_TOKEN")
    
    # Check for placeholder MongoDB URI
    if "username:password" in MONGODB_URI:
        missing.append("MONGODB_URI (Current value looks like a placeholder)")
        
    if missing:
        import sys
        print("\n" + "!"*50)
        print(f"CRITICAL ERROR: Missing or placeholder configuration keys:\n{', '.join(missing)}")
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
MAX_GROUPS_PER_USER = 100
GROUP_GAP_SECONDS = 300          # Delay between groups (5 minutes - As requested)
MESSAGE_GAP_SECONDS = 300       # Delay between messages (5 minutes - As requested)
MIN_INTERVAL_MINUTES = 15       # Minimum user interval
DEFAULT_INTERVAL_MINUTES = 15   # Default interval (if user doesn't set .interval)

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
