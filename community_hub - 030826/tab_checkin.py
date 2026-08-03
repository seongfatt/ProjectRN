import streamlit as st
from datetime import datetime, timezone
from config import supabase, DB_CONNECTED, load_activities, refresh_data
from utils import clean_phone_number, find_participant_by_phone
import urllib.parse

def show_checkin(selected_date):
    """
    UNIFIED SMART CHECK-IN HUB
    Includes USB Scanner Listener with URL Parsing
    """
    
    # 🔥 CSS FOR PROFESSIONAL DESIGN
    st.markdown("""
    <style>
    .participant-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 15px; padding: 20px; margin: 10px 0; color: white;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }
    .participant-card h3 { margin: 0 0 10px 0; font-size: 24px; }
    .participant-info { font-size: 14px; opacity: 0.9; margin: 5px 0; }
    .checkin-btn {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        color: white; border: none; padding: 15px 30px; border-radius: 10px;
        font-size: 18px; font-weight: bold; width: 100%; margin-top: 15px;
        cursor: pointer; box-shadow: 0 4px 10px rgba(0,0,0,0.2);
    }
    .checkin-btn:hover { transform: translateY(-2px); box-shadow: 0 6px 15px rgba(0,0,0,0.3); }
    .already-checked {
        background: #e3f2fd; border-left: 5px solid #2196f3;
        padding: 15px; border-radius: 8px; margin-top: 15px;
    }
    .phone-section {
        background: white; border: 3px solid #e0e0e0; border-radius: 20px;
        padding: 30px; margin: 20px 0; box-shadow: 0 4px 15px rgba(0,0,0,0.08);
    }
    </style>
    """, unsafe_allow_html=True)

    # 🔥 GLOBAL USB SCANNER LISTENER WITH URL PARSING
    st.markdown("""
    <script>
    let scanBuffer = '';
    let scanTimeout;
    document.addEventListener('keydown', function(e) {
        if (document.activeElement.tagName === 'INPUT' && !document.activeElement.id.includes('scanner-input')) {
            return; 
        }
        if (e.key === 'Enter') {
            if (scanBuffer.length > 5) {
                let scannerInput = document.getElementById('scanner-input');
                if (scannerInput) {
                    const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                    nativeInputValueSetter.call(scannerInput, scanBuffer);
                    scannerInput.dispatchEvent(new Event('input', { bubbles: true }));
                }
            }
            scanBuffer = '';
        } else if (e.key.length === 1) {
            scanBuffer += e.key;
            clearTimeout(scanTimeout);
            scanTimeout = setTimeout(() => { scanBuffer = ''; }, 100); 
        }
    });
    </script>
    """, unsafe_allow_html=True)

    st.title("🏘️ Community Check-In Hub")
    
    # 🔒 SHARED VOLUNTEER ACCOUNTABILITY
    role = st.session_state.get('user_role', 'Unknown').upper()
    st.markdown(f"""
    <div style="background: #fff3cd; padding: 10px; border-radius: 8px; text-align: center; margin-bottom: 20px;">
        <strong>🔐 Logged in as: {role}</strong> | All scans are recorded under this session.
    </div>
    """, unsafe_allow_html=True)
    
    st.caption("Woodlands Zone 6 - Fast & Easy Check-In")
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

    st.subheader(" Select Session")
    if has_s2:
        session_option = st.radio("Which session?", ["Both", s1_label, s2_label], horizontal=True, key="kiosk_session")
        s1 = session_option in ["Both", s1_label]
        s2 = session_option in ["Both", s2_label]
    else:
        st.info(f"ℹ️ Only one session: {s1_label}")
        s1, s2 = True, False

    st.divider()

    # 🔥 SMART SCANNER: Accepts both Direct ID and Full URL
    scanned_input = st.text_input(
        "📱 Scan QR Code (ID or URL)", 
        key=f"scanner-input-{datetime.now().strftime('%Y%m%d%H%M')}", 
        type="default", 
        placeholder="Scan QR code or enter ID...", 
        label_visibility="collapsed"
    )
    
    if scanned_input and len(scanned_input.strip()) > 5:
        # 🔥 SMART PARSER: Detect if it's a URL or direct ID
        input_text = scanned_input.strip()
        extracted_pid = None
        extracted_date = None
        extracted_act = None
        extracted_session = None
        
        if 'pid=' in input_text or input_text.startswith('http'):
            # It's a URL - extract parameters
            try:
                parsed_url = urllib.parse.urlparse(input_text)
                query_params = urllib.parse.parse_qs(parsed_url.query)
                
                extracted_pid = query_params.get('pid', [None])[0]
                extracted_date = query_params.get('date', [datetime.now().strftime("%Y%m%d")])[0]
                extracted_act = query_params.get('act', [activity])[0]
                extracted_session = query_params.get('session', ['both'])[0]
                
                if extracted_pid:
                    st.success(f"✅ Scanned QR Code - ID: {extracted_pid[:12]}...")
                    # Update activity if different
                    if extracted_act and extracted_act != activity:
                        st.info(f"📅 Activity from QR: {extracted_act}")
                        st.session_state.selected_activity = extracted_act
            except Exception as e:
                st.error(f"Error parsing URL: {e}")
        else:
            # It's a direct ID
            extracted_pid = input_text
            extracted_date = selected_date.strftime("%Y%m%d")
            extracted_act = activity
            extracted_session = 'both'
        
        # Process check-in if we have a valid ID
        if extracted_pid:
            process_checkin_by_id(
                extracted_pid, 
                extracted_date, 
                extracted_act or activity, 
                s1 if extracted_session in ['1', 'both'] else False,
                s2 if extracted_session in ['2', 'both'] else False
            )
            st.rerun()

    # ── METHOD 1: Phone Search ──────────────────
    st.markdown('<div class="phone-section">', unsafe_allow_html=True)
    st.subheader(" Quick Check-In by Phone")
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
                        <p style="margin: 5px 0 0 0; color: #1a1a1a;"><strong>{resident['name']}</strong> is already recorded for today's {activity}.</p>
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
                    <div style="background: #e8f5e9; border: 2px solid #4CAF50; padding: 20px; border-radius: 15px; margin: 10px 0;">
                        <h3 style="margin:0; color:#1a1a1a;">✅ {resident['name']}</h3>
                        <p style="margin:5px 0 0 0; color:#666;">ID: {resident['id'][:12]}... | Attended {att_count}x for {activity}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if st.button("Confirm Check-In", type="primary", key=f"confirm_{resident['id']}", use_container_width=True):
                        process_checkin_by_id(resident['id'], selected_date, activity, s1, s2)
                        st.rerun()
            except Exception as e:
                st.error(f"Error checking attendance: {e}")
        else:
            st.warning("❓ Phone not found.")
    st.markdown('</div>', unsafe_allow_html=True)

    st.divider()

    # ─ METHOD 2: Name Search ──────────────────
    show_names = st.checkbox("👁️ Show participant names", value=True, key="show_names_toggle")
    
    if show_names:
        st.subheader("🔍 Find by Name")
        st.caption(f"Participants for **{activity}** - {selected_date.strftime('%d %b %Y')}")
        
        participants = st.session_state.get('participants', [])
        active_participants = [p for p in participants if p.get('active', True)]
        
        show_all = st.checkbox(" Show ALL participants (including newly registered)", value=False, key="show_all_participants")
        
        if not show_all:
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
            cols = st.columns(2)
            for i, p in enumerate(active_participants[:50]):
                with cols[i % 2]:
                    try:
                        att_count = supabase.table('attendance').select("*", count="exact") \
                            .eq('participant_id', p['id']) \
                            .eq('source', activity) \
                            .execute().count
                    except:
                        att_count = 0
                    
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
                        <div class="participant-info">
                            🆔 ID: {p['id'][:12]}...<br>
                             Attended {att_count}x for {activity}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if already_checked:
                        st.markdown('<div class="already-checked"><h4 style="margin:0; color:#0d47a1;">ℹ️ Already Checked In</h4></div>', unsafe_allow_html=True)
                    else:
                        if st.button("Check In", key=f"btn_{p['id']}", use_container_width=True, type="primary"):
                            process_checkin_by_id(p['id'], selected_date, activity, s1, s2)
                            st.rerun()
        else:
            st.info("No participants found for this activity.")
    else:
        st.info("🔒 Participant names hidden. Use QR scanner or phone search.")

def process_checkin_by_id(pid, date, activity, s1, s2):
    """Core logic to mark attendance - prevents duplicates and forces instant refresh"""
    try:
        # Format date properly
        try:
            formatted_date = datetime.strptime(str(date), "%Y%m%d").strftime("%Y-%m-%d")
        except:
            formatted_date = str(date)
        
        # 1. CHECK IF ALREADY EXISTS TODAY
        existing = supabase.table('attendance').select("*") \
            .eq('participant_id', pid).eq('date', formatted_date).eq('source', activity).execute()
        
        if existing.data and len(existing.data) > 0:
            # Fetch name for the message
            res = supabase.table('participants').select("name").eq('id', pid).execute()
            name = res.data[0]['name'] if res.data else "Resident"
            st.info(f"ℹ️ **{name}** is already checked in today for {activity}. No action needed.")
            return
        
        # 2. FETCH RESIDENT DETAILS
        res = supabase.table('participants').select("*").eq('id', pid).execute()
        if not res.data:
            st.error(f" Resident ID not found: {pid}")
            return
            
        resident = res.data[0]
        
        # 3. INSERT ATTENDANCE
        supabase.table('attendance').insert({
            "participant_id": pid,
            "name": resident['name'],
            "date": formatted_date,
            "session_1": s1,
            "session_2": s2,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "self_checkin": False,
            "source": activity
        }).execute()
        
        # 🔥 4. FORCE INSTANT REFRESH OF SESSION STATE
        refresh_data()
        
        st.success(f"✅ Successfully checked in **{resident['name']}**!")
        st.rerun() # Instantly refresh the UI
        
    except Exception as e:
        error_msg = str(e)
        if 'duplicate key value' in error_msg or 'idx_attendance_unique' in error_msg:
            st.info("ℹ️ This person has already checked in today. (Duplicate prevented)")
        else:
            st.error(f"Error: {e}")