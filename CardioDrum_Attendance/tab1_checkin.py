import streamlit as st
from datetime import datetime, timezone
from config import supabase, DB_CONNECTED
from utils import check_and_convert_status

def show_tab1(selected_date):
    st.header("📝 Mark Attendance")
    
    participants = st.session_state.participants
    counts = st.session_state.attendance_counts
    
    # Remove duplicates by ID (safety check)
    seen_ids = set()
    unique_participants = []
    for p in participants:
        if p['id'] not in seen_ids:
            seen_ids.add(p['id'])
            unique_participants.append(p)
    participants = unique_participants
    
    # Mobile-friendly filters
    with st.container():
        search = st.text_input("🔍 Search name or phone", placeholder="Type name or phone number...")
        filter_type = st.selectbox("Filter View", 
                                   ["All", "New Only", "Regular Only", "Unsigned Indemnity"],
                                   label_visibility="collapsed")
    
    # Stats in mobile-friendly columns
    active_count = len([p for p in participants if p.get('active', True)])
    col1, col2 = st.columns(2)
    col1.metric("Active", active_count)
    col2.metric("Date", selected_date.strftime("%d %b"))
    
    # Apply filters (include phone in search)
    filtered = [p for p in participants if p.get('active', True)]
    if search:
        search_lower = search.lower()
        filtered = [p for p in filtered if 
                   search_lower in p['name'].lower() or 
                   search_lower in p.get('contact', '')]
    if filter_type == "New Only":
        filtered = [p for p in filtered if p.get('is_new')]
    elif filter_type == "Regular Only":
        filtered = [p for p in filtered if not p.get('is_new')]
    elif filter_type == "Unsigned Indemnity":
        filtered = [p for p in filtered if not p.get('indemnity')]
    
    if not filtered:
        st.info("No participants found")
        return
    
    st.divider()

    # SINGLE LOOP - Mobile optimized with unique keys
    for idx, p in enumerate(filtered):
        pid = p['id']
        attend_count = counts.get(pid, 0)
        phone = p.get('contact', 'No phone')
        
        with st.container():
            # Header with name and phone
            status = "🟢" if p.get('indemnity') else "🔴"
            badge = "🆕" if p.get('is_new') else "⭐"
            
            # Name on one line, phone below
            st.write(f"### {status} {badge} {p['name']}")
            st.caption(f"📞 {phone}")  # Phone number displayed here
            
            if p.get('is_new') and attend_count > 0:
                st.progress(min(attend_count/3, 1.0), text=f"{attend_count}/3 to Regular")
            
            # Action buttons - UNIQUE KEYS with tab1_ prefix and idx
            c1, c2, c3 = st.columns([1, 1, 1])
            with c1:
                s1 = st.checkbox("Session 1", key=f"tab1_s1_{pid}_{idx}")
            with c2:
                s2 = st.checkbox("Session 2", key=f"tab1_s2_{pid}_{idx}")
            with c3:
                if st.button("✓ Confirm", key=f"tab1_btn_{pid}_{idx}", type="primary", use_container_width=True):
                    try:
                        record = {
                            "participant_id": pid,
                            "name": p['name'],
                            "date": str(selected_date),
                            "session_1": s1,
                            "session_2": s2,
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        }
                        supabase.table('attendance').insert(record).execute()
                        
                        counts[pid] = counts.get(pid, 0) + 1
                        st.session_state.attendance_counts = counts
                        
                        msg = check_and_convert_status(pid, p['name'])
                        if msg:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.success(f"✓ {p['name']} recorded!")
                            
                    except Exception as e:
                        st.error(f"Error: {e}")
            
            st.divider()