import streamlit as st
from config import supabase, DB_CONNECTED, SUPABASE_KEY
from datetime import datetime, timedelta
import hashlib

def mask_phone(phone):
    if not phone: return "N/A"
    p = str(phone).strip().replace(" ", "").replace("-", "")
    if len(p) >= 8: return "••••" + p[-4:]
    return p

def get_attendance_count(pid):
    if not DB_CONNECTED: return 0
    try:
        return supabase.table('attendance').select('*', count='exact').eq('participant_id', pid).execute().count
    except: return 0

def check_and_convert_status(pid, name):
    if not DB_CONNECTED: return None
    try:
        c = get_attendance_count(pid)
        if c >= 3:
            p = supabase.table('participants').select('is_new').eq('id', pid).execute()
            if p.data and p.data[0].get('is_new'):
                supabase.table('participants').update({'is_new': False}).eq('id', pid).execute()
                return f"🎉 {name} graduated to Regular!"
        return None
    except: return None

def generate_token(pid, date_str):
    return hashlib.sha256(f"{pid}{date_str}{SUPABASE_KEY[:20]}".encode()).hexdigest()[:16]

def verify_token(pid, date_str, token):
    return token == generate_token(pid, date_str)

def load_participants():
    if not DB_CONNECTED: return []
    try:
        return supabase.table('participants').select("*").execute().data
    except: return []

def load_plots():
    if not DB_CONNECTED: return []
    try:
        return supabase.table('garden_plots').select("*").order('plot_number').execute().data
    except: return []

def get_plot(plot_num):
    if not DB_CONNECTED: return None
    try:
        r = supabase.table('garden_plots').select("*").eq('plot_number', plot_num).execute()
        return r.data[0] if r.data else None
    except: return None

def update_plot(plot_num, updates):
    if not DB_CONNECTED: return False
    try:
        updates['updated_at'] = datetime.now().isoformat()
        r = supabase.table('garden_plots').update(updates).eq('plot_number', plot_num).execute()
        return bool(r.data)
    except: return False

def get_user_plot(user_id):
    if not user_id or not DB_CONNECTED: return None
    try:
        # Now user_id is the Participant ID, exactly as stored
        r = supabase.table('garden_plots').select("*").eq('user_id', user_id).eq('occupied', True).execute()
        return r.data[0] if r.data else None
    except: return None

def create_request(plot_num, user_id, user_name, contact, notes=""):
    if not DB_CONNECTED: return None
    try:
        r = supabase.table('plot_requests').insert({
            "plot_number": plot_num, "user_id": user_id, "user_name": user_name,
            "contact": contact, "notes": notes, "status": "pending"
        }).execute()
        return r.data[0] if r.data else None
    except: return None

def get_pending_requests():
    if not DB_CONNECTED: return []
    try:
        return supabase.table('plot_requests').select("*").eq('status', 'pending').order('created_at').execute().data
    except: return []

def update_request_status(rid, status):
    if not DB_CONNECTED: return False
    try:
        r = supabase.table('plot_requests').update({"status": status}).eq('id', rid).execute()
        return bool(r.data)
    except: return False

def get_occupied_count():
    if not DB_CONNECTED: return 0
    try:
        return supabase.table('garden_plots').select('*', count="exact").eq('occupied', True).execute().count
    except: return 0

def clean_phone_number(phone):
    if not phone: return ""
    p = str(phone).strip().replace(" ", "").replace("-", "").replace("+", "")
    if p.startswith("65") and len(p) == 10:
        p = p[2:]
    return p

def find_participant_by_phone(phone):
    if not DB_CONNECTED: return None
    clean = clean_phone_number(phone)
    if len(clean) < 4: return None
    
    try:
        res = supabase.table('participants').select("*").eq('contact', clean).execute()
        if res.data: return res.data[0]
        
        res2 = supabase.table('participants').select("*").ilike('contact', f'%{clean[-4:]}%').execute()
        for p in res2.data:
            if clean_phone_number(p.get('contact', '')) == clean:
                return p
    except:
        pass
    return None

# NEW HELPER FUNCTION FOR THE MERGE
def find_participant_by_id(pid):
    """Fetch a participant's full record by their ID."""
    if not DB_CONNECTED or not pid: return None
    try:
        res = supabase.table('participants').select("*").eq('id', pid).execute()
        return res.data[0] if res.data else None
    except:
        return None

def check_returning_guest(phone):
    if not DB_CONNECTED: return None
    clean = clean_phone_number(phone)
    if len(clean) < 4: return None
    
    try:
        res = supabase.table('session_rsvp').select("created_at, name").eq('phone', clean).order('created_at', desc=True).limit(1).execute()
        if res.data: 
            return res.data[0] 
    except:
        pass
    return None

def log_action(role, action, details="", target_id=""):
    if not DB_CONNECTED: return
    try:
        supabase.table('audit_logs').insert({
            "user_role": role,
            "action": action,
            "details": details,
            "target_id": target_id
        }).execute()
    except Exception as e:
        print(f"Audit log error: {e}")

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
        
        if session_number == 1 or session_number == "Session 1":
            start_time_str = activity.get('session_1_start_time')
            end_time_str = activity.get('session_1_end_time')
            session_label = activity.get('session_1_label', 'Session 1')
        else:
            start_time_str = activity.get('session_2_start_time')
            end_time_str = activity.get('session_2_end_time')
            session_label = activity.get('session_2_label', 'Session 2')
        
        if not start_time_str or not end_time_str:
            return True, "OK"
        
        try:
            start_time = datetime.strptime(start_time_str, "%H:%M").time()
            end_time = datetime.strptime(end_time_str, "%H:%M").time()
        except:
            return True, "OK"
        
        sgt_tz = timezone(timedelta(hours=8))
        now = datetime.now(sgt_tz)
        current_time = now.time()
        
        if current_time < start_time:
            return False, f"Check-in for {session_label} opens at {start_time.strftime('%I:%M %p')}. Please return at that time."
        elif current_time > end_time:
            return False, f"Check-in for {session_label} closed at {end_time.strftime('%I:%M %p')}. The session has started."
        else:
            return True, "OK"
            
    except Exception as e:
        print(f"Time validation error: {e}")
        return True, "OK" 