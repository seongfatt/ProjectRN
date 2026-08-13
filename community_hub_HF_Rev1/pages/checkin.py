from email import message

import streamlit as st
from datetime import datetime, timezone
from config import supabase, DB_CONNECTED, load_activities, refresh_data
from utils import clean_phone_number, find_participant_by_phone, validate_checkin_time
try:
    from utils import sync_session_attendance_async
except ImportError:
    def sync_session_attendance_async(*args, **kwargs):
        pass
import urllib.parse
from services import AttendanceService

def show_checkin(selected_date):
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

    role = st.session_state.get('user_role', 'Unknown').upper()
    st.markdown(f"""
    <div class="volunteer-banner">
        🔐 Logged in as: {role} | All scans are recorded under this session.
    </div>
    """, unsafe_allow_html=True)

    if not DB_CONNECTED:
        st.error("Database not connected")
        return

    acts = load_activities()
    act_list = list(acts.values()) if isinstance(acts, dict) else acts
    activity = st.session_state.get('selected_activity', 'Cardio Drumming')

    ctx = f"{selected_date}|{activity}"
    if st.session_state.get('checkin_ctx') != ctx:
        st.session_state['checkin_ctx'] = ctx
        st.session_state['scan_banner'] = None

    act_config = next((a for a in act_list if a['name'] == activity), None)

    # 🔥 Dynamic session list (1 to 4 sessions)
    session_labels = []
    if act_config:
        for i in range(1, 5):
            lbl = (act_config.get(f'session_{i}_label') or '').strip()
            if lbl:
                session_labels.append(lbl)
    if not session_labels:
        session_labels = ['Session 1']

    st.subheader("🕐 Select Session")
    if len(session_labels) == 1:
        st.info(f"ℹ️ Only one session: {session_labels[0]}")
        flags = [True]
    else:
        options = ["All Sessions"] + session_labels
        choice = st.radio("Which session?", options, horizontal=True, key="kiosk_session")
        flags = [(choice == "All Sessions") or (choice == lbl) for lbl in session_labels]

    flags = (flags + [False, False, False, False])[:4]
    s1, s2, s3, s4 = flags

    def _fully_checked(rec):
        if not rec:
            return False
        for idx, f in enumerate([s1, s2, s3, s4], start=1):
            if f and not rec.get(f'session_{idx}', False):
                return False
        return True

    st.divider()

    # ── QR / ID SCANNER INPUT ──────────────────────────────────
    st.subheader("📱 Scan QR Code or Enter ID")
    st.caption("💡 Tip: If using a USB scanner, click the box below and scan. The system will auto-detect the ID.")

    if st.session_state.get('scan_banner'):
        btype, bmsg = st.session_state['scan_banner']
        if btype == 'success':
            st.success(bmsg)
        elif btype == 'info':
            st.info(bmsg)
        else:
            st.error(bmsg)

    if 'clear_scanner' not in st.session_state:
        st.session_state.clear_scanner = False
    if st.session_state.get('clear_scanner'):
        st.session_state['scanner_input_main'] = ""
        st.session_state.clear_scanner = False

    if 'processing_checkin' not in st.session_state:
        st.session_state.processing_checkin = False

    scanned_input = st.text_input(
        "Scan QR code or enter ID...",
        key="scanner_input_main",
        placeholder="e.g., 2026080316562190",
        label_visibility="collapsed"
    )

    if scanned_input and len(scanned_input.strip()) > 5 and not st.session_state.processing_checkin:
        input_text = scanned_input.strip()
        extracted_pid = None
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
            st.session_state.processing_checkin = True
            st.session_state['scan_banner'] = None
            success, message, _ = AttendanceService.process_checkin(extracted_pid, selected_date, activity, s1, s2, s3, s4)
            st.session_state['scan_banner'] = ('success', message) if success else ('error', message)
            st.session_state.processing_checkin = False
            if success:
                st.session_state.clear_scanner = True
                st.rerun()

    st.divider()

    # ── PHONE SEARCH ───────────────────────────────────────────
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
                rec = existing_check.data[0] if existing_check.data else None
                already_checked = _fully_checked(rec)

                if already_checked:
                    st.markdown(f"""
                    <div class="already-checked">
                        <h4 style="margin: 0; color: #0d47a1;">ℹ️ Already Checked In</h4>
                        <p style="margin: 5px 0 0 0;"><strong>{resident['name']}</strong> is already recorded for the selected session(s).</p>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    btn_label = "➕ Add Session & Check-In" if rec else "Confirm Check-In"
                    st.markdown(f"""
                    <div style="background: #e8f5e9; border: 2px solid #4CAF50; padding: 20px; border-radius: 15px; margin: 10px 0; color: #1a1a1a;">
                        <h3 style="margin:0;">✅ {resident['name']}</h3>
                        <p style="margin:5px 0 0 0; color:#666;">ID: {resident['id'][:12]}...</p>
                    </div>
                    """, unsafe_allow_html=True)
                    if st.button(btn_label, type="primary", key=f"confirm_{resident['id']}", use_container_width=True):
                        success, message, _ = AttendanceService.process_checkin(resident['id'], selected_date, activity, s1, s2, s3, s4)
                    if st.success:
                        st.rerun()
                        st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")
        else:
            st.warning("❓ Phone not found.")

    st.markdown('</div>', unsafe_allow_html=True)
    st.divider()

    # ── NAME LIST ────────
    show_names = st.checkbox("👁️ Show participant names", value=True, key="show_names_toggle")
    if show_names:
        st.subheader("🔍 Find by Name")
        participants = st.session_state.get('participants', [])
        active_participants = [p for p in participants if p.get('active', True)]

        try:
            att_data = supabase.table('attendance').select('participant_id').eq('source', activity).execute().data
            activity_attendees = {rec['participant_id'] for rec in att_data}
            active_participants.sort(key=lambda p: p['id'] in activity_attendees, reverse=True)
        except:
            activity_attendees = set()

        sort_az = st.checkbox("📋 Sort A–Z (Alphabetical)", value=False, key="sort_az_toggle")

        name_search = st.text_input("Type name to search...", key="checkin_name_search")
        if name_search:
            s = name_search.lower()
            active_participants = [p for p in active_participants if s in p['name'].lower()]
        else:
            if sort_az:
                active_participants.sort(key=lambda p: p['name'].lower())
            else:
                active_participants = active_participants[:20]

        st.caption(f"Showing {len(active_participants)} participant(s)")

        if active_participants:
            cols = st.columns(4)
            for i, p in enumerate(active_participants):
                with cols[i % 4]:
                    try:
                        existing_check = supabase.table('attendance').select("*") \
                            .eq('participant_id', p['id']) \
                            .eq('date', str(selected_date)) \
                            .eq('source', activity) \
                            .execute()
                        rec = existing_check.data[0] if existing_check.data else None
                    except:
                        rec = None

                    already_checked = _fully_checked(rec)
                    has_record = rec is not None

                    is_regular = p['id'] in activity_attendees
                    badge = "⭐ Regular" if is_regular else "🆕 New"

                    st.markdown(f"""
                    <div class="participant-card">
                        <h3>{p['name']}</h3>
                        <div class="participant-info">🆔 ID: {p['id'][:12]}... | {badge}</div>
                    </div>
                    """, unsafe_allow_html=True)

                    if already_checked:
                        st.markdown('<div class="already-checked" style="margin-top:5px; padding:10px;"><b>✅ Checked In</b></div>', unsafe_allow_html=True)
                    else:
                        btn_label = "➕ Add Session" if has_record else "Check In"
                        if st.button(btn_label, key=f"btn_{p['id']}", use_container_width=True, type="primary"):
                            success, message, _ = AttendanceService.process_checkin(p['id'], selected_date, activity, s1, s2, s3, s4)
                        if st.success:
                            st.rerun()
                            st.rerun()

def process_checkin_by_id(pid, date, activity, s1, s2, s3=False, s4=False):
    """Core logic: Time Validation + SESSION UPDATE (supports 1-4 sessions). Returns True/False."""
    try:
        selected = [s1, s2, s3, s4]

        if isinstance(date, str):
            if len(date) == 8 and date.isdigit():
                formatted_date = datetime.strptime(date, "%Y%m%d").strftime("%Y-%m-%d")
            else:
                formatted_date = date
        else:
            formatted_date = date.strftime("%Y-%m-%d")

        res = supabase.table('participants').select("*").eq('id', pid).execute()
        if not res.data:
            st.error(f"❌ Resident ID not found: {pid}")
            return False
        resident = res.data[0]

        existing = supabase.table('attendance').select("*") \
            .eq('participant_id', pid).eq('date', formatted_date).eq('source', activity).execute()

        if existing.data and len(existing.data) > 0:
            record = existing.data[0]
            missing = [i + 1 for i, f in enumerate(selected) if f and not record.get(f'session_{i + 1}', False)]

            if not missing:
                st.info(f"ℹ️ **{resident['name']}** is already fully checked in for {activity} today.")
                return False

            is_allowed, message = validate_checkin_time(activity, missing[0])
            if not is_allowed:
                st.error(message)
                st.info("💡 If this is incorrect, please contact the admin to adjust the session times or disable time validation.")
                return False

            updates = {"timestamp": datetime.now(timezone.utc).isoformat()}
            for n in missing:
                updates[f'session_{n}'] = True
            current_activities = record.get('activities') or []
            if activity not in current_activities:
                current_activities.append(activity)
            updates['activities'] = current_activities

            supabase.table('attendance').update(updates).eq('id', record['id']).execute()
            refresh_data()

            sync_session_attendance_async(pid, resident['name'], activity, formatted_date,
                                          st.session_state.get('user_role', 'system'))

            st.session_state['scan_banner'] = ('success', f"✅ Updated **{resident['name']}** with additional session(s)!")
            return True

        first_selected = next((i + 1 for i, f in enumerate(selected) if f), 1)
        is_allowed, message = validate_checkin_time(activity, first_selected)
        if not is_allowed:
            st.error(message)
            st.info("💡 If this is incorrect, please contact the admin to adjust the session times or disable time validation.")
            return False

        supabase.table('attendance').insert({
            "participant_id": pid, "name": resident['name'], "date": formatted_date,
            "session_1": s1, "session_2": s2, "session_3": s3, "session_4": s4,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "self_checkin": False, "source": activity,
            "activities": [activity]
        }).execute()
        refresh_data()

        sync_session_attendance_async(pid, resident['name'], activity, formatted_date,
                                      st.session_state.get('user_role', 'system'))

        st.session_state['scan_banner'] = ('success', f"✅ Successfully checked in **{resident['name']}**!")
        return True
    except Exception as e:
        if 'duplicate key' in str(e):
            st.info(f"ℹ️ Already checked in for **{activity}** today.")
        else:
            st.error(f"Error: {e}")
        return False