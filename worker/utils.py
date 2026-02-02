"""
Utility functions for the Worker service.
"""

from datetime import datetime
import pytz

from config import TIMEZONE, NIGHT_MODE_START_HOUR, NIGHT_MODE_END_HOUR

IST = pytz.timezone(TIMEZONE)


def is_night_mode() -> bool:
    """
    Check if current time is within night mode hours.
    Night mode: 00:00 - 06:00 IST
    """
    now_ist = datetime.now(IST)
    current_hour = now_ist.hour
    
    return NIGHT_MODE_START_HOUR <= current_hour < NIGHT_MODE_END_HOUR


def seconds_until_morning() -> int:
    """
    Calculate seconds until night mode ends (06:00 IST).
    """
    now_ist = datetime.now(IST)
    
    # Target is 06:00 today or tomorrow
    morning = now_ist.replace(
        hour=NIGHT_MODE_END_HOUR,
        minute=0,
        second=0,
        microsecond=0
    )
    
    if now_ist >= morning:
        # Already past 6 AM, this shouldn't happen during night mode
        # but calculate for tomorrow just in case
        from datetime import timedelta
        morning += timedelta(days=1)
    
    delta = morning - now_ist
    return int(delta.total_seconds())


def format_time_remaining(seconds: int) -> str:
    """Format seconds into human-readable string."""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"
