import streamlit as st
import pandas as pd
from datetime import datetime
from supabase import create_client
import hashlib
import os
from dotenv import load_dotenv
import time

# Load environment variables
load_dotenv()

# ============== AUTHORIZATION CONFIGURATION ==============
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
CHECKER_PASSWORD = os.getenv("CHECKER_PASSWORD", "checker123")

def verify_password(password, role):
    """Verify password based on role"""
    if role == "admin":
        return password == ADMIN_PASSWORD
    elif role == "checker":
        return password == CHECKER_PASSWORD
    return False

# ============== CONFIGURATION ==============
st.set_page_config(
    page_title="Cardio Drumming Attendance",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ============== IMPORT CONFIG ==============
from config import supabase, DB_CONNECTED, MOBILE_CSS, refresh_data

# Apply CSS (hidden from display)
st.markdown(MOBILE_CSS, unsafe_allow_html=True)

# ============== AUTHENTICATION STATE INITIALIZATION ==============
if 'is_authenticated' not in st.session_state:
    st.session_state.is_authenticated = False
if 'user_role' not in st.session_state:
    st.session_state.user_role = None
if 'show_login' not in st.session_state:
    st.session_state.show_login = False

# ============== LOAD DATA (Only if connected) ==============
if DB_CONNECTED and supabase is not None:
    if 'participants' not in st.session_state or len(st.session_state.participants) == 0:
        try:
            st.session_state.participants = supabase.table('participants').select("*").execute().data
        except Exception as e:
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
        
        if not DB_CONNECTED or supabase is None:
            st.error("❌ Database not connected. Please try again later.")
            st.stop()
        
        pid = params.get("pid")
        date_str = params.get("date", datetime.now().strftime("%Y%m%d"))
        token = params.get("tk")
        
        from config import verify_token
        if not verify_token(pid, date_str, token):
            st.error("❌ Invalid or expired link. Please contact administrator.")
            st.stop()
        
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
        
        st.markdown(f"""
            <h1 style='text-align: center; color: #0066CC; margin-bottom: 10px;'>
                Hello {participant['name']}!
            </h1>
        """, unsafe_allow_html=True)
        
        st.subheader(f"📅 {datetime.strptime(date_str, '%Y%m%d').strftime('%d %B %Y')}")
        
        st.divider()
        st.markdown("### 👇 Tap to select session(s):")
        
        col1, col2 = st.columns(2)
        with col1:
            s1 = st.checkbox("## Session 1\n### 7:00 PM - 8:00 PM\n\nTap here ✓", key="s1_mobile")
        with col2:
            s2 = st.checkbox("## Session 2\n### 8:00 PM - 9:00 PM\n\nTap here ✓", key="s2_mobile")
        
        st.write(" ")
        
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
        st.stop()
except Exception as e:
    pass

# ============== MAIN ADMIN APP ==============
st.title("🥁 Woodlands Zone 6 - Cardio Drumming")

# ============== PDPA COMPLIANCE NOTICE ==============
st.markdown("""
    <div class="pdpa-notice">
        🔒 <strong>PDPA Compliant:</strong> Phone numbers displayed with last 4 digits only for privacy protection.
    </div>
""", unsafe_allow_html=True)

# ============== CONNECTION STATUS WARNING ==============
if not DB_CONNECTED or supabase is None:
    st.error("❌ **Database Not Connected** - Please check your internet connection or wait for Supabase to wake up. Refresh the page to retry.")
    st.stop()

# ============== ACCESS LEVEL INDICATOR ==============
if st.session_state.is_authenticated:
    role_badge = "👑 Admin" if st.session_state.user_role == "admin" else "👤 Attendance Checker"
    st.success(f"{role_badge} - Full Access" if st.session_state.user_role == "admin" else f"{role_badge} - Attendance Only", icon="✅")
else:
    st.info("🔐 Please login to access the system", icon="ℹ️")

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
            st.session_state.user_role = None
            st.rerun()
    else:
        if st.button("🔐 Login", use_container_width=True):
            st.session_state.show_login = True

# ============== LOGIN MODAL ==============
if not st.session_state.is_authenticated and st.session_state.show_login:
    st.divider()
    st.subheader("🔐 User Login")
    col_a, col_b = st.columns([2, 1])
    
    with col_a:
        password_input = st.text_input(
            "Enter Password", 
            type="password", 
            key="user_password_input",
            placeholder="Type password..."
        )
        st.caption("• Checker: Attendance marking only\n• Admin: Full system access")
    
    with col_b:
        st.write(" ")
        st.write(" ")
        if st.button("✓ Login", type="primary", use_container_width=True):
            if verify_password(password_input, "admin"):
                st.session_state.is_authenticated = True
                st.session_state.user_role = "admin"
                st.session_state.show_login = False
                st.success("✅ Admin login successful!")
                st.rerun()
            elif verify_password(password_input, "checker"):
                st.session_state.is_authenticated = True
                st.session_state.user_role = "checker"
                st.session_state.show_login = False
                st.success("✅ Attendance Checker login successful!")
                st.rerun()
            else:
                st.error("❌ Invalid password")
        
        if st.button("Cancel", use_container_width=True):
            st.session_state.show_login = False
            st.rerun()

# ============== SIDEBAR ==============
with st.sidebar:
    st.title("⚡ Quick Actions")
    if st.button("🔄 Refresh Data", use_container_width=True):
        refresh_data()
        if DB_CONNECTED and supabase is not None:
            try:
                st.session_state.participants = supabase.table('participants').select("*").execute().data
                st.success("✅ Data refreshed!")
            except Exception as e:
                st.error(f"⚠️ Refresh failed: {e}")
        st.rerun()
    
    selected_date = st.date_input("📅 Session Date", value=st.session_state.today_date)
    
    st.divider()
    st.markdown("**⏰ Session Times**")
    st.markdown("1st: 7:00 PM - 8:00 PM")
    st.markdown("2nd: 8:00 PM - 9:00 PM")
    
    active_count = len([p for p in st.session_state.participants if p.get('active', True)])
    st.metric("Active Members", active_count)

# ============== TAB IMPORTS ==============
with st.spinner("Loading..."):
    try:
        import sys
        from pathlib import Path
        sys.path.append(str(Path(__file__).parent))
        
        from tab1_checkin import show_tab1
        from tab2_whatsapp import show_tab2
        from tab3_reports import show_tab3
        from tab4_manage import show_tab4
        from tab5_import import show_tab5
        
        if st.session_state.is_authenticated:
            if st.session_state.user_role == "admin":
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
                
            elif st.session_state.user_role == "checker":
                tab_names = ["📝 Check-In", "📊 Reports"]
                tab1, tab3 = st.tabs(tab_names)
                
                with tab1:
                    show_tab1(selected_date)
                with tab3:
                    show_tab3(selected_date)
        else:
            st.info("🔐 Please login to access attendance features")
            
    except ImportError as e:
        st.error(f"Error loading modules: {e}")
        st.info("Please ensure all tab files are in the same folder")

st.divider()
st.caption("Woodlands Zone 6 - Cardio Drumming System | PDPA Compliant | Optimized for Mobile")