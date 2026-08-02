import streamlit as st
from datetime import datetime, timezone
from config import supabase, DB_CONNECTED, load_activities
from utils import clean_phone_number, find_participant_by_phone, mask_phone

def show_checkin(selected_date):
    """
    McDONALD'S-STYLE KIOSK INTERFACE
    Fixed version - no broken HTML, uses proper Streamlit components
    """
    
    # Commercial kiosk CSS
    st.markdown("""
    <style>
    .kiosk-header {
        text-align: center;
        padding: 30px 0;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 20px;
        margin-bottom: 30px;
    }
    .kiosk-header h1 {
        font-size: 48px;
        font-weight: 800;
        margin: 0;
    }
    .kiosk-header p {
        font-size: 18px;
        margin: 10px 0 0 0;
        opacity: 0.9;
    }
    
    .resident-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
        gap: 15px;
        margin: 20px 0;
    }
    
    .resident-card {
        background: white;
        border: 3px solid #e0e0e0;
        border-radius: 15px;
        padding: 20px;
        text-align: center;
        transition: all 0.3s ease;
    }
    .resident-card:hover {
        border-color: #667eea;
        transform: translateY(-3px);
        box-shadow: 0 6px 20px rgba(102, 126, 234, 0.2);
    }
    .resident-card.checked-in {
        border-color: #4CAF50;
        background: #f1f8e9;
    }
    .resident-card .name {
        font-size: 20px;
        font-weight: 700;
        color: #1a1a1a;
        margin: 0 0 8px 0;
    }
    .resident-card .meta {
        font-size: 12px;
        color: #666;
        margin: 5px 0;
    }
    .resident-card .status {
        font-size: 14px;
        font-weight: 600;
        margin-top: 10px;
        padding: 8px;
        border-radius: 8px;
    }
    .resident-card .status.checked {
        background: #4CAF50;
        color: white;
    }
    .resident-card .status.pending {
        background: #FF9800;
        color: white;
    }
    
    .phone-section {
        background: white;
        border: 3px solid #e0e0e0;
        border-radius: 20px;
        padding: 30px;
        margin: 20px 0;
        box-shadow: 0 4px 15px rgba(0,0,0,0.08);
    }
    
    .session-badge {
        display: inline-block;
        padding: 6px 15px;
        border-radius: 20px;
        font-size: 13px;
        font-weight: 600;
        margin: 5px;
    }
    .badge-s1 { background: #4CAF50; color: white; }
    .badge-s2 { background: #2196F3; color: white; }
    .badge-both { background: #FF9800; color: white; }
    
    @media (max-width: 768px) {
        .resident-grid {
            grid-template-columns: repeat(2, 1fr);
        }
    }
    @media (min-width: 769px) and (max-width: 1200px) {
        .resident-grid {
            grid-template-columns: repeat(4, 1fr);
        }
    }
    @media (min-width: 1201px) {
        .resident-grid {
            grid-template-columns: repeat(6, 1fr);
        }
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Header
    st.markdown("""
    <div class="kiosk-header">
        <h1>🏘️ Woodlands Zone 6</h1>
        <p>Community Check-In Kiosk - Simple & Easy!</p>
    </div>
    """, unsafe_allow_html=True)
    
    if not DB_CONNECTED:
        st.error("Database not connected")
        return
    
    # Get activity from top bar
    activity = st.session_state.get('selected_activity', 'Cardio Drumming')
    
    # Get session config
    acts = load_activities()
    act_config = next((a for a in acts if a['name'] == activity), None)
    s1_label = act_config.get('session_1_label', 'Session 1') if act_config else 'Session 1'
    s2_label = act_config.get('session_2_label', 'Session 2') if act_config else 'Session 2'
    has_s2 = bool(s2_label and s2_label.strip())
    
    # Session selection
    st.subheader("📅 Select Your Session")
    if has_s2:
        session_option = st.radio(
            "Which session are you attending?",
            ["Both Sessions", s1_label, s2_label],
            horizontal=True,
            key="kiosk_session_select"
        )
        s1 = session_option in ["Both Sessions", s1_label]
        s2 = session_option in ["Both Sessions", s2_label]
    else:
        st.info(f"ℹ️ This activity has only one session: {s1_label}")
        s1 = True
        s2 = False
        session_option = s1_label
    
    st.divider()
    
    # METHOD 1: Phone-First
    st.markdown('<div class="phone-section">', unsafe_allow_html=True)
    st.subheader("📱 Quick Check-In by Phone")
    st.caption("Enter your 8-digit mobile number to instantly find your profile")
    
    phone_input = st.text_input(
        "Mobile Number",
        placeholder="e.g., 91234567",
        key="checkin_phone",
        label_visibility="collapsed"
    )
    st.markdown('</div>', unsafe_allow_html=True)
    
    if phone_input and len(clean_phone_number(phone_input)) >= 8:
        clean_phone = clean_phone_number(phone_input)
        resident = find_participant_by_phone(clean_phone)
        
        if resident:
            # Check existing attendance
            try:
                existing_att = supabase.table('attendance').select("*") \
                    .eq('participant_id', resident['id']) \
                    .eq('date', str(selected_date)) \
                    .eq('source', activity) \
                    .execute()
                
                already_checked_in = False
                current_s1 = False
                current_s2 = False
                
                if existing_att.data:
                    already_checked_in = True
                    current_s1 = existing_att.data[0].get('session_1', False)
                    current_s2 = existing_att.data[0].get('session_2', False)
            except Exception:
                already_checked_in = False
            
            # Display resident card
            status_badges = []
            if current_s1:
                status_badges.append(f'<span class="session-badge badge-s1">✓ {s1_label}</span>')
            if current_s2:
                status_badges.append(f'<span class="session-badge badge-s2">✓ {s2_label}</span>')
            
            status_html = ' '.join(status_badges) if status_badges else '<span style="opacity:0.8;">Not checked in yet</span>'
            
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%); color: white; padding: 30px; border-radius: 20px; text-align: center; margin: 20px 0; box-shadow: 0 4px 15px rgba(76, 175, 80, 0.3);">
                <div style="font-size: 36px; font-weight: 800; margin: 0;">✅ {resident['name']}</div>
                <div style="font-size: 16px; margin: 10px 0 0 0; opacity: 0.9;">ID: {resident['id'][:10]}... | 📞 {mask_phone(clean_phone)}</div>
                <div style="margin-top: 15px;">{status_html}</div>
            </div>
            """, unsafe_allow_html=True)
            
            # Session selection buttons
            if has_s2:
                st.markdown("**Select Session to Mark:**")
                col_s1, col_s2, col_both = st.columns(3)
                
                with col_s1:
                    s1_disabled = current_s1
                    if st.button(f"✓ {s1_label}", key="checkin_s1", disabled=s1_disabled, use_container_width=True, type="primary"):
                        mark_attendance(resident['id'], resident['name'], str(selected_date), activity, s1=True, s2=False)
                        st.success(f"Marked {s1_label} for {resident['name']}!")
                        st.rerun()
                
                with col_s2:
                    s2_disabled = current_s2
                    if st.button(f"✓ {s2_label}", key="checkin_s2", disabled=s2_disabled, use_container_width=True, type="primary"):
                        mark_attendance(resident['id'], resident['name'], str(selected_date), activity, s1=False, s2=True)
                        st.success(f"Marked {s2_label} for {resident['name']}!")
                        st.rerun()
                
                with col_both:
                    both_disabled = (current_s1 and current_s2)
                    if st.button("✓ Both Sessions", key="checkin_both", disabled=both_disabled, use_container_width=True, type="primary"):
                        mark_attendance(resident['id'], resident['name'], str(selected_date), activity, s1=True, s2=True)
                        st.success(f"Marked Both Sessions for {resident['name']}!")
                        st.rerun()
            else:
                if st.button(f"✓ Mark {s1_label}", key="checkin_single", disabled=already_checked_in, use_container_width=True, type="primary"):
                    mark_attendance(resident['id'], resident['name'], str(selected_date), activity, s1=True, s2=False)
                    st.success(f"Marked attendance for {resident['name']}!")
                    st.rerun()
            
            if st.button("🔄 Reset / Search Another", key="checkin_reset", use_container_width=True):
                st.rerun()
        else:
            st.warning("❓ Phone number not found. Please see a volunteer for assistance.")
    
    st.divider()
    
    # METHOD 2: Quick Select Grid
    st.subheader("👥 Or Find Your Name Below")
    st.caption("Tap your name to check in - Large buttons for easy selection")
    
    # Filter by activity
    filter_by_activity = st.checkbox(f"🎯 Show only residents who attend '{activity}'", value=True, key="checkin_filter_act")
    
    participants = st.session_state.get('participants', [])
    active_participants = [p for p in participants if p.get('active', True)]
    
    # Calculate activity stats
    activity_counts = {}
    activity_attendees = set()
    if filter_by_activity:
        try:
            att_data = supabase.table('attendance').select('participant_id').eq('source', activity).execute().data
            for rec in att_data:
                pid = rec['participant_id']
                activity_attendees.add(pid)
                activity_counts[pid] = activity_counts.get(pid, 0) + 1
            active_participants = [p for p in active_participants if p['id'] in activity_attendees]
        except Exception:
            pass
    
    # Search filter
    search = st.text_input(
        "🔍 Type to filter names...",
        placeholder="e.g., TAN, 9123",
        key="checkin_search"
    )
    
    if search:
        s = search.lower()
        active_participants = [p for p in active_participants if s in p['name'].lower() or s in p.get('contact', '')[-4:]]
    
    # Stats bar
    total_shown = len(active_participants)
    st.caption(f"📊 Showing {total_shown} resident(s)")
    
    if not active_participants:
        st.info("No residents found matching criteria")
    else:
        # Get today's attendance
        attended_ids = set()
        attendance_details = {}
        try:
            att_today = supabase.table('attendance').select('participant_id', 'session_1', 'session_2') \
                .eq('date', str(selected_date)) \
                .eq('source', activity) \
                .execute().data
            for rec in att_today:
                pid = rec['participant_id']
                attended_ids.add(pid)
                attendance_details[pid] = {
                    's1': rec.get('session_1', False),
                    's2': rec.get('session_2', False)
                }
        except Exception:
            pass
        
        # FIXED: Use Streamlit columns instead of broken HTML grid
        # Calculate number of columns based on screen size (Streamlit max is 12)
        num_cols = 3  # Default for mobile
        if len(active_participants) > 20:
            num_cols = 4
        
        cols = st.columns(num_cols)
        
        for i, p in enumerate(active_participants[:50]):  # Limit to 50 for performance
            with cols[i % num_cols]:
                is_attended = p['id'] in attended_ids
                attend_count = activity_counts.get(p['id'], 0)
                
                # Determine status
                if is_attended:
                    card_class = "resident-card checked-in"
                    status_text = "✅ Checked In"
                    status_class = "status checked"
                    
                    # Show session badges
                    details = attendance_details.get(p['id'], {})
                    badges = []
                    if details.get('s1'):
                        badges.append(f'<span class="session-badge badge-s1">✓ {s1_label}</span>')
                    if details.get('s2'):
                        badges.append(f'<span class="session-badge badge-s2">✓ {s2_label}</span>')
                    badge_html = ' '.join(badges)
                else:
                    card_class = "resident-card"
                    status_text = " Not Checked In"
                    status_class = "status pending"
                    badge_html = ""
                
                st.markdown(f"""
                <div class="{card_class}">
                    <div class="name">{p['name']}</div>
                    <div class="meta">ID: {p['id'][:10]}... | 🔥 {attend_count}x</div>
                    <div class="{status_class}">{status_text}</div>
                    {badge_html}
                </div>
                """, unsafe_allow_html=True)
                
                if not is_attended:
                    if st.button(f"✓ Mark Present", key=f"checkin_{p['id']}", use_container_width=True, type="primary"):
                        mark_attendance(p['id'], p['name'], str(selected_date), activity, s1, s2)
                        st.success(f"Marked attendance for {p['name']}!")
                        st.rerun()
    
    st.divider()
    st.caption("Need help? Please ask our volunteers at the counter.")

def mark_attendance(pid, name, date, activity, s1=True, s2=False):
    """Smart attendance marking with S1→S2 update support"""
    try:
        existing = supabase.table('attendance').select("*") \
            .eq('participant_id', pid) \
            .eq('date', date) \
            .eq('source', activity) \
            .execute()
        
        if existing.data:
            record = existing.data[0]
            current_s1 = record.get('session_1', False)
            current_s2 = record.get('session_2', False)
            
            updates = {"timestamp": datetime.now(timezone.utc).isoformat()}
            if s1: updates["session_1"] = True
            if s2: updates["session_2"] = True
            
            if current_s1 != s1 or current_s2 != s2:
                supabase.table('attendance').update(updates).eq('id', record['id']).execute()
                return True
            else:
                return False
        else:
            supabase.table('attendance').insert({
                "participant_id": pid,
                "name": name,
                "date": date,
                "session_1": s1,
                "session_2": s2,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "self_checkin": False,
                "source": activity
            }).execute()
            return True
    except Exception as e:
        st.error(f"Error: {e}")
        return False