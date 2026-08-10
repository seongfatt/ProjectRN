import streamlit as st
from datetime import datetime, timezone
from config import supabase, DB_CONNECTED
from utils import check_and_convert_status, mask_phone  # Import mask_phone

def get_today_attendees(selected_date):
    """Get dictionary of participants who attended today with deduplicated sessions"""
    try:
        result = supabase.table('attendance')\
            .select('*')\
            .eq('date', str(selected_date))\
            .execute()
        
        attendees = {}
        for record in result.data:
            pid = record['participant_id']
            
            if pid not in attendees:
                attendees[pid] = {'sessions': set()}
            
            if record.get('session_1'):
                attendees[pid]['sessions'].add('Session 1')
            if record.get('session_2'):
                attendees[pid]['sessions'].add('Session 2')
        
        for pid in attendees:
            attendees[pid]['sessions'] = sorted(list(attendees[pid]['sessions']))
        
        return attendees
    except Exception as e:
        st.error(f"Error loading today's attendance: {e}")
        return {}

def show_tab1(selected_date):
    st.header("📝 Mark Attendance")
    
    participants = st.session_state.participants
    counts = st.session_state.attendance_counts
    
    # Remove duplicates by ID
    seen_ids = set()
    unique_participants = []
    for p in participants:
        if p['id'] not in seen_ids:
            seen_ids.add(p['id'])
            unique_participants.append(p)
    participants = unique_participants
    
    # Get today's attendees for highlighting
    today_attendees = get_today_attendees(selected_date)
    
    # Mobile-friendly filters
    with st.container():
        search = st.text_input("🔍 Search name or last 4 digits", placeholder="Type name or last 4 digits...")
        filter_type = st.selectbox("Filter View", 
                                   ["All", "New Only", "Regular Only", "Unsigned Indemnity"],
                                   label_visibility="collapsed")
    
    # Stats
    active_count = len([p for p in participants if p.get('active', True)])
    attended_count = len(today_attendees)
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Active", active_count)
    col2.metric("Attended Today", attended_count)
    col3.metric("Date", selected_date.strftime("%d %b"))
    
    # Apply filters (include masked phone in search)
    filtered = [p for p in participants if p.get('active', True)]
    if search:
        search_lower = search.lower()
        filtered = [p for p in filtered if 
                   search_lower in p['name'].lower() or 
                   search_lower in p.get('contact', '')[-4:]]  # Search last 4 digits
    
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

    # Display participants with masked phone numbers
    for idx, p in enumerate(filtered):
        pid = p['id']
        attend_count = counts.get(pid, 0)
        phone = p.get('contact', 'No phone')
        masked_phone = mask_phone(phone)  # PDPA compliant
        
        attended_info = today_attendees.get(pid)
        is_attended_today = attended_info is not None
        
        with st.container():
            # Highlight if attended today
            if is_attended_today:
                sessions = list(set(attended_info['sessions']))
                sessions.sort()
                sessions_str = ", ".join(sessions)
                
                st.markdown(f"""
                <div style='
                    background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%);
                    border-left: 5px solid #28a745;
                    padding: 12px;
                    border-radius: 8px;
                    margin-bottom: 10px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                '>
                    <strong style='color: #155724; font-size: 16px;'>🎉 ATTENDED TODAY: {sessions_str}</strong>
                </div>
                """, unsafe_allow_html=True)
            
            # Header with name and masked phone
            status = "🟢" if p.get('indemnity') else "🔴"
            badge = "🆕" if p.get('is_new') else "⭐"
            
            st.write(f"### {status} {badge} {p['name']}")
            masked_phone = mask_phone(p.get('contact', 'No phone'))
            st.caption(f"📞 {masked_phone}")  # PDPA compliant display
            
            if p.get('is_new') and attend_count > 0:
                st.progress(min(attend_count/3, 1.0), text=f"{attend_count}/3 to Regular")
            
            # Session 1 checkbox
            s1_key = f"tab1_s1_{pid}_{idx}"
            s1_checked = st.checkbox("Session 1", key=s1_key)
            
            if s1_checked and not st.session_state.get(f"s1_saved_{pid}_{selected_date}", False):
                try:
                    existing = supabase.table('attendance')\
                        .select("*")\
                        .eq('participant_id', pid)\
                        .eq('date', str(selected_date))\
                        .execute()
                    
                    if existing.data:
                        supabase.table('attendance')\
                            .update({"session_1": True})\
                            .eq('id', existing.data[0]['id'])\
                            .execute()
                    else:
                        record = {
                            "participant_id": pid,
                            "name": p['name'],
                            "date": str(selected_date),
                            "session_1": True,
                            "session_2": False,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "self_checkin": False
                        }
                        supabase.table('attendance').insert(record).execute()
                    
                    st.session_state[f"s1_saved_{pid}_{selected_date}"] = True
                    
                    if not existing.data:
                        counts[pid] = counts.get(pid, 0) + 1
                        st.session_state.attendance_counts = counts
                    
                    today_attendees = get_today_attendees(selected_date)
                    
                    msg = check_and_convert_status(pid, p['name'])
                    if msg:
                        st.success(f"✅ {msg}")
                    else:
                        st.success(f"✅ Session 1 saved for {p['name']}!")
                        
                except Exception as e:
                    st.error(f"❌ Error saving: {e}")
            
            st.markdown("##")
            
            # Session 2 checkbox
            s2_key = f"tab1_s2_{pid}_{idx}"
            s2_checked = st.checkbox("Session 2", key=s2_key)
            
            if s2_checked and not st.session_state.get(f"s2_saved_{pid}_{selected_date}", False):
                try:
                    existing = supabase.table('attendance')\
                        .select("*")\
                        .eq('participant_id', pid)\
                        .eq('date', str(selected_date))\
                        .execute()

                    if existing.data:
                        supabase.table('attendance')\
                            .update({"session_2": True})\
                            .eq('id', existing.data[0]['id'])\
                            .execute()
                    else:
                        record = {
                            "participant_id": pid,
                            "name": p['name'],
                            "date": str(selected_date),
                            "session_1": False,
                            "session_2": True,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "self_checkin": False
                        }
                        supabase.table('attendance').insert(record).execute()
                    
                    st.session_state[f"s2_saved_{pid}_{selected_date}"] = True
                    
                    if not existing.data:
                        counts[pid] = counts.get(pid, 0) + 1
                        st.session_state.attendance_counts = counts
                    
                    today_attendees = get_today_attendees(selected_date)
                    
                    msg = check_and_convert_status(pid, p['name'])
                    if msg:
                        st.success(f"✅ {msg}")
                    else:
                        st.success(f"✅ Session 2 saved for {p['name']}!")
                        
                except Exception as e:
                    st.error(f"❌ Error saving: {e}")
            
            st.divider()