"""
Utility functions for the Worker service.
"""

from datetime import datetime
import pytz

from config import TIMEZONE, NIGHT_MODE_START_HOUR, NIGHT_MODE_END_HOUR

IST = pytz.timezone(TIMEZONE)


async def is_night_mode() -> bool:
    """
    Check if current time is within night mode hours.
    Night mode: 00:00 - 06:00 IST
    Overrides based on global settings:
    - force=on: always true
    - force=off: always false
    - force=auto: time-based
    """
    from db.models import get_global_settings
    settings = await get_global_settings()
    force = settings.get("night_mode_force", "auto")
    
    if force == "on":
        return True
    if force == "off":
        return False
        
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


import logging

class UserLogAdapter(logging.LoggerAdapter):
    """
    Adapter that adds user context to log messages.
    Usage:
        logger = UserLogAdapter(original_logger, {'user_id': 123, 'phone': '+1234'})
        logger.info("Message") -> "[User 123][+1234] Message"
    """
    def process(self, msg, kwargs):
        user_id = self.extra.get('user_id', 'Unknown')
        phone = self.extra.get('phone', 'Unknown')
        return f"[User {user_id}][{phone}] {msg}", kwargs


# ═══════════════════════════════════════════════════════
#  CENTRAL LOG CHANNEL — Styled Helpers
# ═══════════════════════════════════════════════════════

_log_bot = None  # Singleton bot instance
_log_bot_init_failed = False  # Prevent repeated init attempts on permanent failures

async def _get_log_bot():
    """Get or create a cached Bot instance for the log channel."""
    global _log_bot, _log_bot_init_failed
    if _log_bot_init_failed:
        return None
    if _log_bot is None:
        from config import MAIN_BOT_TOKEN
        if not MAIN_BOT_TOKEN:
            logging.getLogger(__name__).warning("MAIN_BOT_TOKEN is empty — cannot send to log channel")
            _log_bot_init_failed = True
            return None
        try:
            from telegram import Bot
            _log_bot = Bot(token=MAIN_BOT_TOKEN)
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to initialize log Bot: {e}")
            _log_bot_init_failed = True
            return None
    return _log_bot


async def send_central_log(text: str):
    """Send an update log to the central LOG_CHANNEL_ID using MAIN_BOT_TOKEN."""
    from config import LOG_CHANNEL_ID
    if not LOG_CHANNEL_ID:
        logging.getLogger(__name__).debug("LOG_CHANNEL_ID is not set — skipping central log")
        return
    try:
        bot = await _get_log_bot()
        if not bot:
            return
        # Truncate messages over 4096 chars (Telegram limit)
        if len(text) > 4096:
            text = text[:4090] + "\n..."
        await bot.send_message(chat_id=LOG_CHANNEL_ID, text=text, parse_mode="HTML")
    except Exception as e:
        _logger = logging.getLogger(__name__)
        error_str = str(e)
        # Log full error details for debugging
        _logger.error(f"Failed to send central log to {LOG_CHANNEL_ID}: {error_str}")
        # If it's a parse error, retry without HTML formatting
        if "parse" in error_str.lower() or "can't" in error_str.lower():
            try:
                await bot.send_message(chat_id=LOG_CHANNEL_ID, text=text)
                _logger.info("Retried without HTML parse_mode — success")
            except Exception as retry_e:
                _logger.error(f"Retry without parse_mode also failed: {retry_e}")


def mask_phone(phone: str) -> str:
    """Mask a phone number for privacy: +91****82"""
    if not phone or len(phone) < 6:
        return "****"
    return f"{phone[:3]}****{phone[-2:]}"


def build_live_update(phone: str, chat_title: str, action: str, index: int, total: int) -> str:
    """Build a styled live update message for a single successful send."""
    now_ist = datetime.now(IST)
    time_str = now_ist.strftime("%I:%M %p")
    masked = mask_phone(phone)
    progress_pct = int((index / total) * 100) if total > 0 else 0

    # Progress bar visual
    filled = progress_pct // 10
    bar = "█" * filled + "░" * (10 - filled)

    return (
        f"<b>┌─── 🟢 LIVE UPDATE ───</b>\n"
        f"<b>│</b>\n"
        f"<b>│</b> 👤 Account: <code>{masked}</code>\n"
        f"<b>│</b> 📢 Target:  <code>{chat_title}</code>\n"
        f"<b>│</b> ⚡ Action:  {action}\n"
        f"<b>│</b> 📊 Progress: [{bar}] {progress_pct}%\n"
        f"<b>│</b> ⏱ Time:    {time_str} IST\n"
        f"<b>│</b>\n"
        f"<b>└─── {index}/{total} ───</b>"
    )


def build_cycle_report(phone: str, success_groups: list, failed_groups: list, send_mode: str, interval: int, cycle_duration: float = 0, skipped: int = 0) -> str:
    """Build a premium styled cycle summary report — V6 with metrics."""
    now_ist = datetime.now(IST)
    time_str = now_ist.strftime("%d %b %Y • %I:%M %p IST")
    masked = mask_phone(phone)
    total = len(success_groups) + len(failed_groups)
    rate = int((len(success_groups) / total) * 100) if total > 0 else 0

    # Duration formatting
    if cycle_duration > 0:
        dur_min = int(cycle_duration // 60)
        dur_sec = int(cycle_duration % 60)
        dur_str = f"{dur_min}m {dur_sec}s" if dur_min > 0 else f"{dur_sec}s"
        throughput = f"{(len(success_groups) / (cycle_duration / 60)):.1f}" if cycle_duration > 0 else "N/A"
    else:
        dur_str = "N/A"
        throughput = "N/A"

    # Speed rating
    if cycle_duration > 0 and total > 0:
        avg_per_group = cycle_duration / total
        if avg_per_group < 30:
            speed_badge = "⚡ BLAZING"
        elif avg_per_group < 60:
            speed_badge = "🚀 FAST"
        elif avg_per_group < 120:
            speed_badge = "🟢 NORMAL"
        else:
            speed_badge = "🐢 SLOW"
    else:
        speed_badge = "—"

    # Header
    text = (
        f"<b>╔══════════════════════════╗</b>\n"
        f"<b>║   📊 CYCLE REPORT        ║</b>\n"
        f"<b>╚══════════════════════════╝</b>\n\n"
        f"👤 <b>Account:</b> <code>{masked}</code>\n"
        f"🕐 <b>Completed:</b> {time_str}\n"
        f"⚙️ <b>Mode:</b> {send_mode.title()} | <b>Interval:</b> {interval}m\n\n"
    )

    # Stats bar
    text += f"<b>━━━ DELIVERY STATS ━━━</b>\n"
    text += f"  ✅ Delivered:  <b>{len(success_groups)}</b>\n"
    text += f"  ❌ Failed:     <b>{len(failed_groups)}</b>\n"
    if skipped > 0:
        text += f"  ⏭ Skipped:    <b>{skipped}</b> (dedup)\n"
    text += f"  📈 Success:    <b>{rate}%</b>\n\n"

    # V6: Performance metrics
    text += f"<b>━━━ PERFORMANCE ━━━</b>\n"
    text += f"  ⏱ Duration:   <b>{dur_str}</b>\n"
    text += f"  📊 Throughput: <b>{throughput} groups/min</b>\n"
    text += f"  {speed_badge}\n\n"

    # Success list
    if success_groups:
        text += f"<b>✅ SENT ({len(success_groups)}):</b>\n"
        for i, g in enumerate(success_groups[:15], 1):
            text += f"  {i}. {g}\n"
        if len(success_groups) > 15:
            text += f"  <i>...+{len(success_groups)-15} more groups</i>\n"
        text += "\n"

    # Failed list
    if failed_groups:
        text += f"<b>❌ FAILED ({len(failed_groups)}):</b>\n"
        for i, g in enumerate(failed_groups[:10], 1):
            text += f"  {i}. {g}\n"
        if len(failed_groups) > 10:
            text += f"  <i>...+{len(failed_groups)-10} more groups</i>\n"
        text += "\n"

    text += f"<b>━━━━━━━━━━━━━━━━━━━━━━━━</b>"
    return text


def build_error_log(phone: str, chat_title: str, error_type: str, detail: str = "") -> str:
    """Build a styled error/warning log entry."""
    now_ist = datetime.now(IST)
    time_str = now_ist.strftime("%I:%M %p")
    masked = mask_phone(phone)

    return (
        f"<b>⚠️ ALERT</b> | {time_str} IST\n"
        f"👤 <code>{masked}</code>\n"
        f"📢 <code>{chat_title}</code>\n"
        f"🔴 {error_type}"
        + (f"\n📝 <i>{detail[:60]}</i>" if detail else "")
    )


def build_cleanup_log(phone: str, removed_count: int, removed_titles: list = None) -> str:
    """Build a styled auto-cleanup log."""
    masked = mask_phone(phone)
    now_ist = datetime.now(IST)
    time_str = now_ist.strftime("%I:%M %p")

    text = (
        f"<b>🧹 AUTO-CLEANUP</b> | {time_str} IST\n"
        f"👤 <code>{masked}</code>\n"
        f"🗑 Removed <b>{removed_count}</b> failing group(s)\n"
    )
    if removed_titles:
        for t in removed_titles[:5]:
            text += f"  • {t}\n"
        if len(removed_titles) > 5:
            text += f"  <i>...+{len(removed_titles)-5} more</i>\n"
    return text


def build_session_start_log(phone: str, group_count: int, plan_status: str) -> str:
    """Build a styled session start notification."""
    now_ist = datetime.now(IST)
    time_str = now_ist.strftime("%I:%M %p IST")
    masked = mask_phone(phone)

    return (
        f"<b>🟢 SESSION STARTED</b> | {time_str}\n"
        f"👤 <code>{masked}</code>\n"
        f"📂 Groups: <b>{group_count}</b>\n"
        f"💎 Plan: <b>{plan_status}</b>"
    )

