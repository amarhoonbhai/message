import sys
import traceback
from unittest.mock import MagicMock

# Mock out motor to avoid timeout exceptions on local connection attempts
sys.modules['motor'] = MagicMock()
sys.modules['motor.motor_asyncio'] = MagicMock()

handlers = [
    'start', 'dashboard', 'plans', 'referral', 'redeem',
    'admin', 'help', 'account', 'profile'
]

print("--- TESTING IMPORTS ---")
for h in handlers:
    try:
        __import__(f'main_bot.handlers.{h}')
        print(f"OK: {h}")
    except Exception as e:
        print(f"ERROR IMPORTING {h}:")
        traceback.print_exc()

print("--- TESTING BOT INITIALIZATION ---")
try:
    import main_bot.bot
    print("OK: main_bot.bot imported successfully.")
except Exception as e:
    print("ERROR IMPORTING main_bot.bot:")
    traceback.print_exc()
