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
