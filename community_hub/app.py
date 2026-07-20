import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import urllib.parse
from config import (CHAIRMAN_PASSWORD, supabase, DB_CONNECTED, MOBILE_CSS, ADMIN_PASSWORD, 
    CHECKER_PASSWORD, APP_URL, load_activities, PLOT_TYPES, TOTAL_PLOTS, TYPE_MAP, refresh_data)
from utils import (mask_phone, get_attendance_count, check_and_convert_status, 
    generate_token, verify_token, load_participants, load_plots, get_plot, 
    update_plot, get_user_plot, create_request, get_pending_requests, 
    update_request_status, get_occupied_count, clean_phone_number, 
    find_participant_by_phone, check_returning_guest)

# ===== IMPORT TAB FUNCTIONS (MUST BE AT TOP) =====
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
from tab_chairman import show_chairman

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
    elif role == "chairman": return pwd == CHAIRMAN_PASSWORD
    elif role == "checker": return pwd == CHECKER_PASSWORD
    return False

# ===== URL PARAMETER ROUTING (Public Modes) =====
params = st.query_params

# ===== AUTO CHECK-IN MODE (QR / Link) =====
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
                st.success("Both sessions recorded! See you there!")
            elif s1_done:
                st.write("Session 1: Confirmed")
                if session_param in ['2', 'both'] and not s2_done:
                    supabase.table('attendance').update({"session_2": True}).eq('id', record['id']).execute()
                    st.success("Session 2 added! Both sessions confirmed!")
            elif s2_done:
                st.write("Session 2: Confirmed")
                if session_param in ['1', 'both'] and not s1_done:
                    supabase.table('attendance').update({"session_1": True}).eq('id', record['id']).execute()
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

    st.title("🤝 Volunteer Check-In & Registration")
    st.markdown("<h4 style='text-align:center;'>Woodlands Zone 6 Community Hub</h4>", unsafe_allow_html=True)
    st.success("✅ Volunteer access active — link expires automatically")
    st.divider()

    try:
        all_participants = supabase.table('participants').select("*").eq('active', True).execute().data
    except:
        all_participants = []

    acts = load_activities()
    act_names = [a['name'] for a in acts] if acts else ["Cardio Drumming"]

    selected_activity = st.selectbox("Activity", act_names, index=0, key="vol_act")
    selected_date = st.date_input("Date", value=datetime.now().date(), key="vol_date")

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

    # 🔥 PHASE 5: PHONE-FIRST SMART CHECK-IN ROUTER
    st.subheader("📱 Smart Check-In (Phone Number)")
    st.caption("Enter the resident's 8-digit mobile number to instantly check them in or register them.")

    phone_input = st.text_input("Mobile Number", placeholder="e.g., 91234567", key="vol_phone_input")

    if phone_input and len(clean_phone_number(phone_input)) >= 8:
        clean_phone = clean_phone_number(phone_input)
        resident = find_participant_by_phone(clean_phone)

        if resident:
            status_text = '⭐ Regular' if not resident.get('is_new') else '🆕 New'
            st.markdown(f"""
            <div style="background: #d4edda; border-left: 4px solid #28a745; padding: 15px; border-radius: 8px; margin: 10px 0;">
                <h4 style="margin: 0 0 8px 0; color: #155724; font-size: 18px;">✅ Resident Found</h4>
                <p style="margin: 0 0 5px 0; color: #1a1a1a; font-size: 20px; font-weight: bold;">{resident['name']}</p>
                <p style="margin: 0; color: #495057; font-size: 14px;">Status: {status_text}</p>
            </div>
            """, unsafe_allow_html=True)

            if st.button("✅ Mark Present & Check-In", type="primary", use_container_width=True, key="vol_checkin_found"):
                try:
                    existing_att = supabase.table('attendance').select('id').eq('participant_id', resident['id']).eq('date', str(selected_date)).execute()
                    if existing_att.data:
                        supabase.table('attendance').update({
                            "session_1": s1, "session_2": s2,
                            "timestamp": datetime.now().isoformat(),
                            "source": selected_activity
                        }).eq('id', existing_att.data[0]['id']).execute()
                    else:
                        supabase.table('attendance').insert({
                            "participant_id": resident['id'],
                            "name": resident['name'],
                            "date": str(selected_date),
                            "session_1": s1, "session_2": s2,
                            "timestamp": datetime.now().isoformat(),
                            "self_checkin": False, "source": selected_activity
                        }).execute()
                    st.success(f"✅ {resident['name']} checked in successfully!")
                    st.balloons()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

        else:
            st.markdown(f"""
            <div style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; border-radius: 8px; margin: 10px 0;">
                <h4 style="margin: 0 0 8px 0; color: #856404; font-size: 18px;">❓ Phone Number Not Found</h4>
                <p style="margin: 0; color: #1a1a1a; font-size: 15px;">Would you like to register them or add them as a guest?</p>
            </div>
            """, unsafe_allow_html=True)

            guest_history = check_returning_guest(clean_phone)
            if guest_history:
                st.info(f"💡 This phone number attended as a Guest on {guest_history['created_at'][:10]}. Consider upgrading them to a Permanent Resident!")

            c1, c2 = st.columns(2)
            with c1:
                if st.button("📝 Register Permanent", use_container_width=True, key="vol_reg_perm"):
                    st.session_state.vol_action = "register_permanent"
            with c2:
                if st.button("🚶 Add as Walk-in / Guest", use_container_width=True, key="vol_reg_walkin"):
                    st.session_state.vol_action = "register_walkin"

            if st.session_state.get('vol_action') == "register_permanent":
                with st.form("vol_permanent_form", clear_on_submit=True):
                    st.subheader("Register as Permanent Resident")
                    new_name = st.text_input("Full Name *", placeholder="e.g., AHMAD BIN ISMAIL")
                    new_indemnity = st.checkbox("Indemnity Signed", value=False)
                    
                    if st.form_submit_button("Register & Check-In", type="primary", use_container_width=True):
                        if not new_name.strip():
                            st.error("Name is required")
                        else:
                            # 🔥 BULLETPROOF DUPLICATE CHECK
                            clean_phone = clean_phone_number(phone_input)
                            
                            try:
                                existing_check = supabase.table('participants').select('id, name, contact').eq('contact', clean_phone).eq('active', True).execute()
                                
                                if existing_check.data:
                                    existing_name = existing_check.data[0]['name']
                                    st.error(f"⚠️ **Resident already exists!**\n\nName: **{existing_name}**\nPhone: {mask_phone(clean_phone)}\n\nPlease use the 'Mark Present & Check-In' button above instead.")
                                    st.stop()
                            except Exception as e:
                                st.error(f"Error checking for duplicates: {e}")
                                st.stop()
                            
                            # No duplicate - proceed
                            try:
                                import random
                                new_id = datetime.now().strftime("%Y%m%d%H%M%S") + str(random.randint(10, 99))
                                supabase.table('participants').insert({
                                    "id": new_id, "name": new_name.strip().upper(), "contact": clean_phone,
                                    "indemnity": new_indemnity, "is_new": True, "active": True,
                                    "registration_date": str(selected_date)
                                }).execute()
                                supabase.table('attendance').insert({
                                    "participant_id": new_id, "name": new_name.strip().upper(),
                                    "date": str(selected_date), "session_1": s1, "session_2": s2,
                                    "timestamp": datetime.now().isoformat(), "self_checkin": False,
                                    "source": selected_activity
                                }).execute()
                                st.success(f"✅ {new_name.strip().upper()} registered & checked in!")
                                st.session_state.vol_action = None
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")

            elif st.session_state.get('vol_action') == "register_walkin":
                with st.form("vol_walkin_form", clear_on_submit=True):
                    st.subheader("Add as Walk-in / Guest")
                    walkin_name = st.text_input("Guest Name *", placeholder="e.g., John Doe")
                    st.caption("🔒 PDPA Notice: This number is used solely for community attendance tracking.")
                    
                    if st.form_submit_button("Add Walk-in", type="primary", use_container_width=True):
                        if not walkin_name.strip():
                            st.error("Name is required")
                        else:
                            try:
                                supabase.table('attendance').insert({
                                    "participant_id": f"GUEST_{clean_phone}",
                                    "name": walkin_name.strip().upper(),
                                    "date": str(selected_date), "session_1": s1, "session_2": s2,
                                    "timestamp": datetime.now().isoformat(), "self_checkin": False,
                                    "source": selected_activity
                                }).execute()
                                st.success(f"🚶 {walkin_name.strip().upper()} added as walk-in!")
                                st.session_state.vol_action = None
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")

    st.divider()
    
        # 🔥 ELDERLY / NO PHONE FALLBACK
    with st.expander("👴 Resident does not have a mobile phone?"):
        st.caption("Use this section to search or register residents without a handphone.")
        
        with st.form("no_phone_form"):
            np_name = st.text_input("Full Name *", placeholder="e.g., TAN AH KOW")
            
            c1, c2 = st.columns(2)
            with c1:
                search_np = st.form_submit_button(" Search Existing")
            with c2:
                register_np = st.form_submit_button("📝 Register New")

            # 🔥 FIX: Handle Search Results using Selectbox instead of st.button()
            if search_np and np_name.strip():
                matches = [p for p in all_participants if np_name.strip().upper() in p.get('name', '').upper()]
                st.session_state['np_matches'] = matches
            else:
                if 'np_matches' not in st.session_state:
                    st.session_state['np_matches'] = []

            matches = st.session_state.get('np_matches', [])

            if matches:
                st.success(f"Found {len(matches)} match(es). Please select one:")
                # Create options for selectbox
                match_options = {f"{m['name']} (ID: {m['id'][:8]}...)": m for m in matches}
                selected_label = st.selectbox("Select Resident to Check-In", list(match_options.keys()), key="np_selectbox")
                
                # This is the ONLY way to trigger an action inside a form
                if st.form_submit_button("✅ Confirm Check-In", type="primary", use_container_width=True):
                    if selected_label:
                        selected_resident = match_options[selected_label]
                        try:
                            supabase.table('attendance').insert({
                                "participant_id": selected_resident['id'],
                                "name": selected_resident['name'],
                                "date": str(selected_date),
                                "session_1": s1, "session_2": s2,
                                "timestamp": datetime.now().isoformat(),
                                "self_checkin": False, "source": selected_activity
                            }).execute()
                            st.success(f"✅ {selected_resident['name']} checked in!")
                            st.session_state['np_matches'] = [] # Clear matches after success
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")
            elif search_np and np_name.strip():
                st.warning("No matches found. Please register them as a new resident.")
                
            # 🔥 Handle Registration
            if register_np and np_name.strip():
                # Apply the Ultimate Duplicate Check here too!
                res_name = supabase.table('participants').select('name', 'contact').eq('name', np_name.strip().upper()).eq('active', True).execute()
                if res_name.data:
                    st.error(f"⛔ **Name already exists!**\n\nA resident named **{np_name.strip().upper()}** is already registered.\n\nTo register a different person with the same name, you MUST provide their phone number in the main form above.")
                else:
                    try:
                        import random
                        new_id = datetime.now().strftime("%Y%m%d%H%M%S") + str(random.randint(10, 99))
                        
                        new_data = {
                            "id": new_id, 
                            "name": np_name.strip().upper(), 
                            "contact": "NO_PHONE", 
                            "indemnity": False, 
                            "is_new": True, 
                            "active": True,
                            "registration_date": str(selected_date)
                        }

                        supabase.table('participants').insert(new_data).execute()
                        
                        supabase.table('attendance').insert({
                            "participant_id": new_id, 
                            "name": np_name.strip().upper(),
                            "date": str(selected_date), "session_1": s1, "session_2": s2,
                            "timestamp": datetime.now().isoformat(), "self_checkin": False,
                            "source": selected_activity
                        }).execute()
                        
                        st.success(f"✅ {np_name.strip().upper()} registered & checked in!")
                        st.rerun()
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
        contact = st.text_input("Contact Number", placeholder="e.g., 91234567")
        no_phone = st.checkbox("👴 I do not have a phone")
        indemnity = st.checkbox("Indemnity Form Signed", value=False)

        st.caption("By registering, you confirm the resident has agreed to participate in community activities.")

        submitted = st.form_submit_button("Register Resident", type="primary", use_container_width=True)

        if submitted:
            if not name.strip():
                st.error("Name is required")
            else:
                                # Handle no phone case
                final_contact = "NO_PHONE" if no_phone else contact.strip()
                
                # 🔥 ULTIMATE DUPLICATE CHECK
                clean_contact = clean_phone_number(final_contact) if final_contact != "NO_PHONE" else None

                try:
                    # 1. Check Phone (Strict Block)
                    if clean_contact:
                        res_phone = supabase.table('participants').select('name').eq('contact', clean_contact).eq('active', True).execute()
                        if res_phone.data:
                            st.error(f"⛔ **Phone number already exists!**\n\nResident: **{res_phone.data[0]['name']}**\n\nPlease search for them in the system instead.")
                            st.stop()

                        # 2. Check Name (Hard Block for Public Registration)
                        res_name = supabase.table('participants').select('name', 'contact').eq('name', name.strip().upper()).eq('active', True).execute()
                        if res_name.data:
                            st.error(f" **Name already exists!**\n\nA resident named **{name.strip().upper()}** is already in our system.\n\nIf you are already registered, please use the Check-In link instead of registering again.")
                            st.stop() # 🔥 STOP execution immediately
                        else:
                            # Soft Warning if phone is different
                            st.warning(f"⚠️ **Name Match:** A resident named '{name.strip().upper()}' already exists. Proceeding because phone numbers differ.")
                            
                except Exception as e:
                    st.error(f"Error checking duplicates: {e}")
                    st.stop()
                
                try:
                    new_id = datetime.now().strftime("%Y%m%d%H%M%S") + str(random.randint(10, 99))
                    supabase.table('participants').insert({
                        "id": new_id,
                        "name": name.strip().upper(),
                        "contact": final_contact,
                        "indemnity": indemnity,
                        "is_new": True,
                        "active": True,
                        "registration_date": datetime.now().strftime("%Y-%m-%d")
                    }).execute()
                    st.success(f"✅ {name.strip().upper()} registered successfully!")
                    st.info(f"Resident ID: `{new_id}`")
                    st.caption("They can now use the check-in QR for attendance.")
                except Exception as e:
                    st.error(f"Registration failed: {e}")

    st.divider()
    st.caption("Woodlands Zone 6 Community Hub | Volunteer Registration | Time-limited access")
    st.stop()

# ===== PUBLIC RSVP MODE (Phone-First, expires automatically) =====
if params.get("mode") == "rsvp":
    if not DB_CONNECTED or supabase is None:
        st.error("Database not connected."); st.stop()
    
    token = params.get("tk")
    if not token:
        st.error("❌ Invalid RSVP link."); st.stop()
        
    try:
        sess = supabase.table('sessions').select("*").eq('rsvp_link_token', token).single().execute().data
    except:
        sess = None
        
    if not sess:
        st.error("❌ Session not found or link is invalid."); st.stop()
        
    is_locked = sess.get('status') in ['closed', 'cancelled']
    
    try:
        date_str = sess.get('session_date')
        time_str = sess.get('session_time', '23:59')
        start_time_str = time_str.split('-')[0].strip()
        try: start_time = datetime.strptime(start_time_str, "%I:%M %p").time()
        except: start_time = datetime.strptime(start_time_str, "%H:%M").time()
        
        session_dt = datetime.combine(datetime.strptime(date_str, "%Y-%m-%d").date(), start_time)
        if datetime.now() > session_dt + timedelta(hours=2):
            is_locked = True
    except:
        pass

    if is_locked:
        st.markdown("""
        <div style="background: #ffebee; border-left: 4px solid #f44336; padding: 20px; border-radius: 8px; color: #1a1a1a; text-align: center;">
            <h3>⏰ Session Closed / Expired</h3>
            <p>This session has already ended or been closed by the admin.</p>
            <p><strong>No further RSVPs or check-ins can be recorded.</strong></p>
            <p>Please contact the admin for a new session link.</p>
        </div>
        """, unsafe_allow_html=True)
        st.stop()
        
    st.title(f"📅 {sess['activity_name']}")
    st.markdown(f"<h3 style='text-align:center;'>{sess['session_date']}</h3>", unsafe_allow_html=True)
    st.markdown(f"<h4 style='text-align:center;color:#888;'>{sess['session_time']}</h4>", unsafe_allow_html=True)
    st.divider()
    
    st.subheader("📱 Please confirm your attendance")
    st.caption("Enter your 8-digit mobile number to quickly find your profile.")
    
    rsvp_phone = st.text_input("Mobile Number *", placeholder="e.g., 91234567", key="rsvp_phone_input")
    
    if rsvp_phone and len(clean_phone_number(rsvp_phone)) >= 8:
        clean_phone = clean_phone_number(rsvp_phone)
        resident = find_participant_by_phone(clean_phone)
        
        if resident:
            st.success(f"✅ Welcome back, **{resident['name']}**!")
            
            with st.form("rsvp_form_found"):
                response = st.radio("Will you be attending?", ["👍 Attending", "👎 Not Attending", "⏳ Maybe"], horizontal=True)
                
                acts = load_activities()
                act_config = next((a for a in acts if a['name'] == sess['activity_name']), None)
                s1_label = act_config.get('session_1_label', 'Session 1') if act_config else 'Session 1'
                s2_label = act_config.get('session_2_label', 'Session 2') if act_config else 'Session 2'
                has_s2 = bool(s2_label and s2_label.strip())
                
                s1_attend, s2_attend = True, False
                if has_s2:
                    session_choice = st.radio("Which session(s)?", ["Both", s1_label, s2_label], horizontal=True)
                    s1_attend = session_choice in ["Both", s1_label]
                    s2_attend = session_choice in ["Both", s2_label]
                
                if st.form_submit_button("Confirm RSVP", type="primary", use_container_width=True):
                    try:
                        import uuid
                        resp_map = {"👍 Attending": "attending", "👎 Not Attending": "not_attending", "⏳ Maybe": "maybe"}
                        
                        existing = supabase.table('session_rsvp').select("*").eq('session_id', sess['id']).eq('name', resident['name']).execute().data
                        
                        if existing:
                            supabase.table('session_rsvp').update({
                                "response": resp_map[response], "checked_in": False,
                                "session_1": s1_attend, "session_2": s2_attend, "phone": clean_phone,
                                "updated_at": datetime.now().isoformat()
                            }).eq('id', existing[0]['id']).execute()
                        else:
                            supabase.table('session_rsvp').insert({
                                "id": str(uuid.uuid4()), "session_id": sess['id'],
                                "name": resident['name'], "phone": clean_phone,
                                "response": resp_map[response], "checked_in": False, "is_walk_in": False,
                                "session_1": s1_attend, "session_2": s2_attend,
                                "created_at": datetime.now().isoformat()
                            }).execute()
                        st.success(f"✅ RSVP updated: {response}")
                        st.balloons()
                    except Exception as e:
                        st.error(f"Error: {e}")
        else:
            st.warning("❓ Phone number not found. Please enter your details to RSVP.")
            
            with st.form("rsvp_form_new"):
                new_name = st.text_input("Your Name *", placeholder="e.g., Tan Ah Kow")
                response = st.radio("Will you be attending?", ["👍 Attending", "👎 Not Attending", "⏳ Maybe"], horizontal=True)
                
                acts = load_activities()
                act_config = next((a for a in acts if a['name'] == sess['activity_name']), None)
                s1_label = act_config.get('session_1_label', 'Session 1') if act_config else 'Session 1'
                s2_label = act_config.get('session_2_label', 'Session 2') if act_config else 'Session 2'
                has_s2 = bool(s2_label and s2_label.strip())
                
                s1_attend, s2_attend = True, False
                if has_s2:
                    session_choice = st.radio("Which session(s)?", ["Both", s1_label, s2_label], horizontal=True)
                    s1_attend = session_choice in ["Both", s1_label]
                    s2_attend = session_choice in ["Both", s2_label]
                
                if st.form_submit_button("Submit RSVP", type="primary", use_container_width=True):
                    if not new_name.strip():
                        st.error("Name is required")
                    else:
                        try:
                            import uuid
                            resp_map = {"👍 Attending": "attending", "👎 Not Attending": "not_attending", "⏳ Maybe": "maybe"}
                            
                            supabase.table('session_rsvp').insert({
                                "id": str(uuid.uuid4()), "session_id": sess['id'],
                                "name": new_name.strip().upper(), "phone": clean_phone,
                                "response": resp_map[response], "checked_in": False, "is_walk_in": True,
                                "session_1": s1_attend, "session_2": s2_attend,
                                "created_at": datetime.now().isoformat()
                            }).execute()
                            st.success(f"✅ RSVP submitted: {response}")
                            st.balloons()
                        except Exception as e:
                            st.error(f"Error: {e}")
    else:
        st.info("📱 Enter your 8-digit mobile number to continue.")

    # 🔥 ELDERLY / NO PHONE FALLBACK FOR RSVP
    st.divider()
    with st.expander("👴 I do not have a mobile phone"):
        st.caption("Please enter your details below to RSVP. A volunteer will assist you at the venue.")
        
        with st.form("no_phone_rsvp_form"):
            np_name = st.text_input("Full Name *", placeholder="e.g., TAN AH KOW")
            
            response = st.radio("Will you be attending?", ["👍 Attending", "👎 Not Attending", "⏳ Maybe"], horizontal=True)
            
            if st.form_submit_button("Submit RSVP", type="primary", use_container_width=True):
                if not np_name.strip():
                    st.error("Name is required")
                else:
                    try:
                        import uuid
                        resp_map = {"👍 Attending": "attending", "👎 Not Attending": "not_attending", "⏳ Maybe": "maybe"}
                        
                        existing = supabase.table('session_rsvp').select("*").eq('session_id', sess['id']).eq('name', np_name.strip().upper()).execute().data
                        
                        rsvp_data = {
                            "session_id": sess['id'],
                            "name": np_name.strip().upper(),
                            "phone": "NO_PHONE",
                            "response": resp_map[response], 
                            "checked_in": False, 
                            "is_walk_in": False,
                            "session_1": True, "session_2": False,
                            "updated_at": datetime.now().isoformat()
                        }

                        if existing:
                            supabase.table('session_rsvp').update(rsvp_data).eq('id', existing[0]['id']).execute()
                        else:
                            rsvp_data["id"] = str(uuid.uuid4())
                            rsvp_data["created_at"] = datetime.now().isoformat()
                            supabase.table('session_rsvp').insert(rsvp_data).execute()
                            
                        st.success(f"✅ RSVP submitted: {response}")
                        st.balloons()
                    except Exception as e:
                        st.error(f"Error: {e}")
        
    st.divider()
    st.caption("Woodlands Zone 6 Community Hub | RSVP System")
    st.stop()

# ===== MAIN APP (Admin Dashboard) =====
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

if not st.session_state.participants:
    st.session_state.participants = load_participants()
if not st.session_state.plots:
    st.session_state.plots = load_plots()
if not st.session_state.activities:
    st.session_state.activities = load_activities()

# 🔥 FIX: Wrap ALL dashboard elements inside this authenticated block
if st.session_state.is_authenticated:
    # Header for logged-in users
    col1, col2 = st.columns([3,1])
    with col1: st.subheader("Admin Dashboard")
    with col2:
        st.caption(f"{datetime.now().strftime('%d %b %Y')}")
        if st.button("Logout", use_container_width=True):
            st.session_state.is_authenticated = False
            st.session_state.user_role = None
            st.session_state.show_login = False
            st.rerun()

    # 🔥 CHAIRMAN TERMS & CONDITIONS (Digital Handshake)
    if st.session_state.user_role == "chairman" and not st.session_state.get("chairman_tc_accepted"):
        st.title("📜 System Usage Policy")
        st.markdown("""
        Welcome, Chairman. You have been granted limited administrative access to the 
        **Woodlands Zone 6 Community Hub**. By proceeding, you agree to:
        
        1. **Maintain strict PDPA compliance:** Never share resident personal data externally.
        2. **Use this system solely for community management and oversight.**
        3. **Keep your login credentials secure.**
        
        *All administrative actions are logged in the Audit Trail for accountability.*
        """)
        
        if st.checkbox("I have read and agree to the Terms of Use"):
            if st.button("Accept & Continue", type="primary", use_container_width=True):
                st.session_state.chairman_tc_accepted = True
                st.rerun()
        st.stop()

    # ── MOBILE TOP BAR (Now strictly INSIDE the authenticated block) ──
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
            st.write(" "); st.write(" ")
            if st.button("🔄", key="mobile_refresh"):
                refresh_data(); st.session_state.participants = load_participants()
                st.session_state.plots = load_plots(); st.session_state.activities = load_activities()
                st.success("Refreshed!"); st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    # Tab Routing
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
        
    elif st.session_state.user_role == "chairman":
        tabs = st.tabs(["📊 Overview", "Reports", "Meeting", "Garden", "Residents", "Sessions","Volunteer Access"])
        with tabs[0]: show_chairman()
        with tabs[1]: show_reports(selected_date)
        with tabs[2]: show_meeting(selected_date)
        with tabs[3]: show_garden()
        with tabs[4]: show_residents()
        with tabs[5]: show_volunteer_access()  # ✅ This line MUST be her
        with tabs[6]: show_sessions(supabase, st.session_state.user_role)
        e
        
    else: # checker
        tabs = st.tabs(["QR/Links", "Admin Scan", "Reports", "Volunteer", "Garden", "Sessions"])
        with tabs[0]: show_qr_links(selected_date)
        with tabs[1]: show_admin_scan(selected_date)
        with tabs[2]: show_reports(selected_date)
        with tabs[3]: show_volunteer()
        with tabs[4]: show_garden()
        with tabs[5]: show_sessions(supabase, st.session_state.user_role)

else:
    # NOT AUTHENTICATED: Show ONLY the Login Screen
    st.subheader("Admin Dashboard")
    st.caption(f"{datetime.now().strftime('%d %b %Y')}")
    
    if st.session_state.show_login:
        st.divider(); st.subheader("Login")
        c1, c2 = st.columns([2,1])
        with c1:
            pwd = st.text_input("Password", type="password", key="login_pwd")
            st.caption("Checker: Attendance | Chairman: Oversight | Admin: Full Access")
        with c2:
            st.write(" "); st.write(" ")
            if st.button("Login", type="primary", use_container_width=True):
                if verify_password(pwd, "admin"):
                    st.session_state.is_authenticated = True
                    st.session_state.user_role = "admin"
                elif verify_password(pwd, "chairman"):
                    st.session_state.is_authenticated = True
                    st.session_state.user_role = "chairman"
                elif verify_password(pwd, "checker"):
                    st.session_state.is_authenticated = True
                    st.session_state.user_role = "checker"
                else:
                    st.error("Invalid password")
                
                if st.session_state.is_authenticated:
                    st.session_state.show_login = False
                    st.rerun()
            if st.button("Cancel", use_container_width=True):
                st.session_state.show_login = False
                st.rerun()
    else:
        st.info("Please login to access admin features")
        if st.button("Login", type="primary", use_container_width=True):
            st.session_state.show_login = True
            st.rerun()

st.divider()
st.caption("Woodlands Zone 6 Community Hub | PDPA Compliant | v2.1")