import streamlit as st
from datetime import datetime, timezone
from collections import defaultdict  # 🚀 Add this import
from config import supabase, DB_CONNECTED, load_activities
from utils import check_and_convert_status, mask_phone

@st.cache_data(ttl=300)
def get_today_attendees(selected_date, activity="Cardio Drumming"):
    try:
        r = supabase.table('attendance').select('*').eq('date', str(selected_date)).eq('source', activity).execute()
        a = {}
        for rec in r.data:
            pid = rec['participant_id']
            if pid not in a: a[pid] = {'sessions': set()}
            if rec.get('session_1'): a[pid]['sessions'].add('S1')
            if rec.get('session_2'): a[pid]['sessions'].add('S2')
        for pid in a: a[pid]['sessions'] = sorted(list(a[pid]['sessions']))
        return a
    except:
        return {}

def show_checkin(selected_date):
    st.header("Mark Attendance")
    activity = st.session_state.get('selected_activity', 'Cardio Drumming')
    acts = load_activities()
    act_data = next((a for a in acts if a['name'] == activity), None)
    s1_label = act_data['session_1_label'] if act_data else "Session 1"
    s2_label = act_data['session_2_label'] if act_data else "Session 2"

    st.info(f"Activity: {activity}")

    participants = st.session_state.participants
    seen = set()
    participants = [p for p in participants if not (p['id'] in seen or seen.add(p['id']))]

    today_attendees = get_today_attendees(selected_date, activity)

    # 🚀 SPEED FIX: Pre-calculate total lifetime attendance for ALL residents in ONE query
    # This prevents the app from querying the database 20+ times inside the loop below!
    total_lifetime_attendance = defaultdict(int)
    try:
        all_att_records = supabase.table('attendance').select('participant_id').execute().data
        for rec in all_att_records:
            total_lifetime_attendance[rec['participant_id']] += 1
    except Exception:
        pass

    search = st.text_input("Search name or last 4 digits", placeholder="Type name or last 4 digits...")
    filter_type = st.selectbox("Filter", ["All", "New Only", "Regular Only", "Unsigned Indemnity"], label_visibility="collapsed")

    active = [p for p in participants if p.get('active', True)]
    if search:
        s = search.lower()
        active = [p for p in active if s in p['name'].lower() or s in p.get('contact','')[-4:]]
    if filter_type == "New Only": active = [p for p in active if p.get('is_new')]
    elif filter_type == "Regular Only": active = [p for p in active if not p.get('is_new')]
    elif filter_type == "Unsigned Indemnity": active = [p for p in active if not p.get('indemnity')]

    col1, col2, col3 = st.columns(3)
    col1.metric("Active", len(active))
    col2.metric("Attended Today", len(today_attendees))
    col3.metric("Date", selected_date.strftime("%d %b"))

    if not active: st.info("No participants found"); return
    st.divider()

    for idx, p in enumerate(active):
        pid = p['id']
        attended = today_attendees.get(pid)
        is_attended = attended is not None

        # Mobile-friendly card container
        card_bg = "linear-gradient(135deg,#d4edda,#c3e6cb)" if is_attended else "#f8f9fa"
        border_color = "#28a745" if is_attended else "#dee2e6"

        st.markdown(f"""
        <div style='background:{card_bg};border-left:5px solid {border_color};padding:12px;border-radius:10px;margin-bottom:10px;box-shadow:0 2px 4px rgba(0,0,0,0.1);'>
            <div style='display:flex;align-items:center;gap:8px;margin-bottom:4px;'>
                <span style='font-size:18px;'>{"🟢" if p.get('indemnity') else "🔴"}</span>
                <span style='font-size:18px;'>{"🆕" if p.get('is_new') else "⭐"}</span>
                <strong style='font-size:16px;color:#1a1a1a;'>{p['name']}</strong>
            </div>
            {"<div style='color:#155724;font-weight:bold;font-size:13px;margin-top:4px;'>✅ ATTENDED: " + ", ".join(attended['sessions']) + "</div>" if is_attended else ""}
            <div style='color:#666;font-size:12px;margin-top:4px;'>📞 {mask_phone(p.get('contact','No phone'))}</div>
        </div>
        """, unsafe_allow_html=True)

        if p.get('is_new'):
            # 🚀 SPEED FIX: Use pre-calculated dictionary instead of querying DB
            c = total_lifetime_attendance.get(pid, 0)
            if c > 0: 
                st.progress(min(c/3, 1.0), text=f"{c}/3 to Regular")
                st.caption("New resident — 3 attendances to become Regular")

        # Session buttons instead of checkboxes for better mobile UX
        s1_key = f"s1_{pid}_{idx}_{activity}"
        s2_key = f"s2_{pid}_{idx}_{activity}"

        # Use columns for side-by-side buttons on mobile
        btn_cols = st.columns(2)

        with btn_cols[0]:
            if not st.session_state.get(f"s1_saved_{pid}_{selected_date}_{activity}", False):
                if st.button(f"✅ {s1_label}", key=s1_key, use_container_width=True, type="secondary"):
                    try:
                        existing = supabase.table('attendance').select("*").eq('participant_id', pid).eq('date', str(selected_date)).eq('source', activity).execute()
                        if existing.data:
                            supabase.table('attendance').update({"session_1": True}).eq('id', existing.data[0]['id']).execute()
                        else:
                            supabase.table('attendance').insert({
                                "participant_id": pid, "name": p['name'], "date": str(selected_date),
                                "session_1": True, "session_2": False, "timestamp": datetime.now(timezone.utc).isoformat(),
                                "self_checkin": False, "source": activity
                            }).execute()
                        st.session_state[f"s1_saved_{pid}_{selected_date}_{activity}"] = True
                        msg = check_and_convert_status(pid, p['name'])
                        st.success(f"{msg}" if msg else f"{s1_label} saved!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
            else:
                st.button(f"✓ {s1_label}", key=s1_key, use_container_width=True, disabled=True)

        with btn_cols[1]:
            if not st.session_state.get(f"s2_saved_{pid}_{selected_date}_{activity}", False):
                if st.button(f"✅ {s2_label}", key=s2_key, use_container_width=True, type="secondary"):
                    try:
                        existing = supabase.table('attendance').select("*").eq('participant_id', pid).eq('date', str(selected_date)).eq('source', activity).execute()
                        if existing.data:
                            supabase.table('attendance').update({"session_2": True}).eq('id', existing.data[0]['id']).execute()
                        else:
                            supabase.table('attendance').insert({
                                "participant_id": pid, "name": p['name'], "date": str(selected_date),
                                "session_1": False, "session_2": True, "timestamp": datetime.now(timezone.utc).isoformat(),
                                "self_checkin": False, "source": activity
                            }).execute()
                        st.session_state[f"s2_saved_{pid}_{selected_date}_{activity}"] = True
                        msg = check_and_convert_status(pid, p['name'])
                        st.success(f"{msg}" if msg else f"{s2_label} saved!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
            else:
                st.button(f"✓ {s2_label}", key=s2_key, use_container_width=True, disabled=True)

        st.markdown("<div style='margin:8px 0;'></div>", unsafe_allow_html=True)

def get_attendance_count(pid):
    if not DB_CONNECTED: return 0
    try:
        return supabase.table('attendance').select('*', count='exact').eq('participant_id', pid).execute().count
    except: return 0
