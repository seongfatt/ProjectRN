import streamlit as st
from datetime import datetime, timezone
from config import supabase, DB_CONNECTED, load_activities
from utils import verify_token

def show_admin_scan(selected_date):
    st.header("Check-In Scanner")

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
    st.caption("Type resident ID or Name if QR scan doesn't work")
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

    # 🔥 NEW: Activity Filter for Quick Select
    filter_by_activity = st.checkbox(f"🎯 Show only residents who attend '{activity}'", value=True, key="filter_by_act_quick")

    participants = st.session_state.participants
    search = st.text_input("Filter names", placeholder="Type to filter...", key="quick_search")

    # Start with active participants
    filtered = [p for p in participants if p.get('active', True)]
    
    # 🔥 Filter by activity history AND count attendance
    activity_counts = {}
    if filter_by_activity:
        try:
            att_data = supabase.table('attendance').select('participant_id').eq('source', activity).execute().data
            activity_attendees = set()
            for rec in att_data:
                pid = rec['participant_id']
                activity_attendees.add(pid)
                activity_counts[pid] = activity_counts.get(pid, 0) + 1
            
            filtered = [p for p in filtered if p['id'] in activity_attendees]
        except Exception:
            pass

    # Apply text search filter
    if search:
        s = search.lower()
        filtered = [p for p in filtered if s in p['name'].lower() or s in p.get('contact','')[-4:]]

    if not filtered:
        st.info("No residents found matching criteria")
    else:
        show_all = st.toggle("Show All Matching Residents", value=False, key="scan_show_all")
        display_filtered = filtered if show_all else filtered[:12]
        st.caption(f"Showing {len(display_filtered)} of {len(filtered)} residents {'(all)' if show_all else '(first 12 — toggle above to show all)'}")

        # 🚀 SPEED FIX: Fetch all attended IDs for THIS DATE/activity in ONE query
        attended_ids = set()
        try:
            att_data_today = supabase.table('attendance').select('participant_id') \
                .eq('date', str(selected_date)) \
                .eq('source', activity) \
                .execute().data
            attended_ids = {rec['participant_id'] for rec in att_data_today}
        except Exception:
            attended_ids = set()
            
        cols = st.columns(2)
        for i, p in enumerate(display_filtered):
            with cols[i % 2]:
                with st.container():
                    # 🔥 NEW: Show individual activity attendance count
                    attend_count = activity_counts.get(p['id'], 0)
                    if filter_by_activity and attend_count > 0:
                        count_text = f"🔥 Attended {attend_count}x"
                        count_color = "#11998e"
                    else:
                        count_text = "New to this activity"
                        count_color = "#666"

                    st.markdown(f"""
                    <div style='background:#f8f9fa;border:1px solid #dee2e6;padding:10px;border-radius:8px;margin-bottom:8px;text-align:center;'>
                        <div style='font-weight:bold;font-size:15px;color:#1a1a1a;'>{p['name']}</div>
                        <div style='font-size:11px;color:{count_color};margin-top:2px;font-weight:500;'>ID: {p['id'][:10]}... | {count_text}</div>
                    </div>
                    """, unsafe_allow_html=True)

                    already_done = p['id'] in attended_ids

                    if already_done:
                        st.success("✅ Done", icon="✅")
                    else:
                        if st.button(f"Mark Present", key=f"mark_{p['id']}", use_container_width=True, type="primary"):
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
        existing = supabase.table('attendance').select("*") \
            .eq('participant_id', pid) \
            .eq('date', str(selected_date)) \
            .eq('source', activity) \
            .execute()

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