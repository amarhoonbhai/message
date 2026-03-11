"""
Shared utility functions for Group Message Scheduler.
"""

import re

def escape_markdown(text: str) -> str:
    """
    Escape markdown characters for Telegram's legacy Markdown parser.
    Escapes: _, *, [, ]
    """
    if not text:
        return ""
    # We only escape characters that are used in our templates or could be accidentally typed by users.
    # Legacy Markdown (V1) is tricky. V2 is more strict but V1 is what's being used here.
    return re.sub(r'([_*\[\]])', r'\\\1', str(text))

def build_connection_success_text(phone: str, plan: dict) -> str:
    """
    Build standardized success message after account connection.
    Used by both OTP and 2FA flows.
    """
    from datetime import datetime
    
    if plan and plan.get("status") == "active" and plan.get("expires_at", datetime.min) > datetime.utcnow():
        plan_type = plan.get("plan_type", "trial")
        expires_at = plan["expires_at"]
        days_left = (expires_at - datetime.utcnow()).days
        hours_left = (expires_at - datetime.utcnow()).seconds // 3600

        if plan_type == "trial":
            # Trial user
            time_left = f"{days_left}d {hours_left}h" if days_left > 0 else f"{hours_left}h"
            return f"""
✅ *Connected Successfully!*

📱 `{phone}` is now linked to your account.

🏅 *Plan:* Free Trial
⏳ *Time Left:* {time_left}

💡 Invite *3 friends* to earn +7 bonus days!
Open the dashboard to add groups and start sending.
"""
        else:
            # Paid/premium user
            plan_label = plan_type.upper()
            time_left = f"{days_left}d {hours_left}h" if days_left > 0 else f"{hours_left}h"
            return f"""
✅ *Connected Successfully!*

📱 `{phone}` is now linked to your account.

💎 *Plan:* {plan_label} Premium
⏳ *Remaining:* {time_left}

🚀 Your premium plan is active. Open the dashboard to configure groups and intervals.
"""
    else:
        # No active plan (expired or missing)
        return f"""
✅ *Connected Successfully!*

📱 `{phone}` is now linked to your account.

⚠️ *No Active Plan Found*
Your plan may have expired or wasn't assigned yet.

🎁 Redeem a code or contact support to activate your plan.
"""
