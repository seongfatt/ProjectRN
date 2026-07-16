import streamlit as st
from config import supabase, DB_CONNECTED, SUPABASE_KEY
from datetime import datetime
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
        msg = None
        if c >= 3:
            p = supabase.table('participants').select('is_new').eq('id', pid).execute()
            if p.data and p.data[0].get('is_new'):
                supabase.table('participants').update({'is_new': False}).eq('id', pid).execute()
                msg = f"🎉 {name} graduated to Regular!"
        
        #  PHASE 3: Update their streak!
        update_attendance_streak(pid)
        
        return msg
    except: return None

def generate_token(pid, date_str):
    return hashlib.sha256(f"{pid}{date_str}{SUPABASE_KEY[:20]}".encode()).hexdigest()[:16]

def verify_token(pid, date_str, token):
    return token == generate_token(pid, date_str)

@st.cache_data(ttl=300)  # 🚀 CACHING: Saves data in memory for 5 minutes (300 seconds)
def load_participants():
    if not DB_CONNECTED: return []
    try:
        return supabase.table('participants').select("*").execute().data
    except: return []

@st.cache_data(ttl=300)  # 🚀 CACHING: Saves data in memory for 5 minutes (300 seconds)
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
        r = supabase.table('garden_plots').select("*").eq('user_id', user_id.lower().strip()).eq('occupied', True).execute()
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

def update_attendance_streak(pid):
    """Calculates and updates the resident's attendance streak."""
    if not DB_CONNECTED: return
    
    try:
        # Get current streak data
        p = supabase.table('participants').select('streak_weeks', 'longest_streak', 'last_attendance_date').eq('id', pid).execute()
        if not p.data: return
        
        data = p.data[0]
        last_date_str = data.get('last_attendance_date')
        current_streak = data.get('streak_weeks', 0)
        longest = data.get('longest_streak', 0)
        
        today = datetime.now().date()
        
        # If no previous date, start streak at 1
        if not last_date_str:
            new_streak = 1
        else:
            last_date = datetime.strptime(last_date_str, "%Y-%m-%d").date()
            days_diff = (today - last_date).days
            
            # If checked in within 10 days (allows for 1 week + grace period), increment streak
            if 1 <= days_diff <= 10:
                new_streak = current_streak + 1
            # If checked in on the same day, keep streak same
            elif days_diff == 0:
                new_streak = current_streak
            # If missed more than 10 days, reset streak
            else:
                new_streak = 1
        
        # Update longest streak if current is higher
        if new_streak > longest:
            longest = new_streak
            
        # Save to database
        supabase.table('participants').update({
            'streak_weeks': new_streak,
            'longest_streak': longest,
            'last_attendance_date': str(today)
        }).eq('id', pid).execute()
        
    except Exception as e:
        print(f"Streak update error: {e}")

def log_action(role, action, details="", target_id=""):
    """Records critical admin actions for accountability and security."""
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

def clean_phone_number(phone):
    """Standardizes phone numbers for database matching."""
    if not phone: return ""
    p = str(phone).strip().replace(" ", "").replace("-", "").replace("+", "")
    if p.startswith("65") and len(p) == 10:
        p = p[2:] # Remove country code for local matching
    return p

def find_participant_by_phone(phone):
    """Searches the participants database for an exact phone match."""
    if not DB_CONNECTED: return None
    clean = clean_phone_number(phone)
    if len(clean) < 4: return None
    
    try:
        # Try exact match first
        res = supabase.table('participants').select("*").eq('contact', clean).execute()
        if res.data: return res.data[0]
        
        # Fallback: match by last 4 digits if they typed it partially
        res2 = supabase.table('participants').select("*").ilike('contact', f'%{clean[-4:]}%').execute()
        for p in res2.data:
            if clean_phone_number(p.get('contact', '')) == clean:
                return p
    except:
        pass
    return None

def check_returning_guest(phone):
    """Checks if this phone number was used as a walk-in previously."""
    if not DB_CONNECTED: return None
    clean = clean_phone_number(phone)
    if len(clean) < 4: return None
    
    try:
        # Check session_rsvp for past walk-ins with this phone
        res = supabase.table('session_rsvp').select("created_at, name").eq('phone', clean).order('created_at', desc=True).limit(1).execute()
        if res.data: 
            return res.data[0] 
    except:
        pass
    return None

def clean_phone_number(phone):
    """Standardizes phone numbers for database matching."""
    if not phone: return ""
    p = str(phone).strip().replace(" ", "").replace("-", "").replace("+", "")
    if p.startswith("65") and len(p) == 10:
        p = p[2:] # Remove country code for local matching
    return p

def find_participant_by_phone(phone):
    """Searches the participants database for an exact phone match."""
    if not DB_CONNECTED: return None
    clean = clean_phone_number(phone)
    if len(clean) < 4: return None
    
    try:
        # Try exact match first
        res = supabase.table('participants').select("*").eq('contact', clean).execute()
        if res.data: return res.data[0]
        
        # Fallback: match by last 4 digits if they typed it partially
        res2 = supabase.table('participants').select("*").ilike('contact', f'%{clean[-4:]}%').execute()
        for p in res2.data:
            if clean_phone_number(p.get('contact', '')) == clean:
                return p
    except:
        pass
    return None

def check_returning_guest(phone):
    """Checks if this phone number was used as a walk-in previously."""
    if not DB_CONNECTED: return None
    clean = clean_phone_number(phone)
    if len(clean) < 4: return None
    
    try:
        # Check session_rsvp for past walk-ins with this phone
        res = supabase.table('session_rsvp').select("created_at, name").eq('phone', clean).order('created_at', desc=True).limit(1).execute()
        if res.data: 
            return res.data[0] 
    except:
        pass
    return None
