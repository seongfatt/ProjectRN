import streamlit as st
from datetime import datetime, timezone
from config import supabase, DB_CONNECTED, load_activities, refresh_data
from utils import clean_phone_number, find_participant_by_phone
import urllib.parse

def show_checkin(selected_date):
    # 🔥 CSS FOR PROFESSIONAL DESIGN
    st.markdown("""
    <style>
    .volunteer-banner {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white; padding: 15px; border-radius: 10px; text-align: center;
        margin-bottom: 20px; font-weight: 600; box-shadow: 0 4px 10px rgba(0,0,0,0.15);
    }
    .participant-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 15px; padding: 20px; margin: 10px 0; color: white;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }
    .participant-card h3 { margin: 0 0 10px 0; font-size: 24px; }
    .participant-info { font-size: 14px; opacity: 0.9; margin: 5px 0; }
    .already-checked {
        background: #e3f2fd; border-left: 5px solid #2196f3;
        padding: 15px; border-radius: 8px; margin-top: 15px; color: #1a1a1a;
    }
    .phone-section {
        background: #f8f9fa; border: 2px solid #e0e0e0; border-radius: 15px;
        padding: 25px; margin: 20px 0;
    }
    </style>
    """, unsafe_allow_html=True)

    st.title("🏘️ Community Check-In Hub")
    
    # 🔒 VOLUNTEER BANNER
    role = st.session_state.get('user_role', 'Unknown').upper()
    st.markdown(f"""
    <div class="volunteer-banner">
        🔐 Logged in as: {role} | All scans are recorded under this session.
    </div>
    """, unsafe_allow_html=True)
    
    if not DB_CONNECTED:
        st.error("Database not connected")
        return

    activity = st.session_state.get('selected_activity', 'Cardio Drumming')
    acts = load_activities()
    act_config = next((a for a in acts if a['name'] == activity), None)
    s1_label = act_config.get('session_1_label', 'Session 1') if act_config else 'Session 1'
    s2_label = act_config.get('session_2_label', 'Session 2') if act_config else 'Session 2'
    has_s2 = bool(s2_label and s2_label.strip())

    st.subheader(" Select Session")
    if has_s2:
        session_option = st.radio("Which session?", ["Both", s1_label, s2_label], horizontal=True, key="kiosk_session")
        s1 = session_option in ["Both", s1_label]
        s2 = session_option in ["Both", s2_label]
    else:
        st.info(f"️ Only one session: {s1_label}")
        s1, s2 = True, False

    st.divider()

    # 🔥 QR / ID SCANNER INPUT (Native Streamlit - Works with USB Scanners)
    st.subheader("📱 Scan QR Code or Enter ID")
    st.caption("💡 Tip: If using a USB scanner, click the box below and scan. The system will auto-detect the ID.")
    
    scanned_input = st.text_input(
        "Scan QR code or enter ID...", 
        key="scanner_input_main", 
        placeholder="e.g., 2026080316562190", 
        label_visibility="collapsed"
    )
    
    # Process the input immediately when it changes (scanner hits Enter)
    if scanned_input and len(scanned_input.strip()) > 5:
        input_text = scanned_input.strip()
        extracted_pid = None
        
        # Check if it's a full URL
        if 'pid=' in input_text or input_text.startswith('http'):
            try:
                parsed_url = urllib.parse.urlparse(input_text)
                query_params = urllib.parse.parse_qs(parsed_url.query)
                extracted_pid = query_params.get('pid', [None])[0]
            except Exception:
                pass
        else:
            extracted_pid = input_text
            
        if extracted_pid:
            process_checkin_by_id(extracted_pid, selected_date, activity, s1, s2)
            # Clear the input by resetting the key via a rerun or just let user clear it
            # To make it feel like a kiosk, we can use a session state flag to clear it, 
            # but for now, we just process it.
            st.rerun()

    st.divider()

    # ── PHONE SEARCH ──────────────────
    st.markdown('<div class="phone-section">', unsafe_allow_html=True)
    st.subheader("📱 Quick Check-In by Phone")
    phone_input = st.text_input("Enter 8-digit mobile number", placeholder="e.g., 91234567", key="checkin_phone")

    if phone_input and len(clean_phone_number(phone_input)) >= 8:
        clean_phone = clean_phone_number(phone_input)
        resident = find_participant_by_phone(clean_phone)

        if resident:
            try:
                existing_check = supabase.table('attendance').select("*") \
                    .eq('participant_id', resident['id']) \
                    .eq('date', str(selected_date)) \
                    .eq('source', activity) \
                    .execute()
                
                already_checked = existing_check.data is not None and len(existing_check.data) > 0
                
                if already_checked:
                    st.markdown(f"""
                    <div class="already-checked">
                        <h4 style="margin: 0; color: #0d47a1;">ℹ️ Already Checked In</h4>
                        <p style="margin: 5px 0 0 0;"><strong>{resident['name']}</strong> is already recorded for today.</p>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div style="background: #e8f5e9; border: 2px solid #4CAF50; padding: 20px; border-radius: 15px; margin: 10px 0; color: #1a1a1a;">
                        <h3 style="margin:0;">✅ {resident['name']}</h3>
                        <p style="margin:5px 0 0 0; color:#666;">ID: {resident['id'][:12]}...</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if st.button("Confirm Check-In", type="primary", key=f"confirm_{resident['id']}", use_container_width=True):
                        process_checkin_by_id(resident['id'], selected_date, activity, s1, s2)
                        st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")
        else:
            st.warning("❓ Phone not found.")
    st.markdown('</div>', unsafe_allow_html=True)

    st.divider()

    # ── NAME LIST ──────────────────
    show_names = st.checkbox("👁️ Show participant names", value=True, key="show_names_toggle")
    
    if show_names:
        st.subheader("🔍 Find by Name")
        participants = st.session_state.get('participants', [])
        active_participants = [p for p in participants if p.get('active', True)]
        
        # Filter by activity
        try:
            att_data = supabase.table('attendance').select('participant_id').eq('source', activity).execute().data
            activity_attendees = {rec['participant_id'] for rec in att_data}
            active_participants = [p for p in active_participants if p['id'] in activity_attendees]
        except:
            pass
        
        name_search = st.text_input("Type name to search...", key="checkin_name_search")
        if name_search:
            s = name_search.lower()
            active_participants = [p for p in active_participants if s in p['name'].lower()]
        
        st.caption(f"📊 Showing {len(active_participants)} participant(s)")
        
        if active_participants:
            cols = st.columns(4) # 4 Columns for better view
            for i, p in enumerate(active_participants):
                with cols[i % 4]:
                    try:
                        existing_check = supabase.table('attendance').select("*") \
                            .eq('participant_id', p['id']) \
                            .eq('date', str(selected_date)) \
                            .eq('source', activity) \
                            .execute()
                        already_checked = existing_check.data is not None and len(existing_check.data) > 0
                    except:
                        already_checked = False
                    
                    st.markdown(f"""
                    <div class="participant-card">
                        <h3>{p['name']}</h3>
                        <div class="participant-info">🆔 ID: {p['id'][:12]}...</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if already_checked:
                        st.markdown('<div class="already-checked" style="margin-top:5px; padding:10px;"><b>✅ Checked In</b></div>', unsafe_allow_html=True)
                    else:
                        if st.button("Check In", key=f"btn_{p['id']}", use_container_width=True, type="primary"):
                            process_checkin_by_id(p['id'], selected_date, activity, s1, s2)
                            st.rerun()

def process_checkin_by_id(pid, date, activity, s1, s2):
    """Core logic to mark attendance - Fixed Date Format Issue"""
    try:
        # 🔥 FIX: Handle different date formats correctly
        if isinstance(date, str):
            # If it's a string like "20260804"
            if len(date) == 8 and date.isdigit():
                formatted_date = datetime.strptime(date, "%Y%m%d").strftime("%Y-%m-%d")
            else:
                formatted_date = date  # Assume it's already "YYYY-MM-DD"
        else:
            # If it's a datetime.date object from st.date_input (e.g., 2026-08-04)
            formatted_date = date.strftime("%Y-%m-%d")
        
        # Check existing
        existing = supabase.table('attendance').select("*") \
            .eq('participant_id', pid).eq('date', formatted_date).eq('source', activity).execute()
        
        if existing.data and len(existing.data) > 0:
            res = supabase.table('participants').select("name").eq('id', pid).execute()
            name = res.data[0]['name'] if res.data else "Resident"
            st.info(f"ℹ️ **{name}** is already checked in today.")
            return
        
        # Fetch details
        res = supabase.table('participants').select("*").eq('id', pid).execute()
        if not res.data:
            st.error(f"❌ Resident ID not found: {pid}")
            return
            
        resident = res.data[0]
        
        # Insert
        supabase.table('attendance').insert({
            "participant_id": pid, "name": resident['name'], "date": formatted_date,
            "session_1": s1, "session_2": s2, "timestamp": datetime.now(timezone.utc).isoformat(),
            "self_checkin": False, "source": activity
        }).execute()
        
        refresh_data()
        st.success(f"✅ Successfully checked in **{resident['name']}**!")
        st.rerun()
        
    except Exception as e:
        if 'duplicate key' in str(e):
            st.info("ℹ️ Already checked in today.")
        else:
            st.error(f"Error: {e}")