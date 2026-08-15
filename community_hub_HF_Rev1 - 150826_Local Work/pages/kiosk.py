import streamlit as st
from datetime import datetime
from config import supabase, DB_CONNECTED, load_activities
from utils import clean_phone_number, find_participant_by_phone, mask_phone
from services import AttendanceService

def show_kiosk():
    st.set_page_config(layout="wide")
    st.markdown("""
    <style>
    .resident-card {
        background-color: #f8f9fa; border: 3px solid #dee2e6; padding: 20px;
        border-radius: 15px; text-align: center; margin: 10px 0; cursor: pointer; transition: all 0.2s;
    }
    .resident-card:hover { border-color: #4CAF50; background-color: #e8f5e9; }
    .resident-name { font-size: 28px; font-weight: bold; color: #1a1a1a; }
    .resident-id { font-size: 14px; color: #666; margin-top: 5px; }
    .session-badge { display: inline-block; padding: 5px 15px; border-radius: 20px; font-size: 14px; font-weight: bold; margin: 5px; }
    .badge-s1 { background-color: #4CAF50; color: white; }
    .badge-s2 { background-color: #2196F3; color: white; }
    .badge-both { background-color: #FF9800; color: white; }
    </style>
    """, unsafe_allow_html=True)
    st.title("🏘️ Woodlands Zone 6 - Check-In Kiosk")
    st.caption("Tap your name to check in - Simple & Easy!")
    if not DB_CONNECTED:
        st.error("Database not connected")
        return

    acts = load_activities()
    act_names = [a['name'] for a in acts] if acts else ["General Check-In"]
    selected_activity = st.selectbox("🎯 Select Activity", act_names, key="kiosk_activity")
    act_config = next((a for a in acts if a['name'] == selected_activity), None)

    # 🔥 Dynamic sessions (1-4)
    session_labels = []
    if act_config:
        for i in range(1, 5):
            lbl = (act_config.get(f'session_{i}_label') or '').strip()
            if lbl:
                session_labels.append(lbl)
    if not session_labels:
        session_labels = ['Session 1']

    st.divider()
    st.subheader("📅 Select Session")
    if len(session_labels) == 1:
        st.info(f"ℹ️ This activity has only one session: {session_labels[0]}")
        flags = [True]
        session_option = session_labels[0]
    else:
        options = ["All Sessions"] + session_labels
        session_option = st.radio("Which session are you attending?", options, horizontal=True, key="kiosk_session_select")
        flags = [(session_option == "All Sessions") or (session_option == lbl) for lbl in session_labels]

    flags = (flags + [False, False, False, False])[:4]
    s1, s2, s3, s4 = flags

    today = datetime.now().strftime("%Y-%m-%d")
    st.divider()

    st.subheader("📱 Quick Check-In by Phone")
    phone_input = st.text_input("Enter your 8-digit mobile number", placeholder="e.g., 91234567", key="kiosk_phone")

    if phone_input and len(clean_phone_number(phone_input)) >= 8:
        clean_phone = clean_phone_number(phone_input)
        resident = find_participant_by_phone(clean_phone)
        if resident:
            st.markdown(f"""
            <div class="resident-card" style="border-color: #4CAF50; background-color: #e8f5e9;">
                <div class="resident-name">✅ {resident['name']}</div>
                <div class="resident-id">ID: {resident['id'][:10]}... | 📞 {mask_phone(clean_phone)}</div>
            </div>
            """, unsafe_allow_html=True)
            try:
                existing_att = supabase.table('attendance').select("*") \
                    .eq('participant_id', resident['id']) \
                    .eq('date', today) \
                    .eq('source', selected_activity) \
                    .execute()
                already_checked_in = False
                if existing_att.data:
                    rec = existing_att.data[0]
                    done_flags = [rec.get(f'session_{i+1}', False) for i in range(4)]
                    if all(f for f, sel in zip(done_flags, [s1, s2, s3, s4]) if sel):
                        already_checked_in = True
                    status_badges = []
                    badge_cls = ["badge-s1", "badge-s2", "badge-both", "badge-s1"]
                    for i, lbl in enumerate(session_labels):
                        if rec.get(f'session_{i+1}', False):
                            status_badges.append(f'<span class="session-badge {badge_cls[i % 4]}">✓ {lbl}</span>')
                    st.markdown(f"""
                    <div style="background: #fff3cd; padding: 10px; border-radius: 8px; margin: 10px 0; text-align: center;">
                        <strong>⚠️ Already checked in today:</strong><br>
                        {' '.join(status_badges)}
                    </div>
                    """, unsafe_allow_html=True)
            except Exception:
                already_checked_in = False

            col1, col2, col3 = st.columns(3)
            with col1:
                checkin_text = "Update Check-In" if not already_checked_in else "✅ Checked In"
                if st.button(checkin_text, key="kiosk_checkin_yes", use_container_width=True, type="primary"):
                    success, message, _ = AttendanceService.process_checkin(resident['id'], today, selected_activity, s1, s2, s3, s4)
                if success:
                    st.success(f"Welcome {resident['name']}! Checked in for {session_option}")
                    # st.balloons()
                    st.rerun()
            with col2:
                if st.button("❌ Not Attending", key="kiosk_checkin_no", use_container_width=True):
                    st.info("Sorry you can't make it!")
            with col3:
                if st.button("🔄 Reset", key="kiosk_reset", use_container_width=True):
                    st.rerun()
        else:
            st.markdown(f"""
            <div style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; border-radius: 8px; margin: 10px 0;">
                <h4 style="margin:0; color:#1a1a1a;">❓ Phone number not found.</h4>
                <p style="margin:5px 0 0 0;">Please see a volunteer for assistance.</p>
            </div>
            """, unsafe_allow_html=True)

    st.divider()
    st.subheader("👥 Or Find Your Name Below")
    participants = st.session_state.get('participants', [])
    active_participants = [p for p in participants if p.get('active', True)]

    try:
        att_data = supabase.table('attendance').select('participant_id').eq('source', selected_activity).execute().data
        activity_attendees = set(rec['participant_id'] for rec in att_data)
        total_for_activity = len([p for p in active_participants if p['id'] in activity_attendees])
        st.info(f"📊 **Total Active Residents:** {len(active_participants)} | **Regulars for '{selected_activity}':** {total_for_activity}")
    except Exception:
        activity_attendees = set()
        st.info(f"📊 **Total Active Residents:** {len(active_participants)}")

    search = st.text_input("🔍 Type to filter names instantly...", placeholder="e.g., TAN, AHMAD, 9123", key="kiosk_search")
    if search:
        s = search.lower()
        filtered_participants = [p for p in active_participants if s in p['name'].lower() or s in p.get('contact', '')[-4:]]
    else:
        filtered_participants = active_participants[:50]
        if len(active_participants) > 50:
            st.caption("💡 Tip: Type a name or last 4 digits of phone number above to find someone specific without scrolling!")

    if filtered_participants:
        st.caption(f"Showing {len(filtered_participants)} resident(s)")
        cols = st.columns(2)
        for i, p in enumerate(filtered_participants):
            with cols[i % 2]:
                short_id = p['id'][:10] + "..."
                is_regular = p['id'] in activity_attendees if 'activity_attendees' in locals() else False
                badge = "⭐ Regular" if is_regular else "🆕 New / Occasional"
                st.markdown(f"""
                <div class="resident-card">
                    <div class="resident-name">{p['name']}</div>
                    <div class="resident-id">{badge} | ID: {short_id}</div>
                </div>
                """, unsafe_allow_html=True)
                success, message, _ = AttendanceService.process_checkin(p['id'], today, selected_activity, s1, s2, s3, s4)
                if success:
                    st.success(f"Welcome {p['name']}! Checked in for {session_option}")
                    # st.balloons()
                    st.rerun()
        st.info("No residents found matching your search. Please see a volunteer.")

    st.divider()
    st.caption("Need help? Please ask our volunteers at the counter.")

def mark_kiosk_attendance(pid, name, date, activity, s1=True, s2=False, s3=False, s4=False):
    """Mark attendance from kiosk mode with S1-S4 update logic."""
    try:
        selected = [s1, s2, s3, s4]
        existing = supabase.table('attendance').select("*") \
            .eq('participant_id', pid).eq('date', date).eq('source', activity).execute()
        if existing.data:
            record = existing.data[0]
            missing = [i + 1 for i, f in enumerate(selected) if f and not record.get(f'session_{i + 1}', False)]
            if not missing:
                st.info(f"ℹ️ {name} is already checked in for the selected session(s)")
                return
            updates = {"timestamp": datetime.now().isoformat()}
            for n in missing:
                updates[f'session_{n}'] = True
            current_activities = record.get('activities') or []
            if activity not in current_activities:
                current_activities.append(activity)
            updates['activities'] = current_activities
            supabase.table('attendance').update(updates).eq('id', record['id']).execute()
            st.success(f"✅ Updated attendance for {name}!")
        else:
            supabase.table('attendance').insert({
                "participant_id": pid, "name": name, "date": date,
                "session_1": s1, "session_2": s2, "session_3": s3, "session_4": s4,
                "timestamp": datetime.now().isoformat(),
                "self_checkin": False, "source": activity,
                "activities": [activity]
            }).execute()
            st.success(f"✅ Check-in successful for {name}!")
    except Exception as e:
        st.error(f"Error: {e}")