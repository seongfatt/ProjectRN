# utils/helpers.py
"""Helper functions — Extracted from utils.py (NOT used yet)"""

from datetime import datetime, timedelta, timezone
from config import supabase, DB_CONNECTED

# ========== TIMEZONE HELPER ==========
SGT = timezone(timedelta(hours=8))

def now_sgt():
    """Return current datetime in Singapore Time (UTC+8)."""
    return datetime.now(SGT)

# ========== MEMBER BREAKDOWN HELPER ==========
def get_member_breakdown(participants):
    """Get breakdown of member types."""
    active = [p for p in participants if p.get('active', True)]
    return {
        'total': len(active),
        'resident': sum(1 for p in active if p.get('member_type', 'Resident') == 'Resident'),
        'rn': sum(1 for p in active if p.get('member_type') == 'RN Member'),
        'volunteer': sum(1 for p in active if p.get('member_type') == 'Volunteer Member'),
    }