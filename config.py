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

def _safe_int(value: str, default: int = 0) -> int:
    """Safely parse integer from string."""
    try:
        if not value:
            return default
        return int(value)
    except (ValueError, TypeError):
        return default

# ============== Owner/Admin ==============
OWNER_ID = _safe_int(os.getenv("OWNER_ID", "0"))

# ============== MongoDB ==============
MONGODB_URI = os.getenv(
    "MONGODB_URI",
    "mongodb+srv://Spinify:xKtH3qsMhOnTH2Pd@spinifybot.bxjgzoh.mongodb.net/spinify?retryWrites=true&w=majority&appName=SpinifyBot"
)

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

# ============== Channel ==============
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "PHilobots")
PAYMENT_UPI_ID = os.getenv("PAYMENT_UPI_ID", "rain@slc")
SUPPORT_HANDLE = os.getenv("SUPPORT_HANDLE", "@spinify")
SUPPORT_URL = os.getenv("SUPPORT_URL", "https://t.me/spinify")

# ============== Scheduling Rules ==============
MAX_GROUPS_PER_USER = 100
GROUP_GAP_SECONDS = 45           # Delay between groups (45 seconds - medium speed)
MESSAGE_GAP_SECONDS = 210        # Delay between messages (3.5 minutes)
MIN_INTERVAL_MINUTES = 15       # Minimum user interval
DEFAULT_INTERVAL_MINUTES = 15   # Default interval (if user doesn't set .interval)

# ============== Night Mode (IST) ==============
NIGHT_MODE_START_HOUR = 0       # 00:00 IST
NIGHT_MODE_END_HOUR = 6         # 06:00 IST
TIMEZONE = "Asia/Kolkata"

# ============== Plans ==============
PLAN_PRICES = {
    "week": 99,       # ₹99/week
    "month": 299,     # ₹299/month
    "3month": 799,    # ₹799/3 months
    "6month": 1499,   # ₹1499/6 months
    "1year": 2499,    # ₹2499/1 year
}

PLAN_DURATIONS = {
    "week": 7,        # 7 days
    "month": 30,      # 30 days
    "3month": 90,     # 90 days
    "6month": 180,    # 180 days
    "1year": 365,     # 365 days
}
