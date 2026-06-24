import streamlit as st
import pandas as pd
from datetime import datetime
import urllib.parse
from config import (supabase, DB_CONNECTED, MOBILE_CSS, ADMIN_PASSWORD, 
    CHECKER_PASSWORD, APP_URL, load_activities, PLOT_TYPES, TOTAL_PLOTS, TYPE_MAP, refresh_data)
from utils import (mask_phone, get_attendance_count, check_and_convert_status, 
    generate_token, verify_token, load_participants, load_plots, get_plot, 
    update_plot, get_user_plot, create_request, get_pending_requests, 
    update_request_status, get_occupied_count)

st.set_page_config(page_title="Woodlands Zone 6 - Community Hub", layout="wide", initial_sidebar_state="collapsed")
st.markdown(MOBILE_CSS, unsafe_allow_html=True)

for k in ['is_authenticated','user_role','show_login','participants','plots','activities','today_date','selected_plot','selected_activity','auto_checkin_done']:
    if k not in st.session_state:
        st.session_state[k] = None if k in ['user_role','selected_plot','selected_activity'] else (False if k in ['is_authenticated','auto_checkin_done'] else ([] if k in ['participants','plots','activities'] else datetime.now().date()))

def verify_password(pwd, role):
    if role == "admin": return pwd == ADMIN_PASSWORD
    elif role == "checker": return pwd == CHECKER_PASSWORD
    return False

# ===== AUTO CHECK-IN MODE (QR / Link) =====
# URL format: ?mode=auto&pid=ID&date=YYYYMMDD&tk=TOKEN&act=ACTIVITY&session=1 (or 2, or both)
params = st.query_params
if params.get("mode") == "auto":
    if not DB_CONNECTED or supabase is None:
        st.error("Database not connected."); st.stop()

    pid = params.get("pid")
    date_str = params.get("date", datetime.now().strftime("%Y%m%d"))
    token = params.get("tk")
    act = params.get("act", "Cardio Drumming")
    session_param = params.get("session", "both")  # 1, 2, or both

    if not verify_token(pid, date_str, token):
        st.error("Invalid or expired link."); st.stop()

    try:
        p = supabase.table('participants').select("*").eq('id', pid).execute().data[0]
    except:
        st.error("Participant not found"); st.stop()

    # Check if already checked in today for this activity
    try:
        existing = supabase.table('attendance').select("*")\
            .eq('participant_id', pid)\
            .eq('date', datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d"))\
            .eq('source', act)\
            .execute()

        if existing.data:
            # Already checked in - show status
            record = existing.data[0]
            s1_done = record.get('session_1', False)
            s2_done = record.get('session_2', False)

            st.title(f"{act}")
            st.success(f"Hello {p['name']}!")
            st.info(f"You already checked in for {datetime.strptime(date_str, '%Y%m%d').strftime('%d %B %Y')}")

            if s1_done and s2_done:
                st.balloons()
                st.success("Both sessions recorded! See you there!")
            elif s1_done:
                st.write("Session 1: Confirmed")
                if session_param in ['2', 'both'] and not s2_done:
                    # Auto-add session 2
                    supabase.table('attendance').update({"session_2": True}).eq('id', record['id']).execute()
                    st.balloons()
                    st.success("Session 2 added! Both sessions confirmed!")
            elif s2_done:
                st.write("Session 2: Confirmed")
                if session_param in ['1', 'both'] and not s1_done:
                    supabase.table('attendance').update({"session_1": True}).eq('id', record['id']).execute()
                    st.balloons()
                    st.success("Session 1 added! Both sessions confirmed!")
            st.stop()
    except Exception as e:
        pass  # No existing record, continue to auto-register

    # AUTO REGISTER - No user interaction needed!
    if not st.session_state.auto_checkin_done:
        try:
            s1 = session_param in ['1', 'both']
            s2 = session_param in ['2', 'both']

            supabase.table('attendance').insert({
                "participant_id": pid, "name": p['name'], 
                "date": datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d"),
                "session_1": s1, "session_2": s2, 
                "timestamp": datetime.now().isoformat(),
                "self_checkin": True, "source": act
            }).execute()

            st.session_state.auto_checkin_done = True

            # Auto-convert New to Regular if needed
            msg = check_and_convert_status(pid, p['name'])

        except Exception as e:
            st.error(f"Error saving: {e}")
            st.stop()

    # Show success page
    st.title(f"{act}")
    st.balloons()
    st.success(f"Welcome {p['name']}!")
    st.info(f"Attendance confirmed for {datetime.strptime(date_str, '%Y%m%d').strftime('%d %B %Y')}")

    if session_param == 'both':
        st.markdown("### Both sessions auto-registered!")
    elif session_param == '1':
        st.markdown("### Session 1 confirmed!")
    elif session_param == '2':
        st.markdown("### Session 2 confirmed!")

    st.caption("Thank you for joining! See you at Woodlands Zone 6!")
    st.stop()

# ===== LEGACY CHECK-IN MODE (with checkbox - keep for backward compatibility) =====
if params.get("mode") == "checkin":
    if not DB_CONNECTED or supabase is None:
        st.error("Database not connected."); st.stop()
    pid = params.get("pid")
    date_str = params.get("date", datetime.now().strftime("%Y%m%d"))
    token = params.get("tk")
    act = params.get("act", "Cardio Drumming")
    if not verify_token(pid, date_str, token):
        st.error("Invalid or expired link."); st.stop()
    try:
        p = supabase.table('participants').select("*").eq('id', pid).execute().data[0]
    except:
        st.error("Participant not found"); st.stop()

    st.title(f"{act}")
    st.markdown(f"<h2 style='text-align:center;color:#0066CC;'>Hello {p['name']}!</h2>", unsafe_allow_html=True)
    st.subheader(f"{datetime.strptime(date_str, '%Y%m%d').strftime('%d %B %Y')}")
    st.divider()

    acts = load_activities()
    act_data = next((a for a in acts if a['name'] == act), None)
    s1_label = act_data['session_1_label'] if act_data else "Session 1"
    s2_label = act_data['session_2_label'] if act_data else "Session 2"

    s1 = st.checkbox(f"{s1_label}", key="s1_mobile")
    s2 = st.checkbox(f"{s2_label}", key="s2_mobile")

    if st.button("CONFIRM MY ATTENDANCE", type="primary", use_container_width=True):
        if not s1 and not s2:
            st.warning("Please select at least one session")
        else:
            try:
                supabase.table('attendance').insert({
                    "participant_id": pid, "name": p['name'], "date": datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d"),
                    "session_1": s1, "session_2": s2, "timestamp": datetime.now().isoformat(),
                    "self_checkin": True, "source": act
                }).execute()
                st.balloons()
                st.success("Thank You!"); st.info("Attendance confirmed!")
            except:
                st.error("Error saving. Contact admin.")
    st.stop()

# ===== MAIN APP =====
st.title("Woodlands Zone 6 - Community Hub")
st.markdown("<div class='pdpa-notice'><strong>PDPA Compliant:</strong> Phone numbers masked for privacy</div>", unsafe_allow_html=True)

if not DB_CONNECTED or supabase is None:
    st.error("Database Not Connected"); st.stop()

# Load data
if not st.session_state.participants:
    st.session_state.participants = load_participants()
if not st.session_state.plots:
    st.session_state.plots = load_plots()
if not st.session_state.activities:
    st.session_state.activities = load_activities()

# Auth UI
col1, col2, col3 = st.columns([2,1,1])
with col1: st.subheader("Admin Dashboard")
with col2: st.caption(f"{datetime.now().strftime('%d %b %Y')}")
with col3:
    if st.session_state.is_authenticated:
        if st.button("Logout", use_container_width=True):
            st.session_state.is_authenticated = False; st.session_state.user_role = None; st.rerun()
    else:
        if st.button("Login", use_container_width=True):
            st.session_state.show_login = True

if not st.session_state.is_authenticated and st.session_state.show_login:
    st.divider(); st.subheader("Login")
    c1, c2 = st.columns([2,1])
    with c1:
        pwd = st.text_input("Password", type="password", key="login_pwd")
        st.caption("Checker: Attendance only | Admin: Full access")
    with c2:
        st.write(" "); st.write(" ")
        if st.button("Login", type="primary", use_container_width=True):
            if verify_password(pwd, "admin"):
                st.session_state.is_authenticated = True; st.session_state.user_role = "admin"; st.session_state.show_login = False; st.rerun()
            elif verify_password(pwd, "checker"):
                st.session_state.is_authenticated = True; st.session_state.user_role = "checker"; st.session_state.show_login = False; st.rerun()
            else: st.error("Invalid password")
        if st.button("Cancel", use_container_width=True):
            st.session_state.show_login = False; st.rerun()

if st.session_state.is_authenticated:
    role_badge = "Admin" if st.session_state.user_role == "admin" else "Checker"
    st.success(f"{role_badge} - {'Full Access' if st.session_state.user_role=='admin' else 'Attendance Only'}")
else:
    st.info("Please login to access admin features")

# Sidebar
with st.sidebar:
    st.title("Quick Actions")
    if st.button("Refresh Data", use_container_width=True):
        refresh_data(); st.session_state.participants = load_participants()
        st.session_state.plots = load_plots(); st.session_state.activities = load_activities()
        st.success("Refreshed!"); st.rerun()

    selected_date = st.date_input("Session Date", value=st.session_state.today_date)

    if st.session_state.activities:
        act_names = [a['name'] for a in st.session_state.activities]
        selected_act = st.selectbox("Activity", act_names, index=0)
        st.session_state.selected_activity = selected_act
    else:
        st.session_state.selected_activity = "Cardio Drumming"

    st.divider()
    st.markdown("**Session Times**")
    st.markdown("1st: 7:00 PM - 8:00 PM")
    st.markdown("2nd: 8:00 PM - 9:00 PM")
    active_count = len([p for p in st.session_state.participants if p.get('active', True)])
    st.metric("Active Members", active_count)



# Import tab functions
from tab_checkin import show_checkin
from tab_qr_links import show_qr_links
from tab_reports import show_reports
from tab_manage import show_manage
from tab_import import show_import
from tab_garden import show_garden
from tab_residents import show_residents
from tab_admin_scan import show_admin_scan

# Re-run to load tabs after imports
if st.session_state.is_authenticated:
    if st.session_state.user_role == "admin":
        tabs = st.tabs(["Check-In", "QR/Links", "Admin Scan", "Reports", "Manage", "Import", "Garden", "Residents"])
        with tabs[0]: show_checkin(selected_date)
        with tabs[1]: show_qr_links(selected_date)
        with tabs[2]: show_reports(selected_date)
        with tabs[3]: show_manage(selected_date)
        with tabs[4]: show_import(selected_date)
        with tabs[2]: show_admin_scan(selected_date)
        with tabs[5]: show_garden()
        with tabs[6]: show_residents()
    else:
        tabs = st.tabs(["Check-In", "QR/Links", "Admin Scan", "Reports", "Garden"])
        with tabs[0]: show_checkin(selected_date)
        with tabs[1]: show_qr_links(selected_date)
        with tabs[2]: show_admin_scan(selected_date)
        with tabs[3]: show_reports(selected_date)
        with tabs[4]: show_garden()
else:
    st.info("Login to access features")

st.divider()
st.caption("Woodlands Zone 6 Community Hub | PDPA Compliant | v2.0")