import streamlit as st
from datetime import datetime, timezone
from config import supabase, DB_CONNECTED
from utils import check_and_convert_status

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
            
            # Initialize with set to prevent duplicates
            if pid not in attendees:
                attendees[pid] = {'sessions': set()}
            
            # Add sessions (set automatically deduplicates)
            if record.get('session_1'):
                attendees[pid]['sessions'].add('Session 1')
            if record.get('session_2'):
                attendees[pid]['sessions'].add('Session 2')
        
        # Convert sets to sorted lists for clean display
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
    
    # Remove duplicates by ID (safety check)
    seen_ids = set()
    unique_participants = []
    for p in participants:  # FIXED: "p i n" → "p in"
        if p['id'] not in seen_ids:
            seen_ids.add(p['id'])
            unique_participants.append(p)
    participants = unique_participants
    
    # Get today's attendees for highlighting
    today_attendees = get_today_attendees(selected_date)
    
    # Mobile-friendly filters
    with st.container():  # FIXED: "wi th" → "with"
        search = st.text_input("🔍 Search name or phone", placeholder="Type name or phone number...")
        filter_type = st.selectbox("Filter View", 
                                   ["All", "New Only", "Regular Only", "Unsigned Indemnity"],
                                   label_visibility="collapsed")
    
    # Stats in mobile-friendly columns
    active_count = len([p for p in participants if p.get('active', True)])
    attended_count = len(today_attendees)
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Active", active_count)
    col2.metric("Attended Today", attended_count)
    col3.metric("Date", selected_date.strftime("%d %b"))
    
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

    # ============== AUTO-SAVE CHECKBOXES WITH HIGHLIGHTING ==============
    for idx, p in enumerate(filtered):
        pid = p['id']
        attend_count = counts.get(pid, 0)
        phone = p.get('contact', 'No phone')
        
        # Check if this participant attended today
        attended_info = today_attendees.get(pid)
        is_attended_today = attended_info is not None
        
        with st.container():
            # ============== HIGHLIGHT IF ATTENDED TODAY ==============
            if is_attended_today:
                # Get unique sessions (no duplicates)
                sessions = list(set(attended_info['sessions']))
                sessions.sort()  # Sort sessions chronologically
    
                # Format properly (no duplicates)
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
            
            # Header with name and phone
            status = "🟢" if p.get('indemnity') else "🔴"
            badge = "🆕" if p.get('is_new') else "⭐"
            
            # Name on one line, phone below
            st.write(f"### {status} {badge} {p['name']}")
            st.caption(f"📞 {phone}")
            
            if p.get('is_new') and attend_count > 0:
                st.progress(min(attend_count/3, 1.0), text=f"{attend_count}/3 to Regular")
            
            # ============== SESSION 1 CHECKBOX - AUTO-SAVE ==============
            s1_key = f"tab1_s1_{pid}_{idx}"
            s1_checked = st.checkbox("Session 1", key=s1_key)
            
            if s1_checked and not st.session_state.get(f"s1_saved_{pid}_{selected_date}", False):
                try:
                    record = {
                        "participant_id": pid,
                        "name": p['name'],
                        "date": str(selected_date),
                        "session_1": True,
                        "session_2": False,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "self_checkin": False
                    }
                    result = supabase.table('attendance').insert(record).execute()
                    
                    # Mark as saved to prevent duplicate
                    st.session_state[f"s1_saved_{pid}_{selected_date}"] = True
                    
                    # Update attendance count
                    counts[pid] = counts.get(pid, 0) + 1
                    st.session_state.attendance_counts = counts
                    
                    # Refresh today's attendees to show highlight
                    today_attendees = get_today_attendees(selected_date)
                    
                    # Check for status conversion
                    msg = check_and_convert_status(pid, p['name'])  # FIXED: "p[' name']" → "p['name']"
                    if msg:
                        st.success(f"✅ {msg}")
                    else:
                        st.success(f"✅ Session 1 saved for {p['name']}!")
                        
                except Exception as e:
                    st.error(f"❌ Error saving: {e}")
            
            st.markdown("##")  # Spacer
            
            # ============== SESSION 2 CHECKBOX - AUTO-SAVE ==============
            s2_key = f"tab1_s2_{pid}_{idx}"
            s2_checked = st.checkbox("Session 2", key=s2_key)
            
            if s2_checked and not st.session_state.get(f"s2_saved_{pid}_{selected_date}", False):
                try:
                    # Check if Session 1 already exists today
                    existing = supabase.table('attendance')\
                        .select("*")\
                        .eq('participant_id', pid)\
                        .eq('date', str(selected_date))\
                        .execute()

                    if existing.data:
                        # UPDATE existing record
                        supabase.table('attendance')\
                            .update({"session_2": True})\
                            .eq('id', existing.data[0]['id'])\
                            .execute()
                    else:
                        # INSERT new record
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
                    
                    # Mark as saved to prevent duplicate
                    st.session_state[f"s2_saved_{pid}_{selected_date}"] = True
                    
                    # Update attendance count (only if new record created)
                    if not existing.data:
                        counts[pid] = counts.get(pid, 0) + 1
                        st.session_state.attendance_counts = counts
                    
                    # Refresh today's attendees to show highlight
                    today_attendees = get_today_attendees(selected_date)
                    
                    # Check for status conversion
                    msg = check_and_convert_status(pid, p['name'])
                    if msg:
                        st.success(f"✅ {msg}")
                    else:
                        st.success(f"✅ Session 2 saved for {p['name']}!")
                        
                except Exception as e:
                    st.error(f"❌ Error saving: {e}")
            
            st.divider()