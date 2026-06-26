import streamlit as st
from datetime import datetime, timezone
from config import supabase, DB_CONNECTED, load_activities
from utils import verify_token

def show_admin_scan(selected_date):
    st.header("Admin QR Scanner")

    st.markdown("""
    <div style="background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); color: white; padding: 20px; border-radius: 10px; margin-bottom: 20px;">
        <h3 style="color: white; margin-top: 0;">How to Scan Resident QR</h3>
        <ol style="margin: 10px 0; padding-left: 20px;">
            <li>Resident shows their <strong>personal QR card</strong></li>
            <li>Admin scans with this page using <strong>phone camera or webcam</strong></li>
            <li>System auto-identifies resident and <strong>marks attendance</strong></li>
        </ol>
        <p style="margin-bottom: 0; font-size: 14px;">Residents who don't have smartphones can use printed QR cards!</p>
    </div>
    """, unsafe_allow_html=True)

    if not DB_CONNECTED:
        st.error("Database not connected"); return

    acts = load_activities()
    act_names = [a['name'] for a in acts]
    activity = st.selectbox("Activity", act_names, index=0, key="scan_act")

    # Dynamic session options based on activity config
    act_config = next((a for a in acts if a['name'] == activity), None)
    s1_label = act_config.get('session_1_label', 'Session 1') if act_config else 'Session 1'
    s2_label = act_config.get('session_2_label', 'Session 2') if act_config else 'Session 2'
    has_s2 = bool(s2_label and s2_label.strip())

    if has_s2:
        session_options = ["Both", s1_label, s2_label]
        session_option = st.radio("Session", session_options, horizontal=True, key="scan_session")
        s1 = session_option in ["Both", s1_label]
        s2 = session_option in ["Both", s2_label]
    else:
        st.info(f"This activity has only one session: {s1_label}")
        session_option = s1_label
        s1 = True
        s2 = False

    st.info(f"Scanning for: **{activity}** | Date: **{selected_date}** | Session: **{session_option}**")

    st.divider()

    st.subheader("Method 1: Camera Scan")
    st.caption("Use phone camera or webcam to scan resident's QR card")

    scanned_url = st.text_input("Paste scanned QR content (URL)", 
                                  placeholder="https://your-app.hf.space/?mode=auto&pid=...",
                                  key="scanned_url")

    if scanned_url and st.button("Process Scan & Mark Attendance", type="primary", use_container_width=True):
        process_scan(scanned_url, selected_date, activity, s1, s2)

    st.divider()

    st.subheader("Method 2: Manual ID Entry")
    st.caption("Type resident ID if QR scan doesn't work")

    col1, col2 = st.columns([2, 1])
    with col1:
        manual_id = st.text_input("Resident ID / Name", placeholder="e.g., 20260128143935 or ABDUL", key="manual_id")
    with col2:
        st.write(" "); st.write(" ")
        if st.button("Find & Mark", type="primary", use_container_width=True):
            process_manual_entry(manual_id, selected_date, activity, s1, s2)

    st.divider()

    st.subheader("Method 3: Quick Select")
    st.caption("Fastest for known regulars — just click name")

    participants = st.session_state.participants
    search = st.text_input("Filter names", placeholder="Type to filter...", key="quick_search")

    filtered = [p for p in participants if p.get('active', True)]
    if search:
        s = search.lower()
        filtered = [p for p in filtered if s in p['name'].lower() or s in p.get('contact','')[-4:]]

    if not filtered:
        st.info("No residents found")
        return

    # NEW: Show All toggle
    show_all = st.toggle("Show All Residents", value=False, key="scan_show_all")
    display_filtered = filtered if show_all else filtered[:12]
    st.caption(f"Showing {len(display_filtered)} of {len(filtered)} residents {'(all)' if show_all else '(first 12 — toggle above to show all)'}")

    cols = st.columns(3)
    for i, p in enumerate(display_filtered):
        with cols[i % 3]:
            with st.container():
                st.markdown(f"**{p['name']}**")
                st.caption(f"ID: {p['id'][:15]}...")

                try:
                    existing = supabase.table('attendance').select("*")                         .eq('participant_id', p['id'])                         .eq('date', str(selected_date))                         .eq('source', activity)                         .execute()
                    already_done = bool(existing.data)
                except:
                    already_done = False

                if already_done:
                    st.success("Done")
                else:
                    if st.button(f"Mark Present", key=f"mark_{p['id']}", use_container_width=True):
                        mark_attendance(p['id'], p['name'], selected_date, activity, s1, s2)
                        st.rerun()

def process_scan(scanned_url, selected_date, activity, s1, s2):
    try:
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(scanned_url)
        params = parse_qs(parsed.query)

        pid = params.get('pid', [None])[0]
        date_str = params.get('date', [None])[0]
        token = params.get('tk', [None])[0]

        if not pid or not token:
            st.error("Invalid QR code. Missing ID or token.")
            return

        if not verify_token(pid, date_str or datetime.now().strftime("%Y%m%d"), token):
            st.error("Invalid or expired QR code.")
            return

        try:
            p = supabase.table('participants').select("*").eq('id', pid).execute().data[0]
        except:
            st.error("Resident not found in database.")
            return

        mark_attendance(pid, p['name'], selected_date, activity, s1, s2)

    except Exception as e:
        st.error(f"Error processing scan: {e}")

def process_manual_entry(query, selected_date, activity, s1, s2):
    try:
        result = supabase.table('participants').select("*").eq('id', query).execute()

        if not result.data:
            all_p = supabase.table('participants').select("*").ilike('name', f'%{query}%').execute()
            if all_p.data and len(all_p.data) == 1:
                result = all_p
            elif all_p.data and len(all_p.data) > 1:
                st.warning(f"Found {len(all_p.data)} matches. Please be more specific.")
                for p in all_p.data[:5]:
                    st.write(f"- {p['name']} (ID: {p['id']})")
                return

        if not result.data:
            st.error("No resident found. Check ID or name.")
            return

        p = result.data[0]
        mark_attendance(p['id'], p['name'], selected_date, activity, s1, s2)

    except Exception as e:
        st.error(f"Error: {e}")

def mark_attendance(pid, name, selected_date, activity, s1, s2):
    try:
        existing = supabase.table('attendance').select("*")             .eq('participant_id', pid)             .eq('date', str(selected_date))             .eq('source', activity)             .execute()

        if existing.data:
            record = existing.data[0]
            updates = {"timestamp": datetime.now(timezone.utc).isoformat()}
            if s1: updates["session_1"] = True
            if s2: updates["session_2"] = True

            supabase.table('attendance').update(updates).eq('id', record['id']).execute()
            st.success(f"Updated attendance for {name}!")
        else:
            supabase.table('attendance').insert({
                "participant_id": pid,
                "name": name,
                "date": str(selected_date),
                "session_1": s1,
                "session_2": s2,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "self_checkin": False,
                "source": activity
            }).execute()
            st.success(f"Attendance marked for {name}!")
            st.balloons()

    except Exception as e:
        st.error(f"Error saving attendance: {e}")
