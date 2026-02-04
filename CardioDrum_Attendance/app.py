import streamlit as st
import pandas as pd
from datetime import datetime
from supabase import create_client
import hashlib
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ============== ADMIN PASSWORD CONFIGURATION ==============
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "wrn6admin")

def verify_admin_password(password):
    """Verify admin password"""
    return password == ADMIN_PASSWORD

# ============== CONFIGURATION ==============
st.set_page_config(
    page_title="Cardio Drumming Attendance", 
    layout="wide", 
    initial_sidebar_state="collapsed"
)

SUPABASE_URL = "https://nqmvsjubgsghjpzojaxm.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5xbXZzanViZ3NnaGpwem9qYXhtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njk1NzQ3ODMsImV4cCI6MjA4NTE1MDc4M30.OukUcFvR1J5-DJVoPGmgjf34dBv7lrB1198YCp_uRIw"

# ============== MOBILE RESPONSIVE CSS ==============
MOBILE_CSS = """
<style>
    /* Enable scrolling */
    .main {
        overflow-y: auto !important;
        height: 100vh !important;
    }
    
    .block-container {
        padding: 1rem 1rem !important;
        max-width: 100% !important;
        overflow-y: auto !important;
    }
    
    /* Mobile Responsive */
    @media (max-width: 768px) {
        .block-container {padding: 0.5rem !important;}
        h1 {font-size: 24px !important;}
        h2 {font-size: 20px !important;}
        .stButton > button {
            width: 100% !important;
            font-size: 18px !important;
            padding: 15px !important;
            min-height: 50px !important;
        }
        input, select, textarea {font-size: 16px !important;}
    }
    
    /* Prevent horizontal scroll */
    .stApp {
        overflow-x: hidden !important;
    }
    
    /* Login modal styling */
    .stAlert {
        margin-bottom: 10px !important;
    }
</style>
"""

st.markdown(MOBILE_CSS, unsafe_allow_html=True)

# ============== DATABASE & HELPERS ==============
@st.cache_resource
def get_db():
    try:
        return create_client(SUPABASE_URL, SUPABASE_KEY), True
    except Exception as e:
        st.error(f"DB Error: {e}")
        return None, False

supabase, DB_CONNECTED = get_db()

def generate_token(participant_id, date_str):
    secret = SUPABASE_KEY[:20]
    return hashlib.sha256(f"{participant_id}{date_str}{secret}".encode()).hexdigest()[:16]

def verify_token(participant_id, date_str, token):
    return token == generate_token(participant_id, date_str)

def refresh_data():
    st.cache_data.clear()

# ============== AUTHENTICATION STATE INITIALIZATION ==============
if 'is_authenticated' not in st.session_state:
    st.session_state.is_authenticated = False

if 'show_login' not in st.session_state:
    st.session_state.show_login = False

# ============== STATE INITIALIZATION ==============
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

# ============== SELF CHECK-IN MODE (ELDERLY VIEW) ==============
is_self_checkin = False

try:
    params = st.query_params
    if params.get("mode") == "checkin":
        is_self_checkin = True
        pid = params.get("pid")
        date_str = params.get("date", datetime.now().strftime("%Y%m%d"))
        token = params.get("tk")
        
        if not verify_token(pid, date_str, token):
            st.error("❌ Invalid or expired link. Please contact administrator.")
            st.stop()
        
        if not DB_CONNECTED:
            st.error("❌ Database not connected")
            st.stop()
        
        # Load participant directly from DB (not session state)
        try:
            result = supabase.table('participants').select("*").eq('id', pid).execute()
            if not result.data:
                st.error("❌ Participant not found")
                st.stop()
            participant = result.data[0]
        except Exception as e:
            st.error(f"❌ Error loading data: {e}")
            st.stop()
        
        # ============== MOBILE-FRIENDLY CHECK-IN UI ==============
        st.title("🥁 Cardio Drumming")
        
        # Large header for elderly
        st.markdown(f"""
        <h1 style='text-align: center; color: #0066CC; margin-bottom: 10px;'>
            Hello {participant['name']}!
        </h1>
        """, unsafe_allow_html=True)
        
        st.subheader(f"📅 {datetime.strptime(date_str, '%Y%m%d').strftime('%d %B %Y')}")
        
        st.divider()
        st.markdown("### 👇 Tap to select session(s):")
        
        # Large touch targets for mobile
        col1, col2 = st.columns(2)
        with col1:
            s1 = st.checkbox("## Session 1\n### 7:00 PM - 8:00 PM\n\nTap here ✓", key="s1_mobile")
        with col2:
            s2 = st.checkbox("## Session 2\n### 8:00 PM - 9:00 PM\n\nTap here ✓", key="s2_mobile")
        
        st.write("")  # Spacer
        
        # Large confirm button
        if st.button("✅ CONFIRM MY ATTENDANCE", type="primary", use_container_width=True):
            if not s1 and not s2:
                st.warning("⚠️ Please tap at least one session above")
            else:
                try:
                    record = {
                        "participant_id": pid,
                        "name": participant['name'],
                        "date": datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d"),
                        "session_1": s1,
                        "session_2": s2,
                        "timestamp": datetime.now().isoformat(),
                        "self_checkin": True
                    }
                    supabase.table('attendance').insert(record).execute()
                    
                    st.balloons()
                    st.success("## ✅ Thank You!", icon="🎉")
                    st.info("Your attendance is confirmed!", icon="✅")
                    
                    # Show what they selected
                    if s1 and s2:
                        st.markdown("**You selected: Both Sessions**")
                    elif s1:
                        st.markdown("**You selected: Session 1**")
                    else:
                        st.markdown("**You selected: Session 2**")
                    
                    st.caption("See you at Woodlands Zone 6!")
                    
                except Exception as e:
                    st.error("❌ Error saving. Please contact admin.")
        
        st.divider()
        st.caption("📍 Block 622 Woodlands Drive 52 #01-22")
        st.caption("Having trouble? Contact: [Admin]")
        st.stop()  # CRITICAL: Stop here so admin UI doesn't show
        
except Exception as e:
    # Not in self-checkin mode, continue to admin app
    pass

# ============== MAIN ADMIN APP ==============
st.title("🥁 Woodlands Zone 6 - Cardio Drumming")

# ============== ACCESS LEVEL INDICATOR ==============
if st.session_state.is_authenticated:
    st.success("👑 Admin Access - Full Permissions", icon="✅")
else:
    st.info("👤 Normal User - Limited Access (Check-In & Reports only)", icon="ℹ️")

# ============== LOGIN/LOGOUT CONTROLS ==============
col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    st.subheader("Admin Dashboard")

with col2:
    st.caption(f"📅 {datetime.now().strftime('%d %b %Y')}")

with col3:
    if st.session_state.is_authenticated:
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.is_authenticated = False
            st.rerun()
    else:
        if st.button("🔐 Login", use_container_width=True):
            st.session_state.show_login = True

# ============== LOGIN MODAL ==============
if not st.session_state.is_authenticated and st.session_state.show_login:
    st.divider()
    st.subheader("🔐 Admin Login")
    
    col_a, col_b = st.columns([2, 1])
    
    with col_a:
        password_input = st.text_input(
            "Enter Admin Password", 
            type="password", 
            key="admin_password_input",
            placeholder="Type password..."
        )
    
    with col_b:
        st.write("")  # Spacer
        st.write("")
        if st.button("✓ Submit", type="primary", use_container_width=True):
            if verify_admin_password(password_input):
                st.session_state.is_authenticated = True
                st.session_state.show_login = False
                st.success("✅ Login successful!")
                st.rerun()
            else:
                st.error("❌ Invalid password")
        
        if st.button("Cancel", use_container_width=True):
            st.session_state.show_login = False
            st.rerun()

# ============== SIDEBAR (collapsible on mobile) ==============
with st.sidebar:
    st.title("⚡ Quick Actions")
    
    if st.button("🔄 Refresh Data", use_container_width=True):
        refresh_data()
        # Reload from DB
        if DB_CONNECTED:
            st.session_state.participants = supabase.table('participants').select("*").execute().data
        st.rerun()
    
    selected_date = st.date_input("📅 Session Date", value=st.session_state.today_date)
    
    st.divider()
    st.markdown("**⏰ Session Times**")
    st.markdown("1st: 7:00 PM - 8:00 PM")
    st.markdown("2nd: 8:00 PM - 9:00 PM")
    
    # Mobile stats
    active_count = len([p for p in st.session_state.participants if p.get('active', True)])
    st.metric("Active Members", active_count)

# ============== TAB IMPORTS (Lazy loading for speed) ==============
with st.spinner("Loading..."):
    try:
        # Import here to speed up initial load on mobile
        import sys
        from pathlib import Path
        
        # Add current directory to path
        sys.path.append(str(Path(__file__).parent))
        
        from tab1_checkin import show_tab1
        from tab2_whatsapp import show_tab2
        from tab3_reports import show_tab3
        from tab4_manage import show_tab4
        from tab5_import import show_tab5
        
        # ============== CONDITIONAL TAB DISPLAY ==============
        if st.session_state.is_authenticated:
            # Admin sees ALL tabs
            tab_names = ["📝 Check-In", "📱 WhatsApp", "📊 Reports", "⚙️ Manage", "📥 Import"]
            tab1, tab2, tab3, tab4, tab5 = st.tabs(tab_names)
            
            with tab1:
                show_tab1(selected_date)
            
            with tab2:
                show_tab2(selected_date)
            
            with tab3:
                show_tab3(selected_date)
            
            with tab4:
                show_tab4(selected_date)
            
            with tab5:
                show_tab5(selected_date)
                
        else:
            # Normal user sees ONLY Check-In and Reports
            tab_names = ["📝 Check-In", "📊 Reports"]
            tab1, tab3 = st.tabs(tab_names)
            
            with tab1:
                show_tab1(selected_date)
            
            with tab3:
                show_tab3(selected_date)
            
    except ImportError as e:
        st.error(f"Error loading modules: {e}")
        st.info("Please ensure all tab files (tab1_checkin.py, tab2_whatsapp.py, etc.) are in the same folder")

st.divider()
st.caption("Woodlands Zone 6 - Cardio Drumming System | Optimized for Mobile")