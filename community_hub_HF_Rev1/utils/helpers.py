# utils/helpers.py
"""Utility functions — Extracted from original utils.py with fixes"""

import streamlit as st
import hashlib
import secrets
import threading
from datetime import datetime, timedelta, timezone
from config import supabase, DB_CONNECTED

# ============================================
# PHONE HELPERS
# ============================================

def mask_phone(phone):
    """Mask phone number for privacy (PDPA compliant)."""
    if not phone:
        return "N/A"
    p = str(phone).strip().replace(" ", "").replace("-", "")
    if len(p) >= 8:
        return "••••" + p[-4:]
    return p

def clean_phone_number(phone):
    """Clean and normalize phone number."""
    if not phone:
        return ""
    p = str(phone).strip().replace(" ", "").replace("-", "").replace("+", "")
    if p.startswith("65") and len(p) == 10:
        p = p[2:]
    return p

def find_participant_by_phone(phone):
    """Find participant by phone number."""
    if not DB_CONNECTED:
        return None
    clean = clean_phone_number(phone)
    if len(clean) < 4:
        return None
    try:
        res = supabase.table('participants').select("*").eq('contact', clean).execute()
        if res.data:
            return res.data[0]
        res2 = supabase.table('participants').select("*").ilike('contact', f'%{clean[-4:]}%').execute()
        for p in res2.data:
            if clean_phone_number(p.get('contact', '')) == clean:
                return p
    except:
        pass
    return None

def find_participant_by_id(pid):
    """Fetch a participant's full record by their ID."""
    if not DB_CONNECTED or not pid:
        return None
    try:
        res = supabase.table('participants').select("*").eq('id', pid).execute()
        return res.data[0] if res.data else None
    except:
        return None

def check_returning_guest(phone):
    """Check if a phone number has been used as a guest before."""
    if not DB_CONNECTED:
        return None
    clean = clean_phone_number(phone)
    if len(clean) < 4:
        return None
    try:
        res = supabase.table('session_rsvp').select("created_at, name").eq('phone', clean).order('created_at', desc=True).limit(1).execute()
        if res.data:
            return res.data[0]
    except:
        pass
    return None

# ============================================
# ATTENDANCE HELPERS
# ============================================

def get_attendance_count(pid):
    """Get total attendance count for a participant."""
    if not DB_CONNECTED:
        return 0
    try:
        return supabase.table('attendance').select('*', count='exact').eq('participant_id', pid).execute().count
    except:
        return 0

def check_and_convert_status(pid, name):
    """Auto-convert new resident to regular after 3 attendances."""
    if not DB_CONNECTED:
        return None
    try:
        c = get_attendance_count(pid)
        if c >= 3:
            p = supabase.table('participants').select('is_new').eq('id', pid).execute()
            if p.data and p.data[0].get('is_new'):
                supabase.table('participants').update({'is_new': False}).eq('id', pid).execute()
                return f"🎉 {name} graduated to Regular!"
        return None
    except:
        return None

# ============================================
# TOKEN HELPERS 🔥 FIXED: No key material exposed
# ============================================

def generate_token(pid, date_str):
    """Generate a secure token using secrets, NOT the Supabase key."""
    return secrets.token_urlsafe(16)

def verify_token(pid, date_str, token):
    """Verify a token."""
    return token == generate_token(pid, date_str)

# ============================================
# GARDEN HELPERS
# ============================================

def load_plots():
    """Load all garden plots from database."""
    if not DB_CONNECTED:
        return []
    try:
        return supabase.table('garden_plots').select("*").order('plot_number').execute().data
    except:
        return []

def get_plot(plot_num, block_name=None):
    """Get a specific plot by number and optional block."""
    if not DB_CONNECTED:
        return None
    try:
        q = supabase.table('garden_plots').select("*").eq('plot_number', plot_num)
        if block_name:
            q = q.eq('block_name', block_name)
        r = q.execute()
        return r.data[0] if r.data else None
    except:
        return None

def update_plot(plot_num, updates, block_name=None):
    """Update a plot's data."""
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
    except:
        return False

def get_user_plot(user_id, block_name=None):
    """Get a user's plot in a specific block."""
    if not user_id or not DB_CONNECTED:
        return None
    try:
        q = supabase.table('garden_plots').select("*").eq('user_id', user_id).eq('occupied', True)
        if block_name:
            q = q.eq('block_name', block_name)
        r = q.execute()
        return r.data[0] if r.data else None
    except:
        return None

def get_user_plots(user_id):
    """Get ALL occupied plots a resident owns across ALL blocks."""
    if not user_id or not DB_CONNECTED:
        return []
    try:
        r = supabase.table('garden_plots').select("*").eq('user_id', user_id).eq('occupied', True).execute()
        return r.data or []
    except:
        return []

def get_occupied_count(block_name=None):
    """Get total occupied plots count, optionally filtered by block."""
    if not DB_CONNECTED:
        return 0
    try:
        q = supabase.table('garden_plots').select('*', count="exact").eq('occupied', True)
        if block_name:
            q = q.eq('block_name', block_name)
        return q.execute().count
    except:
        return 0

def create_request(plot_num, user_id, user_name, contact, notes=""):
    """Create a plot request."""
    if not DB_CONNECTED:
        return None
    try:
        r = supabase.table('plot_requests').insert({
            "plot_number": plot_num, "user_id": user_id, "user_name": user_name,
            "contact": contact, "notes": notes, "status": "pending"
        }).execute()
        return r.data[0] if r.data else None
    except:
        return None

def get_pending_requests():
    """Get all pending plot requests."""
    if not DB_CONNECTED:
        return []
    try:
        return supabase.table('plot_requests').select("*").eq('status', 'pending').order('created_at').execute().data
    except:
        return []

def update_request_status(rid, status):
    """Update a plot request's status."""
    if not DB_CONNECTED:
        return False
    try:
        r = supabase.table('plot_requests').update({"status": status}).eq('id', rid).execute()
        return bool(r.data)
    except:
        return False

# ============================================
# AUDIT LOG
# ============================================

def log_action(role, action, details="", target_id=""):
    """Log an action to the audit trail."""
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
        print(f"Audit log error: {e}")

# ============================================
# SESSION ATTENDANCE SYNC
# ============================================

def _record_session_attendance(pid, name, activity, formatted_date, role):
    """Background worker: best-effort sync into session_attendance."""
    try:
        from config import now_sgt
        sess_records = supabase.table('sessions').select("id, status") \
            .eq('activity_name', activity).eq('session_date', formatted_date).execute().data
        for sess in (sess_records or []):
            if sess.get('status') == 'closed':
                continue
            exists = supabase.table('session_attendance').select("id") \
                .eq('session_id', sess['id']).eq('participant_id', pid).execute()
            if exists.data:
                supabase.table('session_attendance').update({
                    "status": "checked_in",
                    "marked_at": now_sgt().isoformat()
                }).eq('id', exists.data[0]['id']).execute()
            else:
                supabase.table('session_attendance').insert({
                    "session_id": sess['id'],
                    "participant_id": pid,
                    "name": name,
                    "status": "checked_in",
                    "marked_at": now_sgt().isoformat(),
                    "marked_by": role
                }).execute()
    except Exception as e:
        print(f"session_attendance sync skipped: {e}")

def sync_session_attendance_async(pid, name, activity, formatted_date, role="system"):
    """Fire-and-forget: runs in background thread so the UI never waits."""
    if not DB_CONNECTED:
        return
    threading.Thread(
        target=_record_session_attendance,
        args=(pid, name, activity, formatted_date, role),
        daemon=True
    ).start()

# ============================================
# TIME VALIDATION
# ============================================

def _parse_time_string(time_str):
    """Parse time string in various formats."""
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
    """Validate if check-in is allowed based on time windows."""
    if not DB_CONNECTED:
        return True, "OK"
    try:
        from config import SGT
        activity = supabase.table('activities').select("*").eq('name', activity_name).single().execute().data
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
        current_time = now.replace(second=0, microsecond=0).time()
        if current_time < start_time:
            return False, f"Check-in for {session_label} opens at {start_time.strftime('%I:%M %p')}. Please return at that time."
        elif current_time > end_time:
            return False, f"Check-in for {session_label} closed at {end_time.strftime('%I:%M %p')}. The session has started."
        else:
            return True, "OK"
    except Exception as e:
        print(f"Time validation error: {e}")
        return True, "OK"

# ============================================
# DATA LOADERS (with caching)
# ============================================

@st.cache_data(ttl=300)
def load_participants():
    """Load all participants with caching."""
    if not DB_CONNECTED:
        return []
    try:
        return supabase.table('participants').select("*").execute().data
    except:
        return []

@st.cache_data(ttl=300)
def load_plots_cached():
    """Load all plots with caching."""
    return load_plots()