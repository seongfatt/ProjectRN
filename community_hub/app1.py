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

# Hide sidebar completely on all screen sizes
st.markdown("""
<style>
    [data-testid="stSidebar"] {display: none !important;}
    [data-testid="stSidebarCollapseButton"] {display: none !important;}
    [data-testid="collapsedControl"] {display: none !important;}
</style>
""", unsafe_allow_html=True)

st.set_page_config(page_title="Woodlands Zone 6 - Community Hub", layout="centered", initial_sidebar_state="collapsed")
st.markdown(MOBILE_CSS, unsafe_allow_html=True)

for k in ['is_authenticated','user_role','show_login','participants','plots','activities','today_date','selected_plot','selected_activity','auto_checkin_done']:
    if k not in st.session_state:
        st.session_state[k] = None if k in ['user_role','selected_plot','selected_activity'] else (False if k in ['is_authenticated','auto_checkin_done'] else ([] if k in ['participants','plots','activities'] else datetime.now().date()))

def verify_password(pwd, role):
    if role == "admin": return pwd == ADMIN_PASSWORD
    elif role == "checker": return pwd == CHECKER_PASSWORD
    return False

# ===== AUTO CHECK-IN MODE (QR / Link) =====
params = st.query_params
if params.get("mode") == "auto":
    if not DB_CONNECTED or supabase is None:
        st.error("Database not connected."); st.stop()

    pid = params.get("pid")
    date_str = params.get("date", datetime.now().strftime("%Y%m%d"))
    token = params.get("tk")
    act = params.get("act", "Cardio Drumming")
    session_param = params.get("session", "both")

    if not verify_token(pid, date_str, token):
        st.error("Invalid or expired link."); st.stop()

    try:
        p = supabase.table('participants').select("*").eq('id', pid).execute().data[0]
    except:
        st.error("Participant not found"); st.stop()

    try:
        existing = supabase.table('attendance').select("*")\
            .eq('participant_id', pid)\
            .eq('date', datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d"))\
            .eq('source', act)\
            .execute()

        if existing.data:
            record = existing.data[0]
            s1_done = record.get('session_1', False)
            s2_done = record.get('session_2', False)

            st.title(f"{act}")
            st.success(f"Hello {p['name']}!")
            st.info(f"You already checked in for {datetime.strptime(date_str, '%Y%m%d').strftime('%d %B %Y')}")

            if s1_done and s2_done:
                st.status()
                st.success("Both sessions recorded! See you there!")
            elif s1_done:
                st.write("Session 1: Confirmed")
                if session_param in ['2', 'both'] and not s2_done:
                    supabase.table('attendance').update({"session_2": True}).eq('id', record['id']).execute()
                    st.status()
                    st.success("Session 2 added! Both sessions confirmed!")
            elif s2_done:
                st.write("Session 2: Confirmed")
                if session_param in ['1', 'both'] and not s1_done:
                    supabase.table('attendance').update({"session_1": True}).eq('id', record['id']).execute()
                    st.status()
                    st.success("Session 1 added! Both sessions confirmed!")
            st.stop()
    except Exception as e:
        pass

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
            check_and_convert_status(pid, p['name'])

        except Exception as e:
            st.error(f"Error saving: {e}")
            st.stop()

    st.title(f"{act}")
    st.status()
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

# ===== LEGACY CHECK-IN MODE (with checkbox) =====
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
                st.status()
                st.success("Thank You!"); st.info("Attendance confirmed!")
            except:
                st.error("Error saving. Contact admin.")
    st.stop()

# ===== VOLUNTEER CHECK-IN MODE (Time-limited, no login) =====
if params.get("mode") == "volunteer":
    if not DB_CONNECTED or supabase is None:
        st.error("Database not connected."); st.stop()

    token = params.get("tk")
    if not token:
        st.error("❌ Invalid volunteer link. No token provided."); st.stop()

    # Validate token
    from tab_volunteer_access import validate_volunteer_token
    is_valid, msg = validate_volunteer_token(token)
    if not is_valid:
        st.error(f"❌ {msg}")
        st.markdown("""
        <div style="background: #ffebee; border-left: 4px solid #f44336; padding: 20px; border-radius: 8px; color: #1a1a1a; text-align: center;">
            <h3>⏰ Access Expired</h3>
            <p>This volunteer link is no longer valid.</p>
            <p>Please contact the admin for a new link.</p>
        </div>
        """, unsafe_allow_html=True)
        st.stop()

    # Volunteer is valid — show check-in + registration interface
    st.title("🤝 Volunteer Check-In & Registration")
    st.markdown("<h4 style='text-align:center;'>Woodlands Zone 6 Community Hub</h4>", unsafe_allow_html=True)
    st.success("✅ Volunteer access active — link expires automatically")
    st.divider()

    # Load participants
    try:
        all_participants = supabase.table('participants').select("*").eq('active', True).execute().data
    except:
        all_participants = []

    # Get activities
    acts = load_activities()
    act_names = [a['name'] for a in acts] if acts else ["Cardio Drumming"]

    selected_activity = st.selectbox("Activity", act_names, index=0, key="vol_act")
    selected_date = st.date_input("Date", value=datetime.now().date(), key="vol_date")

    # Dynamic session options based on activity config
    act_config = next((a for a in acts if a['name'] == selected_activity), None)
    s1_label = act_config.get('session_1_label', 'Session 1') if act_config else 'Session 1'
    s2_label = act_config.get('session_2_label', 'Session 2') if act_config else 'Session 2'
    has_s2 = bool(s2_label and s2_label.strip())

    if has_s2:
        session_options = ["Both", s1_label, s2_label]
        session_option = st.radio("Session", session_options, horizontal=True, key="vol_session")
        s1 = session_option in ["Both", s1_label]
        s2 = session_option in ["Both", s2_label]
    else:
        st.info(f"This activity has only one session: {s1_label}")
        session_option = s1_label
        s1 = True
        s2 = False

    st.divider()

    # ── CHECK-IN EXISTING RESIDENTS ──
    st.subheader("Check-In Existing Residents")
    search = st.text_input("Search resident name", placeholder="Type to filter...", key="vol_search")
    filtered = [p for p in all_participants if p.get('active', True)]
    if search:
        s = search.lower()
        filtered = [p for p in filtered if s in p['name'].lower() or s in p.get('contact', '')[-4:]]

    if not filtered:
        st.info("No residents found")
    else:
        show_all = st.toggle("Show All", value=False, key="vol_show_all")
        display = filtered if show_all else filtered[:12]
        st.caption(f"Showing {len(display)} of {len(filtered)} residents")

        cols = st.columns(3)
        for i, p in enumerate(display):
            with cols[i % 3]:
                st.markdown(f"**{p['name']}**")
                st.caption(f"ID: {p['id'][:15]}...")
                try:
                    existing = supabase.table('attendance').select("*")                         .eq('participant_id', p['id'])                         .eq('date', str(selected_date))                         .eq('source', selected_activity)                         .execute()
                    already_done = bool(existing.data)
                except:
                    already_done = False

                if already_done:
                    st.success("✅ Done")
                else:
                    if st.button(f"Mark Present", key=f"vol_mark_{p['id']}", use_container_width=True):
                        try:
                            supabase.table('attendance').insert({
                                "participant_id": p['id'],
                                "name": p['name'],
                                "date": str(selected_date),
                                "session_1": s1,
                                "session_2": s2,
                                "timestamp": datetime.now().isoformat(),
                                "self_checkin": False,
                                "source": selected_activity
                            }).execute()
                            st.success(f"{p['name']} checked in!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")

    st.divider()

    # ── REGISTER NEW RESIDENT ──
    st.subheader("Register New Resident")
    with st.form("volunteer_register", clear_on_submit=True):
        new_name = st.text_input("Full Name *", placeholder="e.g., AHMAD BIN ISMAIL")
        new_contact = st.text_input("Contact Number *", placeholder="e.g., 91234567")
        new_indemnity = st.checkbox("Indemnity Signed", value=False)
        if st.form_submit_button("Register & Check-In", type="primary", use_container_width=True):
            if not new_name.strip():
                st.error("Name is required")
            elif not new_contact.strip():
                st.error("Contact is required")
            else:
                try:
                    import random
                    new_id = datetime.now().strftime("%Y%m%d%H%M%S") + str(random.randint(10, 99))
                    supabase.table('participants').insert({
                        "id": new_id,
                        "name": new_name.strip().upper(),
                        "contact": new_contact.strip(),
                        "indemnity": new_indemnity,
                        "is_new": True,
                        "active": True,
                        "registration_date": str(selected_date)
                    }).execute()
                    # Also check them in immediately
                    supabase.table('attendance').insert({
                        "participant_id": new_id,
                        "name": new_name.strip().upper(),
                        "date": str(selected_date),
                        "session_1": s1,
                        "session_2": s2,
                        "timestamp": datetime.now().isoformat(),
                        "self_checkin": False,
                        "source": selected_activity
                    }).execute()
                    st.success(f"✅ {new_name.strip().upper()} registered & checked in!")
                    st.status()
                except Exception as e:
                    st.error(f"Error: {e}")

    st.divider()
    st.caption("Woodlands Zone 6 Community Hub | Volunteer Access | Link expires automatically")
    st.stop()

# ===== VOLUNTEER REGISTRATION MODE (Token-protected, time-limited) =====
if params.get("mode") == "register":
    import random
    if not DB_CONNECTED or supabase is None:
        st.error("Database not connected."); st.stop()

    token = params.get("tk")
    if not token:
        st.error("❌ Invalid registration link. No token provided.")
        st.markdown("""
        <div style="background: #ffebee; border-left: 4px solid #f44336; padding: 20px; border-radius: 8px; color: #1a1a1a; text-align: center;">
            <h3>🔗 Invalid Link</h3>
            <p>This registration link is missing a security token.</p>
            <p>Please contact the admin for a valid volunteer link.</p>
        </div>
        """, unsafe_allow_html=True)
        st.stop()

    # Validate token
    from tab_volunteer_access import validate_volunteer_token
    is_valid, msg = validate_volunteer_token(token)
    if not is_valid:
        st.error(f"❌ {msg}")
        st.markdown("""
        <div style="background: #ffebee; border-left: 4px solid #f44336; padding: 20px; border-radius: 8px; color: #1a1a1a; text-align: center;">
            <h3>⏰ Access Expired</h3>
            <p>This registration link is no longer valid.</p>
            <p>Please contact the admin for a new volunteer link.</p>
        </div>
        """, unsafe_allow_html=True)
        st.stop()

    st.title("📝 New Resident Registration")
    st.markdown("<h4 style='text-align:center;'>Woodlands Zone 6 Community Hub</h4>", unsafe_allow_html=True)
    st.success("✅ Registration access active — link expires automatically")
    st.divider()

    with st.form("public_register", clear_on_submit=True):
        name = st.text_input("Full Name *", placeholder="e.g., AHMAD BIN ISMAIL")
        contact = st.text_input("Contact Number *", placeholder="e.g., 91234567")
        indemnity = st.checkbox("Indemnity Form Signed", value=False)

        st.caption("By registering, you confirm the resident has agreed to participate in community activities.")

        submitted = st.form_submit_button("Register Resident", type="primary", use_container_width=True)

        if submitted:
            if not name.strip():
                st.error("Name is required")
            elif not contact.strip():
                st.error("Contact is required")
            else:
                try:
                    new_id = datetime.now().strftime("%Y%m%d%H%M%S") + str(random.randint(10, 99))
                    supabase.table('participants').insert({
                        "id": new_id,
                        "name": name.strip().upper(),
                        "contact": contact.strip(),
                        "indemnity": indemnity,
                        "is_new": True,
                        "active": True,
                        "registration_date": datetime.now().strftime("%Y-%m-%d")
                    }).execute()
                    st.success(f"✅ {name.strip().upper()} registered successfully!")
                    st.status()
                    st.info(f"Resident ID: `{new_id}`")
                    st.caption("They can now use the check-in QR for attendance.")
                except Exception as e:
                    st.error(f"Registration failed: {e}")

         # ===== RSVP MODE (Public link, no login) =====
        if params.get("mode") == "rsvp":
            if not DB_CONNECTED or supabase is None:
                st.error("Database not connected."); st.stop()

            token = params.get("tk")
            if not token:
                st.error("❌ Invalid RSVP link."); st.stop()

            try:
                sessions = supabase.table('sessions').select("*").eq('rsvp_link_token', token).execute().data
                if not sessions:
                    st.error("❌ Session not found or link expired."); st.stop()
                sess = sessions[0]
            except:
                st.error("❌ Error loading session."); st.stop()

            if sess.get('status') != 'open':
                st.error("⏰ This session is closed. RSVP no longer accepted."); st.stop()

            st.title(f"📅 {sess['activity_name']}")
            st.markdown(f"<h3 style='text-align:center;'>{sess['session_date']}</h3>", unsafe_allow_html=True)
            st.markdown(f"<h4 style='text-align:center;color:#888;'>{sess['session_time']}</h4>", unsafe_allow_html=True)
            st.divider()

            with st.form("rsvp_form", clear_on_submit=True):
                st.subheader("Will you be attending?")
                name = st.text_input("Your Name *", placeholder="e.g., Tan Ah Kow")
                response = st.radio("Response", ["👍 Attending", "👎 Not Attending", "🤔 Maybe"], horizontal=True)

                if st.form_submit_button("Submit RSVP", type="primary", use_container_width=True):
                    if not name.strip():
                        st.error("Please enter your name")
                    else:
                        try:
                            existing = supabase.table('session_rsvp').select("*")\
                                .eq('session_id', sess['id'])\
                                .eq('name', name.strip())\
                                .execute().data

                            resp_map = {"👍 Attending": "attending", "👎 Not Attending": "not_attending", "🤔 Maybe": "maybe"}

                            if existing:
                                supabase.table('session_rsvp').update({
                                    "response": resp_map[response],
                                    "responded_at": datetime.now().isoformat()
                                }).eq('id', existing[0]['id']).execute()
                                st.success(f"✅ RSVP updated: {response}")
                            else:
                                supabase.table('session_rsvp').insert({
                                    "session_id": sess['id'],
                                    "name": name.strip(),
                                    "response": resp_map[response],
                                    "responded_at": datetime.now().isoformat(),
                                    "is_walk_in": False
                                }).execute()
                                st.success(f"✅ RSVP submitted: {response}")
                            st.balloons()
                        except Exception as e:
                            st.error(f"Error: {e}")

            st.divider()
            st.caption("Woodlands Zone 6 Community Hub | RSVP System")
            st.stop()
            
    st.divider()
    st.caption("Woodlands Zone 6 Community Hub | Volunteer Registration | Time-limited access")
    st.stop()

# ===== MAIN APP =====
# RN Logo + Title
c1, c2 = st.columns([1, 4])
with c1:
    try:
        st.image("logo.png", width=80)
    except:
        st.markdown("🏘️")
with c2:
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

# Auth UI — simplified, no top login button
# Auth UI
if st.session_state.is_authenticated:
    col1, col2 = st.columns([3,1])
    with col1: st.subheader("Admin Dashboard")
    with col2:
        st.caption(f"{datetime.now().strftime('%d %b %Y')}")
        if st.button("Logout", use_container_width=True):
            st.session_state.is_authenticated = False
            st.session_state.user_role = None
            st.session_state.show_login = False
            st.rerun()
    
    # role_badge = "Admin" if st.session_state.user_role == "admin" else "Checker"
    # st.success(f"{role_badge} - {'Full Access' if st.session_state.user_role=='admin' else 'Attendance Only'}")
else:
    st.subheader("Admin Dashboard")
    st.caption(f"{datetime.now().strftime('%d %b %Y')}")
    
    if st.session_state.show_login:
        st.divider(); st.subheader("Login")
        c1, c2 = st.columns([2,1])
        with c1:
            pwd = st.text_input("Password", type="password", key="login_pwd")
            st.caption("Checker: Attendance only | Admin: Full access")
        with c2:
            st.write(" "); st.write(" ")
            if st.button("Login", type="primary", use_container_width=True):
                if verify_password(pwd, "admin"):
                    st.session_state.is_authenticated = True
                    st.session_state.user_role = "admin"
                    st.session_state.show_login = False
                    st.rerun()
                elif verify_password(pwd, "checker"):
                    st.session_state.is_authenticated = True
                    st.session_state.user_role = "checker"
                    st.session_state.show_login = False
                    st.rerun()
                else:
                    st.error("Invalid password")
            if st.button("Cancel", use_container_width=True):
                st.session_state.show_login = False
                st.rerun()
    else:
        st.info("Please login to access admin features")
        if st.button("Login", type="primary", use_container_width=True):
            st.session_state.show_login = True
            st.rerun()

# if st.session_state.is_authenticated:
#     role_badge = "Admin" if st.session_state.user_role == "admin" else "Checker"
#     st.success(f"{role_badge} - {'Full Access' if st.session_state.user_role=='admin' else 'Attendance Only'}")
# else:
#     st.info("Please login to access admin features")

# Top bar for mobile — date, activity, refresh
st.markdown("""
<style>
@media(max-width:768px){
    [data-testid="stSidebar"]{display:none!important;}
    [data-testid="stSidebarCollapseButton"]{display:none!important;}
    .mobile-topbar{background:#1a1a2e;padding:10px;border-radius:8px;margin-bottom:10px;}
}
@media(min-width:769px){
    .mobile-topbar{display:none;}
}
</style>
""", unsafe_allow_html=True)

# Mobile top bar
with st.container():
    st.markdown('<div class="mobile-topbar">', unsafe_allow_html=True)
    m1, m2, m3 = st.columns([2, 2, 1])
    with m1:
        selected_date = st.date_input("📅 Date", value=st.session_state.today_date, key="mobile_date")
    with m2:
        if st.session_state.activities:
            act_names = [a['name'] for a in st.session_state.activities]
            selected_act = st.selectbox("🎯 Activity", act_names, index=0, key="mobile_act")
            st.session_state.selected_activity = selected_act
        else:
            st.session_state.selected_activity = "Cardio Drumming"
    with m3:
        st.write(""); st.write("")
        if st.button("🔄", key="mobile_refresh"):
            refresh_data(); st.session_state.participants = load_participants()
            st.session_state.plots = load_plots(); st.session_state.activities = load_activities()
            st.success("Refreshed!"); st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)


# Import tab functions
from tab_checkin import show_checkin
from tab_qr_links import show_qr_links
from tab_reports import show_reports
from tab_manage import show_manage
from tab_import import show_import
from tab_garden import show_garden
from tab_residents import show_residents
from tab_admin_scan import show_admin_scan
from tab_meeting import show_meeting
from tab_volunteer import show_volunteer
from tab_volunteer_access import show_volunteer_access
from tab_sessions import show_sessions

# Re-run to load tabs after imports
if st.session_state.is_authenticated:
    if st.session_state.user_role == "admin":
        tabs = st.tabs(["QR/Links", "Admin Scan", "Reports", "Meeting", "Volunteer", "Volunteer Access", "Manage", "Import", "Garden", "Residents", "Sessions"])
        with tabs[0]: show_qr_links(selected_date)
        with tabs[1]: show_admin_scan(selected_date)
        with tabs[2]: show_reports(selected_date)
        with tabs[3]: show_meeting(selected_date)
        with tabs[4]: show_volunteer()
        with tabs[5]: show_volunteer_access()
        with tabs[6]: show_manage(selected_date)
        with tabs[7]: show_import(selected_date)
        with tabs[8]: show_garden()
        with tabs[9]: show_residents()
        with tabs[10]: show_sessions(supabase, st.session_state.user_role)
    else:
        tabs = st.tabs(["QR/Links", "Admin Scan", "Reports", "Volunteer", "Garden", "Sessions"])
        with tabs[0]: show_qr_links(selected_date)
        with tabs[1]: show_admin_scan(selected_date)
        with tabs[2]: show_reports(selected_date)
        with tabs[3]: show_volunteer()
        with tabs[4]: show_garden()
        with tabs[5]: show_sessions(supabase, st.session_state.user_role)
else:
    st.info("Login to access features")

st.divider()
st.caption("Woodlands Zone 6 Community Hub | PDPA Compliant | v2.1")
