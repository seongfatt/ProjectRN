import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from supabase import create_client

# Page config - elderly friendly (large text)
st.set_page_config(page_title="Cardio Drumming Attendance", layout="wide")

# Custom CSS for elderly-friendly large buttons
st.markdown("""
<style>
    .stCheckbox label { font-size: 20px !important; }
    .stTextInput label { font-size: 20px !important; }
    .stSelectbox label { font-size: 20px !important; }
    .success-msg {
        font-size: 24px; color: green; font-weight: bold; 
        padding: 15px; background-color: #E8F5E9; 
        border-radius: 10px; text-align: center;
    }
    .participant-card {
        background-color: #f0f2f6; padding: 15px; 
        border-radius: 10px; margin: 10px 0; 
        border-left: 5px solid #0066CC;
    }
    .warning-box {
        background-color: #FEE2E2; padding: 15px; 
        border-radius: 10px; border-left: 5px solid #EF4444;
        margin: 10px 0;
    }
    .success-box {
        background-color: #D1FAE5; padding: 15px;
        border-radius: 10px; border-left: 5px solid #10B981;
        margin: 10px 0;
    }
    .info-box {
        background-color: #DBEAFE; padding: 15px;
        border-radius: 10px; border-left: 5px solid #3B82F6;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# Supabase config (your credentials)
SUPABASE_URL = "https://nqmvsjubgsghjpzojaxm.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5xbXZzanViZ3NnaGpwem9qYXhtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njk1NzQ3ODMsImV4cCI6MjA4NTE1MDc4M30.OukUcFvR1J5-DJVoPGmgjf34dBv7lrB1198YCp_uRIw"

# Initialize connection
@st.cache_resource
def init_connection():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

try:
    supabase = init_connection()
    DB_CONNECTED = True
except Exception as e:
    DB_CONNECTED = False
    st.error(f"Database connection failed: {e}")

# Function to check and auto-convert new to regular
def check_and_update_status(participant_id, participant_name):
    """Auto-convert New to Regular after 3 attendances"""
    if not DB_CONNECTED:
        return None
    
    try:
        # Count attendance records for this participant
        attendance_count = supabase.table('attendance')\
            .select('*', count='exact')\
            .eq('participant_id', participant_id)\
            .execute()
        
        count = attendance_count.count
        
        # If 3 or more attendances, check if still marked as new
        if count >= 3:
            # Get current participant data
            participant = supabase.table('participants')\
                .select('is_new')\
                .eq('id', participant_id)\
                .execute()
            
            if participant.data and participant.data[0].get('is_new', False):
                # Update to Regular
                supabase.table('participants')\
                    .update({'is_new': False})\
                    .eq('id', participant_id)\
                    .execute()
                
                return f"🎉 {participant_name} graduated to Regular status! (3+ attendances)"
        
        return None
    except Exception as e:
        return None

# Load participants from Supabase on startup
if 'participants' not in st.session_state:
    if DB_CONNECTED:
        try:
            response = supabase.table('participants').select("*").execute()
            st.session_state.participants = response.data
        except Exception as e:
            st.session_state.participants = []
            st.error(f"Error loading participants: {e}")
    else:
        st.session_state.participants = []

if 'today_date' not in st.session_state:
    st.session_state.today_date = datetime.now()

# Sidebar - Admin Controls
with st.sidebar:
    st.title("⚙️ Admin Settings")
    
    if st.button("🔄 Refresh Data"):
        if DB_CONNECTED:
            try:
                response = supabase.table('participants').select("*").execute()
                st.session_state.participants = response.data
                st.success("Data refreshed!")
                st.rerun()
            except Exception as e:
                st.error(f"Refresh failed: {e}")
    
    st.markdown("---")
    
    # Session time settings
    st.subheader("⏰ Session Times")
    session1_start = st.time_input("1st Session Start", value=pd.Timestamp("19:00").time())
    session1_end = st.time_input("1st Session End", value=pd.Timestamp("20:00").time())
    session2_start = st.time_input("2nd Session Start", value=pd.Timestamp("20:00").time())
    session2_end = st.time_input("2nd Session End", value=pd.Timestamp("21:00").time())
    
    selected_date = st.date_input("📅 Session Date", value=st.session_state.today_date)
    
    st.markdown("---")
    st.info(f"**Location:**\nBlock 622 Woodlands Drive 52\n#01-22")
    st.info(f"**1st:** {session1_start.strftime('%I:%M %p')} - {session1_end.strftime('%I:%M %p')}\n\n**2nd:** {session2_start.strftime('%I:%M %p')} - {session2_end.strftime('%I:%M %p')}")

# Main App
st.title("🥁 Woodlands Zone 6 - Cardio Drumming")
st.subheader(f"Attendance for {selected_date.strftime('%d %B %Y')}")

# Tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📝 Mark Attendance", "➕ New Participant", "🏆 Reports & Analytics", "📝 Indemnity Status", "⚙️ Manage Participants"])

with tab1:
    st.header("Check In")
    
    # Only show ACTIVE participants for daily check-in (with safety check)
    active_participants = [p for p in st.session_state.participants if p.get('active', True)]
    
    # Warning for unsigned indemnity (among active only)
    unsigned_count = sum([1 for p in active_participants if not p.get('indemnity')])
    if unsigned_count > 0:
        st.error(f"⚠️ {unsigned_count} active participant(s) haven't signed indemnity form!")
    
    # Stats
    new_count = sum([1 for p in active_participants if p.get('is_new')])
    regular_count = len(active_participants) - new_count
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Active Participants", len(active_participants))
    with col2:
        st.metric("🆕 New", new_count)
    with col3:
        st.metric("⭐ Regular", regular_count)
    
    st.markdown("---")
    
    # Search
    search_name = st.text_input("🔍 Search Name", placeholder="Type name here...")
    
    # Filter only ACTIVE participants for check-in
    filtered = [p for p in active_participants if search_name.lower() in p['name'].lower()] if search_name else active_participants
    
    if filtered:
        st.write(f"Found {len(filtered)} participant(s)")
        
        for participant in filtered:
            with st.container():
                # Show attendance count for new participants
                if participant.get('is_new'):
                    if DB_CONNECTED:
                        try:
                            attendance_data = supabase.table('attendance')\
                                .select('*', count='exact')\
                                .eq('participant_id', participant['id'])\
                                .execute()
                            attend_count = attendance_data.count
                            progress = min(attend_count / 3 * 100, 100)
                            st.progress(progress / 100, text=f"Progress to Regular: {attend_count}/3 attendances")
                        except:
                            pass
                
                st.markdown('<div class="participant-card">', unsafe_allow_html=True)
                
                col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                
                with col1:
                    status_icon = "🟢" if participant.get('indemnity') else "🔴"
                    status_text = "🆕 NEW" if participant.get('is_new') else "⭐ REGULAR"
                    st.markdown(f"### {status_icon} {participant['name']}")
                    st.caption(f"Contact: {participant['contact']}")
                    st.markdown(f"**{status_text}**")
                
                with col2:
                    session1 = st.checkbox("Session 1", key=f"s1_{participant['id']}")
                with col3:
                    session2 = st.checkbox("Session 2", key=f"s2_{participant['id']}")
                with col4:
                    if st.button("✅ Confirm", key=f"btn_{participant['id']}", type="primary", use_container_width=True):
                        attendance_record = {
                            "participant_id": participant['id'],
                            "name": participant['name'],
                            "date": str(selected_date),
                            "session_1": session1,
                            "session_2": session2,
                            "timestamp": datetime.now().isoformat()
                        }
                        
                        if DB_CONNECTED:
                            try:
                                supabase.table('attendance').insert(attendance_record).execute()
                                
                                # Check if auto-convert needed
                                convert_msg = check_and_update_status(participant['id'], participant['name'])
                                
                                if convert_msg:
                                    st.success(convert_msg)
                                    # Refresh participants list
                                    response = supabase.table('participants').select("*").execute()
                                    st.session_state.participants = response.data
                                
                                st.success(f"✓ {participant['name']} recorded!")
                                st.balloons()
                            except Exception as e:
                                st.error(f"Error saving attendance: {e}")
                        else:
                            if 'attendance' not in st.session_state:
                                st.session_state.attendance = []
                            st.session_state.attendance.append(attendance_record)
                            st.success(f"✓ {participant['name']} saved locally!")
                            st.balloons()
                
                st.markdown('</div>', unsafe_allow_html=True)
                st.markdown("---")
    else:
        if search_name:
            st.warning("No participant found. Add as new participant or check inactive list.")
        else:
            st.info("No active participants. Add using the 'New Participant' tab.")

with tab2:
    st.header("Register New Participant")
    
    with st.form("new_participant", clear_on_submit=True):
        st.markdown("### Personal Details")
        name = st.text_input("Full Name*", placeholder="e.g., Tan Ah Kow")
        contact = st.text_input("Contact Number*", placeholder="e.g., 91234567")
        
        st.markdown("### Indemnity Form")
        col1, col2 = st.columns(2)
        with col1:
            indemnity = st.checkbox("✓ Indemnity Form Signed", help="Required once only before first session")
        with col2:
            st.info("New participants auto-convert to Regular after 3 attendances")
        
        submitted = st.form_submit_button("💾 Save Participant", type="primary", use_container_width=True)
        
        if submitted:
            if name and contact:
                new_participant = {
                    "id": datetime.now().strftime("%Y%m%d%H%M%S"),
                    "name": name.upper(),
                    "contact": contact,
                    "indemnity": indemnity,
                    "is_new": True,  # Always start as New
                    "active": True,
                    "registration_date": str(selected_date)
                }
                
                if DB_CONNECTED:
                    try:
                        supabase.table('participants').insert(new_participant).execute()
                        response = supabase.table('participants').select("*").execute()
                        st.session_state.participants = response.data
                        st.success(f"✅ {name} registered as NEW participant!")
                        st.info("ℹ️ Will auto-convert to REGULAR after 3 attendances")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error saving: {e}")
                else:
                    st.session_state.participants.append(new_participant)
                    st.success(f"✅ {name} added locally!")
            else:
                st.error("Please fill in Name and Contact")

with tab3:
    st.header("📊 Reports & Analytics")
    
    if DB_CONNECTED:
        # Today's Attendance
        st.subheader("📅 Today's Attendance")
        
        try:
            attendance_data = supabase.table('attendance').select("*").eq('date', str(selected_date)).execute()
            df_today = pd.DataFrame(attendance_data.data)
            
            if not df_today.empty:
                st.success(f"Found {len(df_today)} attendance records for {selected_date}")
                st.dataframe(df_today, use_container_width=True)
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Check-ins", len(df_today))
                with col2:
                    st.metric("Session 1", df_today['session_1'].sum())
                with col3:
                    st.metric("Session 2", df_today['session_2'].sum())
                
                csv = df_today.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download Today's CSV", csv, f"attendance_{selected_date}.csv", "text/csv")
            else:
                st.info(f"No attendance records for {selected_date} yet")
        except Exception as e:
            st.error(f"Error loading today's attendance: {e}")
        
        st.markdown("---")
        
        # Most Frequent Attendees
        st.subheader("🏆 Most Frequent Attendees (All Time)")
        
        try:
            all_attendance = supabase.table('attendance').select("*").execute()
            df_all = pd.DataFrame(all_attendance.data)
            
            if not df_all.empty:
                # Calculate frequency
                freq_analysis = df_all.groupby(['participant_id', 'name']).agg({
                    'session_1': 'sum',
                    'session_2': 'sum',
                    'date': 'count'
                }).reset_index()
                
                freq_analysis.columns = ['Participant ID', 'Name', 'Session 1 Count', 'Session 2 Count', 'Total Days Attended']
                freq_analysis['Total Sessions'] = freq_analysis['Session 1 Count'] + freq_analysis['Session 2 Count']
                freq_analysis = freq_analysis.sort_values('Total Days Attended', ascending=False)
                freq_analysis.insert(0, 'Rank', range(1, len(freq_analysis) + 1))
                
                # Add status column
                def get_status(row):
                    pid = row['Participant ID']
                    participant = next((p for p in st.session_state.participants if p['id'] == pid), None)
                    if participant:
                        return "🆕 New" if participant.get('is_new') else "⭐ Regular"
                    return "Unknown"
                
                freq_analysis['Current Status'] = freq_analysis.apply(get_status, axis=1)
                
                st.write("### Top 10 Most Regular Participants")
                st.dataframe(freq_analysis.head(10), use_container_width=True)
                
                st.write("### 🆕 New Participants Close to Graduation (2 attendances)")
                close_to_grad = freq_analysis[(freq_analysis['Total Days Attended'] == 2)]
                if not close_to_grad.empty:
                    st.dataframe(close_to_grad[['Name', 'Total Days Attended', 'Current Status']], use_container_width=True)
                    st.info("These participants will become REGULAR on their next attendance!")
                else:
                    st.info("No participants with exactly 2 attendances currently")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Most Attended", freq_analysis['Total Days Attended'].max(), "days")
                with col2:
                    st.metric("Average", f"{freq_analysis['Total Days Attended'].mean():.1f}", "days")
                with col3:
                    st.metric("Unique Attendees", len(freq_analysis))
                
                csv_freq = freq_analysis.to_csv(index=False).encode('utf-8')
                st.download_button("📊 Download Full Report", csv_freq, f"frequency_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv", use_container_width=True)
            else:
                st.warning("No attendance records found")
        except Exception as e:
            st.error(f"Error generating report: {e}")
        
        st.markdown("---")
        
        # Date Range Search
        st.subheader("🔍 Search by Date Range")
        
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("From Date", value=selected_date - timedelta(days=7))
        with col2:
            end_date = st.date_input("To Date", value=selected_date)
        
        if st.button("Search Range", type="primary"):
            try:
                range_data = supabase.table('attendance').select("*").gte('date', str(start_date)).lte('date', str(end_date)).execute()
                df_range = pd.DataFrame(range_data.data)
                if not df_range.empty:
                    st.success(f"Found {len(df_range)} records")
                    st.dataframe(df_range, use_container_width=True)
                    csv_range = df_range.to_csv(index=False).encode('utf-8')
                    st.download_button("📥 Download Range Report", csv_range, f"attendance_{start_date}_to_{end_date}.csv", "text/csv")
                else:
                    st.info("No records found for this range")
            except Exception as e:
                st.error(f"Error: {e}")

with tab4:
    st.header("📝 Indemnity Form Management")
    
    # SAFETY CHECK: Filter only if 'active' key exists
    active_parts = [p for p in st.session_state.participants if p.get('active', True)]
    total_parts = len(active_parts)
    signed_count = sum([1 for p in active_parts if p.get('indemnity')])
    unsigned_count = total_parts - signed_count
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Active Total", total_parts)
    with col2:
        st.metric("✅ Signed", signed_count)
    with col3:
        st.metric("❌ Not Signed", unsigned_count, delta_color="inverse")
    
    st.markdown("---")
    
    st.subheader("❌ Unsigned Participants (Action Required)")
    
    unsigned = [p for p in active_parts if not p.get('indemnity')]
    
    if unsigned:
        st.warning(f"⚠️ {len(unsigned)} participant(s) haven't signed indemnity form")
        
        for participant in unsigned:
            with st.container():
                st.markdown(f'<div class="warning-box">', unsafe_allow_html=True)
                
                col1, col2, col3 = st.columns([3, 2, 1])
                
                with col1:
                    st.markdown(f"### 🔴 {participant['name']}")
                    st.caption(f"Contact: {participant['contact']}")
                    if participant.get('is_new'):
                        st.markdown("🆕 New Participant")
                    else:
                        st.markdown("⭐ Regular")
                
                with col3:
                    if st.button("✍️ Mark Signed", key=f"indemnity_{participant['id']}", type="primary"):
                        if DB_CONNECTED:
                            try:
                                supabase.table('participants').update({'indemnity': True}).eq('id', participant['id']).execute()
                                response = supabase.table('participants').select("*").execute()
                                st.session_state.participants = response.data
                                st.success(f"✅ {participant['name']} marked as signed!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")
                
                st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="success-box">🎉 All active participants have signed!</div>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    st.subheader("🔍 Search & Edit")
    
    search_indemnity = st.text_input("Search participant", placeholder="Type name...")
    
    if search_indemnity:
        filtered = [p for p in active_parts if search_indemnity.lower() in p['name'].lower()]
        
        for p in filtered:
            status = "✅ SIGNED" if p.get('indemnity') else "❌ NOT SIGNED"
            with st.expander(f"{p['name']} - {status}"):
                st.write(f"Contact: {p['contact']}")
                
                col1, col2 = st.columns(2)
                with col1:
                    if not p.get('indemnity'):
                        if st.button("✓ Mark SIGNED", key=f"sign_{p['id']}", type="primary"):
                            if DB_CONNECTED:
                                supabase.table('participants').update({'indemnity': True}).eq('id', p['id']).execute()
                                response = supabase.table('participants').select("*").execute()
                                st.session_state.participants = response.data
                                st.rerun()
                with col2:
                    if p.get('indemnity'):
                        if st.button("✗ Mark UNSIGNED", key=f"unsign_{p['id']}"):
                            if DB_CONNECTED:
                                supabase.table('participants').update({'indemnity': False}).eq('id', p['id']).execute()
                                response = supabase.table('participants').select("*").execute()
                                st.session_state.participants = response.data
                                st.rerun()
    
    st.markdown("---")
    st.subheader("📥 Download Indemnity Report")
    
    if st.session_state.participants:
        df_indemnity = pd.DataFrame(st.session_state.participants)
        df_indemnity['Indemnity Status'] = df_indemnity['indemnity'].apply(lambda x: 'SIGNED' if x else 'NOT SIGNED')
        df_indemnity['Participant Type'] = df_indemnity['is_new'].apply(lambda x: 'New' if x else 'Regular')
        
        # SAFETY CHECK for 'active' column
        if 'active' in df_indemnity.columns:
            df_indemnity['Account Status'] = df_indemnity['active'].apply(lambda x: 'Active' if x else 'Inactive')
            df_export = df_indemnity[['name', 'contact', 'Participant Type', 'Indemnity Status', 'Account Status', 'registration_date']]
            df_export.columns = ['Name', 'Contact', 'Type', 'Indemnity', 'Status', 'Registration Date']
        else:
            # If 'active' column doesn't exist, show all as Active
            df_export = df_indemnity[['name', 'contact', 'Participant Type', 'Indemnity Status', 'registration_date']]
            df_export.columns = ['Name', 'Contact', 'Type', 'Indemnity', 'Registration Date']
            st.warning("⚠️ 'active' column not found in database. Please add it in Supabase for full functionality.")
        
        col1, col2 = st.columns(2)
        
        with col1:
            csv_all = df_export.to_csv(index=False).encode('utf-8')
            st.download_button("📄 All Participants", csv_all, f"indemnity_all_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv", use_container_width=True)
        
        with col2:
            df_unsigned_only = df_export[df_export['Indemnity'] == 'NOT SIGNED']
            if not df_unsigned_only.empty:
                csv_unsigned = df_unsigned_only.to_csv(index=False).encode('utf-8')
                st.download_button(f"⚠️ Unsigned Only ({len(df_unsigned_only)})", csv_unsigned, f"indemnity_unsigned_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv", use_container_width=True)

with tab5:
    st.header("⚙️ Manage Participants")
    
    st.info("💡 Use this tab to deactivate participants who stopped coming, or reactivate old ones.")
    
    # Check if 'active' column exists in data
    has_active_column = any('active' in p for p in st.session_state.participants)
    
    if not has_active_column:
        st.error("⚠️ 'active' column not found in database!")
        st.info("Please add it in Supabase Table Editor: participants table → Add column → 'active' (boolean, default: true)")
        st.code("SQL: alter table participants add column active boolean default true;", language='sql')
        st.stop()  # Stop execution of this tab if column missing
    
    # Section 1: Deactivate Active
    st.subheader("🟢 Active Participants (Click to Deactivate)")
    active_list = [p for p in st.session_state.participants if p.get('active', True)]
    
    if active_list:
        for p in active_list:
            status_badge = "🆕" if p.get('is_new') else "⭐"
            with st.expander(f"{status_badge} {p['name']} - {p['contact']}"):
                col1, col2, col3 = st.columns([2, 2, 1])
                
                with col1:
                    st.write(f"**Type:** {'New' if p.get('is_new') else 'Regular'}")
                    st.write(f"**Indemnity:** {'✅ Signed' if p.get('indemnity') else '❌ Unsigned'}")
                
                with col2:
                    if st.button("⏸️ Deactivate (Hide)", key=f"deact_{p['id']}", type="primary", use_container_width=True):
                        if DB_CONNECTED:
                            try:
                                supabase.table('participants').update({'active': False}).eq('id', p['id']).execute()
                                response = supabase.table('participants').select("*").execute()
                                st.session_state.participants = response.data
                                st.success(f"{p['name']} deactivated!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")
                
                with col3:
                    st.write("**DANGER:**")
                    confirm_del = st.checkbox("Confirm Delete", key=f"confirm_del_{p['id']}")
                    if confirm_del:
                        if st.button("🗑️ Delete Forever", key=f"del_{p['id']}", type="secondary"):
                            if DB_CONNECTED:
                                try:
                                    supabase.table('participants').delete().eq('id', p['id']).execute()
                                    response = supabase.table('participants').select("*").execute()
                                    st.session_state.participants = response.data
                                    st.warning(f"{p['name']} permanently deleted!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error: {e}")
    else:
        st.info("No active participants")
    
    st.markdown("---")
    
    # Section 2: Reactivate Inactive
    st.subheader("⚪ Inactive Participants (Click to Reactivate)")
    inactive_list = [p for p in st.session_state.participants if not p.get('active', True)]
    
    if inactive_list:
        st.warning(f"There are {len(inactive_list)} inactive participant(s)")
        
        for p in inactive_list:
            with st.expander(f"⚪ {p['name']} (INACTIVE) - {p['contact']}"):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"**Last Registered:** {p.get('registration_date', 'Unknown')}")
                    st.write(f"**Previous Status:** {'New' if p.get('is_new') else 'Regular'}")
                with col2:
                    if st.button("✅ Reactivate", key=f"react_{p['id']}", type="primary"):
                        if DB_CONNECTED:
                            try:
                                supabase.table('participants').update({'active': True}).eq('id', p['id']).execute()
                                response = supabase.table('participants').select("*").execute()
                                st.session_state.participants = response.data
                                st.success(f"{p['name']} reactivated!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")
    else:
        st.markdown('<div class="success-box">All participants are currently active!</div>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Section 3: Force Convert New to Regular (Manual Override)
    st.subheader("🔄 Manual Status Override")
    st.info("Use this to manually convert New to Regular (bypass the 3-attendance auto-check)")
    
    new_active_list = [p for p in active_list if p.get('is_new')]
    
    if new_active_list:
        st.write(f"Currently {len(new_active_list)} New participant(s):")
        
        for p in new_active_list:
            with st.expander(f"🆕 {p['name']}"):
                col1, col2 = st.columns([3, 1])
                with col1:
                    # Show current attendance count
                    if DB_CONNECTED:
                        try:
                            count_data = supabase.table('attendance').select('*', count='exact').eq('participant_id', p['id']).execute()
                            count = count_data.count
                            st.write(f"**Current Attendances:** {count}")
                            st.write(f"**Auto-convert at:** 3 attendances")
                        except:
                            st.write("Cannot retrieve count")
                
                with col2:
                    if st.button("⭐ Make Regular Now", key=f"make_reg_{p['id']}", type="primary"):
                        if DB_CONNECTED:
                            try:
                                supabase.table('participants').update({'is_new': False}).eq('id', p['id']).execute()
                                response = supabase.table('participants').select("*").execute()
                                st.session_state.participants = response.data
                                st.success(f"{p['name']} is now REGULAR!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")
    else:
        st.info("No New participants to convert")

st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 20px;'>
    <small>
    ⏰ Time and date are subject to change.<br>
    Participants will be informed of any replacement or updated schedule.<br>
    All participants are required to fill in the Indemnity Form once only.
    </small>
</div>
""", unsafe_allow_html=True)