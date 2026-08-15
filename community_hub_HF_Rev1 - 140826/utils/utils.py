import streamlit as st
import hashlib
import secrets
import threading
from datetime import datetime, timedelta, timezone
from config import supabase, DB_CONNECTED

# ============================================
# GENERAL HELPERS
# ============================================

def mask_phone(phone):
    if not phone:
        return "N/A"
    p = str(phone).strip().replace(" ", "").replace("-", "")
    if len(p) >= 8:
        return "••••" + p[-4:]
    return p

def get_attendance_count(pid):
    if not DB_CONNECTED:
        return 0
    try:
        return supabase.table('attendance').select('*', count='exact').eq('participant_id', pid).execute().count
    except:
        return 0

def check_and_convert_status(pid, name):
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

def generate_token(pid, date_str):
    """Generate a secure token using secrets."""
    return secrets.token_urlsafe(16)

def verify_token(pid, date_str, token):
    return token == generate_token(pid, date_str)

def load_participants():
    if not DB_CONNECTED:
        return []
    try:
        return supabase.table('participants').select("*").execute().data
    except:
        return []

def clean_phone_number(phone):
    if not phone:
        return ""
    p = str(phone).strip().replace(" ", "").replace("-", "").replace("+", "")
    if p.startswith("65") and len(p) == 10:
        p = p[2:]
    return p

def find_participant_by_phone(phone):
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
    if not DB_CONNECTED or not pid:
        return None
    try:
        res = supabase.table('participants').select("*").eq('id', pid).execute()
        return res.data[0] if res.data else None
    except:
        return None

def log_action(role, action, details="", target_id=""):
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
# GARDEN HELPERS
# ============================================

def load_plots():
    if not DB_CONNECTED:
        return []
    try:
        return supabase.table('garden_plots').select("*").order('plot_number').execute().data
    except:
        return []

def get_plot(plot_num, block_name=None):
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
    if not user_id or not DB_CONNECTED:
        return []
    try:
        r = supabase.table('garden_plots').select("*").eq('user_id', user_id).eq('occupied', True).execute()
        return r.data or []
    except:
        return []

def get_occupied_count(block_name=None):
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
    except:
        return None

def get_pending_requests():
    if not DB_CONNECTED:
        return []
    try:
        return supabase.table('plot_requests').select("*").eq('status', 'pending').order('created_at').execute().data
    except:
        return []

def update_request_status(rid, status):
    if not DB_CONNECTED:
        return False
    try:
        r = supabase.table('plot_requests').update({"status": status}).eq('id', rid).execute()
        return bool(r.data)
    except:
        return False

def check_returning_guest(phone):
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
# SESSION ATTENDANCE SYNC
# ============================================

def _record_session_attendance(pid, name, activity, formatted_date, role):
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