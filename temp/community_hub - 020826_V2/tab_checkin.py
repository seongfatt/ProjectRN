import streamlit as st
from datetime import datetime, timezone
from config import supabase, DB_CONNECTED, load_activities
from utils import clean_phone_number, find_participant_by_phone

def show_checkin(selected_date):
    # 🔥 CSS FOR COLORFUL DESIGN
    st.markdown("""
    <style>
    .checkin-card {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        padding: 20px;
        border-radius: 12px;
        margin: 10px 0;
        color: white;
    }
    .checkin-button {
        background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%);
        color: white;
        font-size: 20px;
        font-weight: bold;
        padding: 15px 30px;
        border-radius: 12px;
        border: none;
        width: 100%;
        margin: 10px 0;
    }
    .checkin-button:disabled {
        background: #cccccc;
        cursor: not-allowed;
    }
    .already-checked {
        background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
        padding: 15px;
        border-radius: 10px;
        color: white;
        text-align: center;
        font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)

    st.title("🏘️ Community Check-In Hub")
    st.caption("Woodlands Zone 6 - Fast & Easy Check-In")
    
    if not DB_CONNECTED:
        st.error("Database not connected")
        return

    activity = st.session_state.get('selected_activity', 'Cardio Drumming')
    acts = load_activities()
    act_config = next((a for a in acts if a['name'] == activity), None)
    s1_label = act_config.get('session_1_label', 'Session 1') if act_config else 'Session 1'
    s2_label = act_config.get('session_2_label', 'Session 2') if act_config else 'Session 2'
    has_s2 = bool(s2_label and s2_label.strip())

    st.subheader("📅 Select Session")
    if has_s2:
        session_option = st.radio("Which session?", ["Both", s1_label, s2_label], horizontal=True, key="kiosk_session")
        s1 = session_option in ["Both", s1_label]
        s2 = session_option in ["Both", s2_label]
    else:
        st.info(f"ℹ️ Only one session: {s1_label}")
        s1, s2 = True, False

    st.divider()

    # Toggle for showing/hiding participant names
    show_names = st.checkbox("👁️ Show participant names", value=True, key="show_names_toggle")
    
    # Hidden scanner input
    scanned_id = st.text_input("Scanner Input", key=f"scanner-input-{datetime.now().strftime('%Y%m%d%H%M')}", type="default", placeholder="Scan QR here...", label_visibility="collapsed")
    
    if scanned_id and len(scanned_id) > 5:
        process_checkin_by_id(scanned_id.strip(), selected_date, activity, s1, s2)
        st.rerun()

    # ── METHOD 1: Phone Search ─────────────────
    st.subheader(" Quick Check-In by Phone")
    phone_input = st.text_input("Enter 8-digit mobile number", placeholder="e.g., 91234567", key="checkin_phone")

    if phone_input and len(clean_phone_number(phone_input)) >= 8:
        clean_phone = clean_phone_number(phone_input)
        resident = find_participant_by_phone(clean_phone)

        if resident:
            #  CHECK IF ALREADY CHECKED IN
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
                        ✅ {resident['name']} already checked in today!<br>
                        No duplicate check-in allowed.
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    try:
                        att_count = supabase.table('attendance').select("*", count="exact") \
                            .eq('participant_id', resident['id']) \
                            .eq('source', activity) \
                            .execute().count
                    except:
                        att_count = 0
                    
                    st.markdown(f"""
                    <div class="checkin-card">
                        <h3 style="margin:0;">✅ {resident['name']}</h3>
                        <p style="margin:5px 0;">ID: {resident['id'][:12]}... | Attended {att_count}x for {activity}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if st.button("Confirm Check-In", type="primary", key=f"confirm_{resident['id']}", use_container_width=True):
                        process_checkin_by_id(resident['id'], selected_date, activity, s1, s2)
                        st.rerun()
            except Exception as e:
                st.error(f"Error checking attendance: {e}")
        else:
            st.warning("❓ Phone not found.")

    st.divider()

    # ── METHOD 2: Name Search ─────────────────
    if show_names:
        st.subheader("🔍 Find by Name")
        st.caption(f"Participants for **{activity}** - {selected_date.strftime('%d %b %Y')}")
        
        participants = st.session_state.get('participants', [])
        active_participants = [p for p in participants if p.get('active', True)]
        
        # 🔥 NEW: Toggle to show all participants or only activity attendees
        show_all = st.checkbox("👥 Show ALL participants (including newly registered)", value=False, key="show_all_participants")
        
        if not show_all:
            # Filter by activity attendance (existing behavior)
            try:
                att_data = supabase.table('attendance').select('participant_id').eq('source', activity).execute().data
                activity_attendees = {rec['participant_id'] for rec in att_data}
                active_participants = [p for p in active_participants if p['id'] in activity_attendees]
            except:
                pass
        
        # Search filter
        name_search = st.text_input("Type name to search...", key="checkin_name_search")
        
        if name_search:
            s = name_search.lower()
            active_participants = [p for p in active_participants if s in p['name'].lower()]
        
        # Display count
        st.caption(f" Showing {len(active_participants)} participant(s)")
        
        # 🔥 COLORFUL CARD DESIGN
        st.markdown("""
        <style>
        .participant-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 15px;
            padding: 20px;
            margin: 10px 0;
            color: white;
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        }
        .participant-card h3 {
            margin: 0 0 10px 0;
            font-size: 24px;
        }
        .participant-info {
            font-size: 14px;
            opacity: 0.9;
            margin: 5px 0;
        }
        .checkin-btn {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            color: white;
            border: none;
            padding: 15px 30px;
            border-radius: 10px;
            font-size: 18px;
            font-weight: bold;
            width: 100%;
            margin-top: 15px;
            cursor: pointer;
            box-shadow: 0 4px 10px rgba(0,0,0,0.2);
        }
        .checkin-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 15px rgba(0,0,0,0.3);
        }
        .already-checked {
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            padding: 15px;
            border-radius: 10px;
            text-align: center;
            font-weight: bold;
            margin-top: 15px;
        }
        </style>
        """, unsafe_allow_html=True)
        
        if active_participants:
            cols = st.columns(2)
            for i, p in enumerate(active_participants[:20]):
                with cols[i % 2]:
                    try:
                        att_count = supabase.table('attendance').select("*", count="exact") \
                            .eq('participant_id', p['id']) \
                            .eq('source', activity) \
                            .execute().count
                    except:
                        att_count = 0
                    
                    # Check if already checked in
                    try:
                        existing_check = supabase.table('attendance').select("*") \
                            .eq('participant_id', p['id']) \
                            .eq('date', str(selected_date)) \
                            .eq('source', activity) \
                            .execute()
                        already_checked = existing_check.data is not None and len(existing_check.data) > 0
                    except:
                        already_checked = False
                    
                    # Colorful card
                    st.markdown(f"""
                    <div class="participant-card">
                        <h3>{p['name']}</h3>
                        <div class="participant-info">
                             ID: {p['id'][:12]}...<br>
                            🔥 Attended {att_count}x for {activity}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if already_checked:
                        st.markdown('<div class="already-checked">✅ Already Checked In Today</div>', unsafe_allow_html=True)
                    else:
                        if st.button("Check In", key=f"btn_{p['id']}", use_container_width=True, type="primary"):
                            process_checkin_by_id(p['id'], selected_date, activity, s1, s2)
                            st.rerun()
        else:
            st.info("No participants found for this activity.")
    else:
        st.info("🔒 Participant names hidden. Use QR scanner or phone search.")

def process_checkin_by_id(pid, date, activity, s1, s2):
    """Core logic to mark attendance - prevents duplicates"""
    try:
        # 🔥 FIRST CHECK IF ALREADY EXISTS
        existing = supabase.table('attendance').select("*") \
            .eq('participant_id', pid).eq('date', str(date)).eq('source', activity).execute()
        
        if existing.data and len(existing.data) > 0:
            st.warning("⚠️ This person has already checked in today!")
            return
        
        res = supabase.table('participants').select("*").eq('id', pid).execute()
        if not res.data:
            st.error("Resident ID not found!")
            return
            
        resident = res.data[0]
        
        supabase.table('attendance').insert({
            "participant_id": pid,
            "name": resident['name'],
            "date": str(date),
            "session_1": s1,
            "session_2": s2,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "self_checkin": False,
            "source": activity
        }).execute()
        st.success(f"✅ Checked in {resident['name']}!")
        st.balloons()
    except Exception as e:
        st.error(f"Error: {e}")