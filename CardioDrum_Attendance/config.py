import streamlit as st
from supabase import create_client
from datetime import datetime, timezone
import hashlib
import os
import time

os.environ['TZ'] = 'UTC'

# ============== DATABASE CONFIG ==============
SUPABASE_URL = "https://nqmvsjubgsghjpzojaxm.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5xbXZzanViZ3NnaGpwem9qYXhtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njk1NzQ3ODMsImV4cCI6MjA4NTE1MDc4M30.OukUcFvR1J5-DJVoPGmgjf34dBv7lrB1198YCp_uRIw"

# ============== WAKE-UP FUNCTION ==============
def wake_up_supabase(max_retries=5, retry_delay=5):
    """Attempt to wake up Supabase if it's paused."""
    for attempt in range(max_retries):
        try:
            client = create_client(SUPABASE_URL, SUPABASE_KEY)
            client.table('participants').select("id").limit(1).execute()
            return client, True, "Connected"
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                return None, False, str(e)
    return None, False, "Max retries exceeded"

# ============== DATABASE CONNECTION ==============
@st.cache_resource
def get_db():
    """Initialize database connection with auto wake-up"""
    try:
        if " " in SUPABASE_URL:
            return None, False
        
        client, success, message = wake_up_supabase()
        
        if success:
            st.success("✅ Database connected successfully!", icon="✅")
            time.sleep(1)
            st.empty()
        
        return client, success
    except Exception as e:
        return None, False

# Initialize database
supabase, DB_CONNECTED = get_db()

# ============== HELPER FUNCTIONS ==============
def generate_token(participant_id, date_str):
    secret = SUPABASE_KEY[:20]
    return hashlib.sha256(f"{participant_id}{date_str}{secret}".encode()).hexdigest()[:16]

def verify_token(participant_id, date_str, token):
    return token == generate_token(participant_id, date_str)

def refresh_data():
    """Clear all streamlit caches"""
    st.cache_data.clear()
    st.cache_resource.clear()

# ============== MOBILE CSS ==============
MOBILE_CSS = """
    <style>
    .main { overflow-y: auto !important; height: 100vh !important; }
    .block-container { padding: 1rem 1rem !important; max-width: 100% !important; overflow-y: auto !important; }
    @media (max-width: 768px) {
        .block-container {padding: 0.5rem !important;}
        h1 {font-size: 24px !important;}
        h2 {font-size: 20px !important;}
        .stButton > button { width: 100% !important; font-size: 18px !important; padding: 15px !important; min-height: 50px !important; }
        input, select, textarea {font-size: 16px !important;}
    }
    .stApp { overflow-x: hidden !important; }
    .stAlert { margin-bottom: 10px !important; }
    .pdpa-notice { background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 12px; border-radius: 4px; margin: 10px 0; font-size: 14px; }
    @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
    .waking-up { animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite; }
    </style>
"""

# ============== INITIALIZE STATE ==============
if 'participants' not in st.session_state:
    st.session_state.participants = []

if 'attendance_counts' not in st.session_state:
    st.session_state.attendance_counts = {}

if 'whatsapp_links' not in st.session_state:
    st.session_state.whatsapp_links = []

if 'today_date' not in st.session_state:
    st.session_state.today_date = datetime.now()