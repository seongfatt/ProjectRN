import streamlit as st
import hashlib
from datetime import datetime, timedelta, timezone
from config import supabase, DB_CONNECTED, SUPABASE_KEY
import threading

def _record_session_attendance(pid, name, activity, formatted_date, role):
    """Background worker: best-effort sync into session_attendance."""
    try:
        sgt_tz = timezone(timedelta(hours=8))
        # Find open sessions for this activity and date
        sess_records = supabase.table('sessions').select("id, status") \
            .eq('activity_name', activity).eq('session_date', formatted_date).execute().data
        
        for sess in (sess_records or []):
            if sess.get('status') == 'closed':
                continue   # Skip closed events
            
            # Check if they are already marked in this specific session
            exists = supabase.table('session_attendance').select("id") \
                .eq('session_id', sess['id']).eq('participant_id', pid).execute()
                
            if exists.data:
                supabase.table('session_attendance').update({
                    "status": "checked_in",
                    "marked_at": datetime.now(sgt_tz).isoformat()
                }).eq('id', exists.data[0]['id']).execute()
            else:
                supabase.table('session_attendance').insert({
                    "session_id": sess['id'],
                    "participant_id": pid,
                    "name": name,
                    "status": "checked_in",
                    "marked_at": datetime.now(sgt_tz).isoformat(),
                    "marked_by": role
                }).execute()
    except Exception as e:
        print(f"session_attendance sync skipped: {e}")

def sync_session_attendance_async(pid, name, activity, formatted_date, role="system"):
    """🔥 Fire-and-forget: runs in background thread so the UI never waits."""
    from config import DB_CONNECTED
    if not DB_CONNECTED:
        return
    threading.Thread(
        target=_record_session_attendance,
        args=(pid, name, activity, formatted_date, role),
        daemon=True
    ).start()

def sync_session_attendance_async(pid, name, activity, formatted_date, role="system"):
    """🔥 Fire-and-forget: runs in background thread so the UI never waits."""
    if not DB_CONNECTED:
        return
    threading.Thread(
        target=_record_session_attendance,
        args=(pid, name, activity, formatted_date, role),
        daemon=True
    ).start()


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
    return hashlib.sha256(f"{pid}{date_str}{SUPABASE_KEY[:20]}".encode()).hexdigest()[:16]


def verify_token(pid, date_str, token):
    return token == generate_token(pid, date_str)


def load_participants():
    if not DB_CONNECTED:
        return []

    try:
        return supabase.table('participants').select("*").execute().data
    except:
        return []


def load_plots():
    if not DB_CONNECTED:
        return []

    try:
        return supabase.table('garden_plots').select("*").order('plot_number').execute().data
    except:
        return []


def get_plot(plot_num):
    if not DB_CONNECTED:
        return None

    try:
        r = supabase.table('garden_plots').select("*").eq('plot_number', plot_num).execute()
        return r.data[0] if r.data else None
    except:
        return None


def update_plot(plot_num, updates):
    if not DB_CONNECTED:
        return False

    try:
        updates['updated_at'] = datetime.now().isoformat()
        r = supabase.table('garden_plots').update(updates).eq('plot_number', plot_num).execute()
        return bool(r.data)
    except:
        return False


def get_user_plot(user_id):
    if not user_id or not DB_CONNECTED:
        return None

    try:
        r = supabase.table('garden_plots').select("*").eq('user_id', user_id).eq('occupied', True).execute()
        return r.data[0] if r.data else None
    except:
        return None


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


def get_occupied_count():
    if not DB_CONNECTED:
        return 0

    try:
        return supabase.table('garden_plots').select('*', count="exact").eq('occupied', True).execute().count
    except:
        return 0


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
    """Fetch a participant's full record by their ID."""
    if not DB_CONNECTED or not pid:
        return None

    try:
        res = supabase.table('participants').select("*").eq('id', pid).execute()
        return res.data[0] if res.data else None
    except:
        return None


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


def _parse_time_string(time_str):
    """
    Safely parse time strings from the database.
    Supports:
        - "19:45"
        - "19:45:00"
        - "7:45 PM"
        - "07:45 PM"
    """
    if not time_str:
        return None

    time_str = str(time_str).strip()

    formats = [
        "%H:%M",
        "%H:%M:%S",
        "%I:%M %p",
        "%I:%M:%S %p",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(time_str, fmt).time()
        except ValueError:
            continue

    return None


def validate_checkin_time(activity_name, session_number=1):
    from datetime import datetime, time, timedelta, timezone
    if not DB_CONNECTED:
        return True, "OK"
    try:
        activity = supabase.table('activities').select("*").eq('name', activity_name).single().execute().data
        if not activity:
            return True, "OK"
        if not activity.get('enable_time_validation', False):
            return True, "OK"

        # 🔥 Dynamic: works for session 1, 2, 3 or 4
        try:
            n = int(session_number)
        except Exception:
            n = 1
        start_time_str = activity.get(f'session_{n}_start_time')
        end_time_str = activity.get(f'session_{n}_end_time')
        session_label = activity.get(f'session_{n}_label') or f'Session {n}'

        if not start_time_str or not end_time_str:
            return True, "OK"
        try:
            start_time = datetime.strptime(start_time_str, "%H:%M").time()
            end_time = datetime.strptime(end_time_str, "%H:%M").time()
        except Exception:
            return True, "OK"

        sgt_tz = timezone(timedelta(hours=8))
        now = datetime.now(sgt_tz)
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