import streamlit as st
from supabase import create_client
from datetime import datetime, timezone
import hashlib
import os
os.environ['TZ'] = 'UTC'

# Password Configuration (Hash for security)
ADMIN_PASSWORD_HASH = "wrn6admin"  # "password" hashed
# Change this to your desired password hash using: hashlib.sha256("your_password".encode()).hexdigest()

def verify_password(password):
    """Verify password against hash"""
    import hashlib
    return hashlib.sha256(password.encode()).hexdigest() == ADMIN_PASSWORD_HASH

# Database Config
SUPABASE_URL = "https://nqmvsjubgsghjpzojaxm.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5xbXZzanViZ3NnaGpwem9qYXhtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njk1NzQ3ODMsImV4cCI6MjA4NTE1MDc4M30.OukUcFvR1J5-DJVoPGmgjf34dBv7lrB1198YCp_uRIw"

@st.cache_resource
def get_db():
    try:
        return create_client(SUPABASE_URL, SUPABASE_KEY), True
    except:
        return None, False

supabase, DB_CONNECTED = get_db()

def generate_token(participant_id, date_str):
    secret = SUPABASE_KEY[:20]
    return hashlib.sha256(f"{participant_id}{date_str}{secret}".encode()).hexdigest()[:16]

def verify_token(participant_id, date_str, token):
    return token == generate_token(participant_id, date_str)

def refresh_data():
    """Clear all streamlit caches"""
    st.cache_data.clear()
    st.session_state.attendance_counts = {}

# Initialize state
if 'participants' not in st.session_state:
    if DB_CONNECTED:
        try:
            st.session_state.participants = supabase.table('participants').select("*").execute().data
        except:
            st.session_state.participants = []
    else:
        st.session_state.participants = []

if 'attendance_counts' not in st.session_state:
    st.session_state.attendance_counts = {}

if 'whatsapp_links' not in st.session_state:
    st.session_state.whatsapp_links = []

if 'today_date' not in st.session_state:
    st.session_state.today_date = datetime.now()

# Add this at the end of config.py or in app.py before tabs

MOBILE_CSS = """
<style>
    /* Mobile Responsive Overrides */
    @media (max-width: 768px) {
        /* Reduce padding on mobile */
        .block-container {
            padding: 0.5rem 1rem !important;
        }
        
        /* Smaller headers on phone */
        h1 {
            font-size: 24px !important;
        }
        h2 {
            font-size: 20px !important;
        }
        h3 {
            font-size: 18px !important;
        }
        
        /* Make metrics stack better */
        div[data-testid="stMetricValue"] {
            font-size: 20px !important;
        }
        
        /* Ensure buttons are full width on mobile */
        .stButton > button {
            width: 100% !important;
            font-size: 18px !important;
            padding: 15px !important;
        }
        
        /* Checkbox larger for fingers */
        .stCheckbox {
            font-size: 16px !important;
        }
        
        /* Table scrollable on mobile */
        .stDataFrame {
            overflow-x: auto !important;
        }
        
        /* Reduce gap between elements */
        div[data-testid="stVerticalBlock"] > div {
            gap: 0.5rem !important;
        }
    }
    
    /* Extra small phones */
    @media (max-width: 480px) {
        h1 {
            font-size: 20px !important;
        }
        .stButton > button {
            font-size: 16px !important;
            padding: 12px !important;
        }
    }
    
    /* Touch-friendly inputs */
    input, select, textarea {
        font-size: 16px !important; /* Prevents zoom on iOS */
    }
    
    /* Ensure WhatsApp links don't overflow */
    .stCode pre {
        white-space: pre-wrap !important;
        word-break: break-all !important;
        font-size: 12px !important;
    }
</style>
"""