import streamlit as st
from datetime import datetime
from config import supabase, DB_CONNECTED, load_activities
from utils import clean_phone_number, find_participant_by_phone, mask_phone

def show_kiosk():
    """
    KIOSK MODE - Simple, tap-based interface for seniors
    Optimized for mobile/tablet use at venue
    NOW WITH INSTANT SEARCH & ACTIVITY TOTALS!
    """
    st.set_page_config(layout="wide")
    
    # Custom CSS for kiosk mode - BIG buttons, easy to tap
    st.markdown("""
    <style>
    .resident-card {
        background-color: #f8f9fa;
        border: 3px solid #dee2e6;
        padding: 20px;
        border-radius: 15px;
        text-align: center;
        margin: 10px 0;
        cursor: pointer;
        transition: all 0.2s;
    }
    .resident-card:hover {
        border-color: #4CAF50;
        background-color: #e8f5e9;
    }
    .resident-name {
        font-size: 28px;
        font-weight: bold;
        color: #1a1a1a;
    }
    .resident-id {
        font-size: 14px;
        color: #666;
        margin-top: 5px;
    }
    .session-badge {
        display: inline-block;
        padding: 5px 15px;
        border-radius: 20px;
        font-size: 14px;
        font-weight: bold;
        margin: 5px;
    }
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
    
    # 1. Select Activity
    acts = load_activities()
    act_names = [a['name'] for a in acts] if acts else ["General Check-In"]
    selected_activity = st.selectbox("🎯 Select Activity", act_names, key="kiosk_activity")
    
    # Get session labels for this activity
    act_config = next((a for a in acts if a['name'] == selected_activity), None)
    s1_label = act_config.get('session_1_label', 'Session 1') if act_config else 'Session 1'
    s2_label = act_config.get('session_2_label', 'Session 2') if act_config else 'Session 2'
    has_s2 = bool(s2_label and s2_label.strip())
    
    # 2. Session Selection
    st.divider()
    st.subheader("📅 Select Session")
    
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
    
    today = datetime.now().strftime("%Y-%m-%d")
    st.divider()
    
    # 3. Quick Check-In by Phone (Fastest)
    st.subheader("📱 Quick Check-In by Phone")
    phone_input = st.text_input(
        "Enter your 8-digit mobile number",
        placeholder="e.g., 91234567",
        key="kiosk_phone"
    )
    
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
            
            # Check existing attendance
            try:
                existing_att = supabase.table('attendance').select("*") \
                    .eq('participant_id', resident['id']) \
                    .eq('date', today) \
                    .eq('source', selected_activity) \
                    .execute()
                
                already_checked_in = False
                if existing_att.data:
                    already_checked_in = True
                    current_s1 = existing_att.data[0].get('session_1', False)
                    current_s2 = existing_att.data[0].get('session_2', False)
                    
                    status_badges = []
                    if current_s1: status_badges.append(f'<span class="session-badge badge-s1">✓ {s1_label}</span>')
                    if current_s2: status_badges.append(f'<span class="session-badge badge-s2">✓ {s2_label}</span>')
                    
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
                checkin_text = "Update Check-In" if already_checked_in else "✅ Check In"
                if st.button(checkin_text, key="kiosk_checkin_yes", use_container_width=True, type="primary"):
                    mark_kiosk_attendance(resident['id'], resident['name'], today, selected_activity, s1, s2)
                    st.success(f"Welcome {resident['name']}! Checked in for {session_option}")
                    st.balloons()
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
    
    # 4. Browse by Name with INSTANT SEARCH & TOTALS
    st.subheader("👥 Or Find Your Name Below")
    
    participants = st.session_state.get('participants', [])
    active_participants = [p for p in participants if p.get('active', True)]
    
    # 🔥 NEW: Calculate total participants for this activity
    try:
        att_data = supabase.table('attendance').select('participant_id').eq('source', selected_activity).execute().data
        activity_attendees = set(rec['participant_id'] for rec in att_data)
        total_for_activity = len([p for p in active_participants if p['id'] in activity_attendees])
        
        st.info(f"📊 **Total Active Residents:** {len(active_participants)} | **Regulars for '{selected_activity}':** {total_for_activity}")
    except Exception:
        total_for_activity = len(active_participants)
        st.info(f"📊 **Total Active Residents:** {len(active_participants)}")
    
    # 🔥 NEW: Prominent Search Filter to prevent scrolling
    search = st.text_input(
        "🔍 Type to filter names instantly...", 
        placeholder="e.g., TAN, AHMAD, 9123", 
        key="kiosk_search",
        help="Start typing to narrow down the list immediately!"
    )
    
    if search:
        s = search.lower()
        filtered_participants = [
            p for p in active_participants 
            if s in p['name'].lower() or s in p.get('contact', '')[-4:]
        ]
    else:
        # If no search, limit to top 50 to prevent lag, with a hint to search
        filtered_participants = active_participants[:50]
        if len(active_participants) > 50:
            st.caption("💡 Tip: Type a name or last 4 digits of phone number above to find someone specific without scrolling!")

    if filtered_participants:
        st.caption(f"Showing {len(filtered_participants)} resident(s)")
        cols = st.columns(2)
        for i, p in enumerate(filtered_participants):
            with cols[i % 2]:
                short_id = p['id'][:10] + "..."
                
                # Check if they are a regular for this activity
                is_regular = p['id'] in activity_attendees if 'activity_attendees' in locals() else False
                badge = "⭐ Regular" if is_regular else "🆕 New / Occasional"
                
                st.markdown(f"""
                <div class="resident-card">
                    <div class="resident-name">{p['name']}</div>
                    <div class="resident-id">{badge} | ID: {short_id}</div>
                </div>
                """, unsafe_allow_html=True)
                
                if st.button("✅ Check In", key=f"kiosk_name_{p['id']}", use_container_width=True, type="primary"):
                    mark_kiosk_attendance(p['id'], p['name'], today, selected_activity, s1, s2)
                    st.success(f"Welcome {p['name']}! Checked in for {session_option}")
                    st.balloons()
                    st.rerun()
    else:
        st.info("No residents found matching your search. Please see a volunteer.")
    
    st.divider()
    st.caption("Need help? Please ask our volunteers at the counter.")

def mark_kiosk_attendance(pid, name, date, activity, s1=True, s2=False):
    """Mark attendance from kiosk mode with S1/S2 update logic."""
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
            
            updates = {"timestamp": datetime.now().isoformat()}
            if s1: updates["session_1"] = True
            if s2: updates["session_2"] = True
            
            if current_s1 != s1 or current_s2 != s2:
                supabase.table('attendance').update(updates).eq('id', record['id']).execute()
                st.success(f"✅ Updated attendance for {name}!")
            else:
                st.info(f"ℹ️ {name} is already checked in for the selected session(s)")
        else:
            supabase.table('attendance').insert({
                "participant_id": pid,
                "name": name,
                "date": date,
                "session_1": s1,
                "session_2": s2,
                "timestamp": datetime.now().isoformat(),
                "self_checkin": False,
                "source": activity
            }).execute()
            st.success(f"✅ Check-in successful for {name}!")
    except Exception as e:
        st.error(f"Error: {e}")