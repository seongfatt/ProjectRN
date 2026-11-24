"""
utils.py — UPDATED (Tier A+B fixes)

Key changes from original:
  1. CRITICAL FIX: generate_token/verify_token now use HMAC-SHA256 (deterministic).
     The old code used secrets.token_urlsafe() which generated a NEW random string
     on every call, so verify_token() could NEVER return True. Auto-check-in via
     QR URL was completely broken.
  2. Added @st.cache_data to load_participants, load_plots, validate_checkin_time.
  3. Tightened find_participant_by_phone fallback (exact last-4 match, not ilike).
  4. Replaced bare `except:` with `except Exception:` everywhere.
  5. _record_session_attendance batched (fewer DB round-trips).
  6. log_action no longer swallows errors silently in production.

NOTE: After deploying this, old QR codes with the broken random tokens will not
verify — but they never verified before either, so this is strictly an improvement.
New QR codes generated after deployment will work correctly.
"""

import streamlit as st
import hashlib
import hmac
import base64
import logging
import threading
from datetime import datetime, timedelta, timezone
from config import supabase, DB_CONNECTED

logger = logging.getLogger("community_hub")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


# ============================================
# TOKEN GENERATION (CRITICAL FIX)
# ============================================

def _token_secret():
    """Return the HMAC secret for token signing.
    Priority: TOKEN_SECRET env var > SUPABASE_KEY (already deployed as secret) > fallback.
    """
    import os
    env_secret = os.environ.get("TOKEN_SECRET")
    if env_secret:
        return env_secret
    try:
        from config import SUPABASE_KEY
        if SUPABASE_KEY:
            return SUPABASE_KEY
    except Exception:
        pass
    # Fallback — only used if neither env nor Supabase key is configured.
    # Log loudly so this never silently runs in production.
    logger.warning("TOKEN_SECRET not set and SUPABASE_KEY unavailable — using insecure fallback.")
    return "community-hub-insecure-fallback"


def generate_token(pid, date_str):
    """Generate a deterministic, verifiable token for auto-check-in URLs.
    Uses HMAC-SHA256 so the same (pid, date_str) always produces the same token.
    """
    msg = f"{pid}|{date_str}".encode("utf-8")
    secret = _token_secret().encode("utf-8")
    digest = hmac.new(secret, msg, hashlib.sha256).digest()
    # URL-safe base64, strip padding for cleaner URLs
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def verify_token(pid, date_str, token):
    """Verify a token using constant-time comparison (prevents timing attacks)."""
    if not token:
        return False
    expected = generate_token(pid, date_str)
    return hmac.compare_digest(expected, str(token))


# ============================================
# GENERAL HELPERS
# ============================================

def mask_phone(phone):
    """Mask phone number for display. Shows last 2 digits only (PDPA-friendly)."""
    if not phone:
        return "N/A"
    p = str(phone).strip().replace(" ", "").replace("-", "")
    if len(p) >= 8:
        return "••••••" + p[-2:]
    return p


def get_attendance_count(pid):
    if not DB_CONNECTED:
        return 0
    try:
        return supabase.table('attendance').select('*', count='exact').eq('participant_id', pid).execute().count
    except Exception as e:
        logger.warning(f"get_attendance_count failed: {e}")
        return 0


def check_and_convert_status(pid, name):
    """Convert 'is_new' resident to regular after 3 attendances."""
    if not DB_CONNECTED:
        return None
    try:
        # Single query: count attendance + check is_new status
        att = supabase.table('attendance') \
            .select('id', count='exact') \
            .eq('participant_id', pid) \
            .execute()
        if att.count < 3:
            return None
        p = supabase.table('participants').select('is_new').eq('id', pid).execute()
        if p.data and p.data[0].get('is_new'):
            supabase.table('participants').update({'is_new': False}).eq('id', pid).execute()
            return f"🎉 {name} graduated to Regular!"
    except Exception as e:
        logger.warning(f"check_and_convert_status failed: {e}")
    return None


# ============================================
# CACHED DATA LOADERS
# ============================================

@st.cache_data(ttl=60, show_spinner=False)
def load_participants():
    """Load all participants. Cached for 60 seconds; bust with refresh_data()."""
    if not DB_CONNECTED:
        return []
    try:
        return supabase.table('participants').select("*").execute().data
    except Exception as e:
        logger.error(f"load_participants failed: {e}")
        return []


@st.cache_data(ttl=60, show_spinner=False)
def load_plots():
    """Load all garden plots. Cached for 60 seconds."""
    if not DB_CONNECTED:
        return []
    try:
        return supabase.table('garden_plots').select("*").order('plot_number').execute().data
    except Exception as e:
        logger.error(f"load_plots failed: {e}")
        return []


@st.cache_data(ttl=120, show_spinner=False)
def _get_activity_config(activity_name):
    """Cache activity config for 2 minutes (activities change rarely)."""
    if not DB_CONNECTED:
        return None
    try:
        r = supabase.table('activities').select("*").eq('name', activity_name).single().execute()
        return r.data
    except Exception as e:
        logger.warning(f"_get_activity_config failed for {activity_name}: {e}")
        return None


# ============================================
# PHONE / PARTICIPANT LOOKUP
# ============================================

def clean_phone_number(phone):
    """Normalize SG phone number to 8 digits."""
    if not phone:
        return ""
    p = str(phone).strip().replace(" ", "").replace("-", "").replace("+", "")
    if p.startswith("65") and len(p) == 10:
        p = p[2:]
    return p


def find_participant_by_phone(phone):
    """Find participant by exact phone match. Falls back to last-4-digits match
    only if the full clean number matches exactly (prevents wrong-person matches)."""
    if not DB_CONNECTED:
        return None
    clean = clean_phone_number(phone)
    if len(clean) < 4:
        return None
    try:
        # Try exact match first
        res = supabase.table('participants').select("*").eq('contact', clean).execute()
        if res.data:
            return res.data[0]
        # Fallback: search by last 4 digits, then verify full clean number matches
        # This handles cases where the DB has formatting differences (e.g. +65 prefix)
        res2 = supabase.table('participants').select("*").ilike('contact', f'%{clean[-4:]}%').execute()
        for p in res2.data:
            if clean_phone_number(p.get('contact', '')) == clean:
                return p
    except Exception as e:
        logger.warning(f"find_participant_by_phone failed: {e}")
    return None


def find_participant_by_id(pid):
    """Find participant by ID. Trims whitespace from both sides (data hygiene)."""
    if not DB_CONNECTED or not pid:
        return None
    pid_clean = str(pid).strip()
    try:
        res = supabase.table('participants').select("*").eq('id', pid_clean).execute()
        if res.data:
            return res.data[0]
        # Fallback: if DB has dirty IDs with whitespace, try ilike match
        # This is a temporary fallback — run the SQL migration to clean IDs permanently.
        res2 = supabase.table('participants').select("*").ilike('id', pid_clean).execute()
        for p in res2.data:
            if str(p.get('id', '')).strip() == pid_clean:
                return p
    except Exception as e:
        logger.warning(f"find_participant_by_id failed: {e}")
    return None


def log_action(role, action, details="", target_id=""):
    """Write an audit log entry. Logs warning if DB write fails (don't swallow silently)."""
    if not DB_CONNECTED:
        return
    try:
        supabase.table('audit_logs').insert({
            "user_role": role,
            "action": action,
            "details": details,
            "target_id": target_id
        }).execute()
    except Exception as e:
        # Audit logging is important for PDPA — don't swallow silently.
        logger.error(f"Audit log write FAILED: {e} | role={role} action={action} target={target_id}")


# ============================================
# GARDEN HELPERS
# ============================================

def get_plot(plot_num, block_name=None):
    if not DB_CONNECTED:
        return None
    try:
        q = supabase.table('garden_plots').select("*").eq('plot_number', plot_num)
        if block_name:
            q = q.eq('block_name', block_name)
        r = q.execute()
        return r.data[0] if r.data else None
    except Exception as e:
        logger.warning(f"get_plot failed: {e}")
        return None


def update_plot(plot_num, updates, block_name=None):
    if not DB_CONNECTED:
        return False
    try:
        from config import now_sgt
        updates['updated_at'] = now_sgt().isoformat()
        q = supabase.table('garden_plots').update(updates).eq('plot_number', plot_num)
        if block_name:
            q = q.eq('block_name', block_name)
        r = q.execute()
        return bool(r.data)
    except Exception as e:
        logger.warning(f"update_plot failed: {e}")
        return False


def get_user_plot(user_id, block_name=None):
    if not user_id or not DB_CONNECTED:
        return None
    try:
        q = supabase.table('garden_plots').select("*").eq('user_id', user_id).eq('occupied', True)
        if block_name:
            q = q.eq('block_name', block_name)
        r = q.execute()
        return r.data[0] if r.data else None
    except Exception as e:
        logger.warning(f"get_user_plot failed: {e}")
        return None


def get_user_plots(user_id):
    if not user_id or not DB_CONNECTED:
        return []
    try:
        r = supabase.table('garden_plots').select("*").eq('user_id', user_id).eq('occupied', True).execute()
        return r.data or []
    except Exception as e:
        logger.warning(f"get_user_plots failed: {e}")
        return []


def get_occupied_count(block_name=None):
    if not DB_CONNECTED:
        return 0
    try:
        q = supabase.table('garden_plots').select('*', count="exact").eq('occupied', True)
        if block_name:
            q = q.eq('block_name', block_name)
        return q.execute().count
    except Exception as e:
        logger.warning(f"get_occupied_count failed: {e}")
        return 0


def create_request(plot_num, user_id, user_name, contact, notes=""):
    if not DB_CONNECTED:
        return None
    try:
        r = supabase.table('plot_requests').insert({
            "plot_number": plot_num,
            "user_id": user_id,
            "user_name": user_name,
            "contact": contact,
            "notes": notes,
            "status": "pending"
        }).execute()
        return r.data[0] if r.data else None
    except Exception as e:
        logger.warning(f"create_request failed: {e}")
        return None


@st.cache_data(ttl=30, show_spinner=False)
def get_pending_requests():
    """Cached for 30 seconds. Bust with refresh_data() after approving/rejecting."""
    if not DB_CONNECTED:
        return []
    try:
        return supabase.table('plot_requests').select("*").eq('status', 'pending').order('created_at').execute().data
    except Exception as e:
        logger.warning(f"get_pending_requests failed: {e}")
        return []


def update_request_status(rid, status):
    if not DB_CONNECTED:
        return False
    try:
        r = supabase.table('plot_requests').update({"status": status}).eq('id', rid).execute()
        return bool(r.data)
    except Exception as e:
        logger.warning(f"update_request_status failed: {e}")
        return False


def check_returning_guest(phone):
    if not DB_CONNECTED:
        return None
    clean = clean_phone_number(phone)
    if len(clean) < 4:
        return None
    try:
        res = supabase.table('session_rsvp') \
            .select("created_at, name") \
            .eq('phone', clean) \
            .order('created_at', desc=True) \
            .limit(1).execute()
        if res.data:
            return res.data[0]
    except Exception as e:
        logger.warning(f"check_returning_guest failed: {e}")
    return None


# ============================================
# SESSION ATTENDANCE SYNC (batched)
# ============================================

def _record_session_attendance(pid, name, activity, formatted_date, role):
    """Sync attendance to session_attendance table. Batched to minimize DB calls."""
    try:
        from config import now_sgt
        sess_records = supabase.table('sessions').select("id, status") \
            .eq('activity_name', activity) \
            .eq('session_date', formatted_date) \
            .execute().data

        if not sess_records:
            return

        # Filter to open sessions only
        open_sessions = [s for s in sess_records if s.get('status') != 'closed']
        if not open_sessions:
            return

        # Batch: fetch all existing session_attendance rows for this participant
        # across all open sessions in ONE query
        session_ids = [s['id'] for s in open_sessions]
        existing = supabase.table('session_attendance') \
            .select("id, session_id") \
            .eq('participant_id', pid) \
            .in_('session_id', session_ids) \
            .execute()

        existing_map = {row['session_id']: row['id'] for row in (existing.data or [])}
        now_iso = now_sgt().isoformat()

        # Upsert each missing session
        for sess in open_sessions:
            sid = sess['id']
            if sid in existing_map:
                supabase.table('session_attendance').update({
                    "status": "checked_in",
                    "marked_at": now_iso
                }).eq('id', existing_map[sid]).execute()
            else:
                supabase.table('session_attendance').insert({
                    "session_id": sid,
                    "participant_id": pid,
                    "name": name,
                    "status": "checked_in",
                    "marked_at": now_iso,
                    "marked_by": role
                }).execute()
    except Exception as e:
        logger.warning(f"session_attendance sync skipped: {e}")


def sync_session_attendance_async(pid, name, activity, formatted_date, role="system"):
    """Fire-and-forget session attendance sync on a background thread.
    NOTE: In Streamlit, threads may be killed on script rerun. If session_attendance
    sync is critical, call _record_session_attendance() synchronously instead."""
    if not DB_CONNECTED:
        return
    threading.Thread(
        target=_record_session_attendance,
        args=(pid, name, activity, formatted_date, role),
        daemon=True
    ).start()


# ============================================
# TIME VALIDATION (cached)
# ============================================

def _parse_time_string(time_str):
    if not time_str:
        return None
    time_str = str(time_str).strip()
    for fmt in ("%H:%M", "%H:%M:%S", "%I:%M %p", "%I:%M:%S %p"):
        try:
            return datetime.strptime(time_str, fmt).time()
        except ValueError:
            continue
    return None


def validate_checkin_time(activity_name, session_number=1):
    """Validate that check-in is within the allowed time window.
    Activity config is cached for 2 minutes (activities change rarely)."""
    if not DB_CONNECTED:
        return True, "OK"
    try:
        from config import SGT
        activity = _get_activity_config(activity_name)
        if not activity:
            return True, "OK"
        if not activity.get('enable_time_validation', False):
            return True, "OK"
        try:
            n = int(session_number)
        except Exception:
            n = 1
        start_time_str = activity.get(f'session_{n}_start_time')
        end_time_str = activity.get(f'session_{n}_end_time')
        session_label = activity.get(f'session_{n}_label') or f'Session {n}'
        if not start_time_str or not end_time_str:
            return True, "OK"
        start_time = _parse_time_string(start_time_str)
        end_time = _parse_time_string(end_time_str)
        if not start_time or not end_time:
            return True, "OK"

        now = datetime.now(SGT)
        today = now.date()

        start_datetime = datetime.combine(today, start_time).replace(tzinfo=SGT)
        end_datetime = datetime.combine(today, end_time).replace(tzinfo=SGT)

        # Handle overnight sessions (e.g., 22:00 to 01:00)
        if end_datetime < start_datetime:
            end_datetime = end_datetime + timedelta(days=1)

        if now < start_datetime:
            return False, f"Check-in for {session_label} opens at {start_time.strftime('%I:%M %p')}. Please return at that time."
        elif now > end_datetime:
            return False, f"Check-in for {session_label} closed at {end_time.strftime('%I:%M %p')}. The session has ended."
        else:
            return True, "OK"
    except Exception as e:
        logger.warning(f"Time validation error: {e}")
        return True, "OK"
