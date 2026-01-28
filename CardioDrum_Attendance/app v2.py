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
tab1, tab2, tab3, tab4 = st.tabs(["📝 Mark Attendance", "➕ New Participant", "📊 View Records", "📝 Indemnity Status"])

with tab1:
    st.header("Check In")
    
    # Warning for unsigned indemnity
    unsigned_count = sum([1 for p in st.session_state.participants if not p.get('indemnity')])
    if unsigned_count > 0:
        st.error(f"⚠️ ATTENTION: {unsigned_count} participant(s) have NOT signed indemnity form! Update in 'Indemnity Status' tab.")
    
    st.info(f"Total Participants in Database: {len(st.session_state.participants)}")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        search_name = st.text_input("Search Name", placeholder="Type name here...", key="search")
    
    filtered = [p for p in st.session_state.participants if search_name.lower() in p['name'].lower()] if search_name else st.session_state.participants
    
    if filtered:
        st.write(f"Found {len(filtered)} participant(s)")
        
        for participant in filtered:
            with st.container():
                st.markdown('<div class="participant-card">', unsafe_allow_html=True)
                
                col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                
                with col1:
                    status_icon = "🟢" if participant.get('indemnity') else "🔴"
                    st.markdown(f"### {status_icon} {participant['name']}")
                    st.caption(f"Contact: {participant['contact']}")
                    if participant.get('is_new'):
                        st.markdown("🆕 **NEW**")
                    else:
                        st.markdown("⭐ Regular")
                
                with col2:
                    session1 = st.checkbox("1st Session", key=f"s1_{participant['id']}")
                with col3:
                    session2 = st.checkbox("2nd Session", key=f"s2_{participant['id']}")
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
            st.warning("No participant found. Add as new participant in the next tab.")
        else:
            st.info("No participants yet. Add using the 'New Participant' tab.")

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
            is_new = st.checkbox("🆕 Mark as New Participant", value=True)
        
        submitted = st.form_submit_button("💾 Save Participant", type="primary", use_container_width=True)
        
        if submitted:
            if name and contact:
                new_participant = {
                    "id": datetime.now().strftime("%Y%m%d%H%M%S"),
                    "name": name.upper(),
                    "contact": contact,
                    "indemnity": indemnity,
                    "is_new": is_new,
                    "registration_date": str(selected_date)
                }
                
                if DB_CONNECTED:
                    try:
                        supabase.table('participants').insert(new_participant).execute()
                        response = supabase.table('participants').select("*").execute()
                        st.session_state.participants = response.data
                        st.success(f"✅ {name} registered successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error saving: {e}")
                else:
                    st.session_state.participants.append(new_participant)
                    st.success(f"✅ {name} added to local list!")
            else:
                st.error("Please fill in Name and Contact")

with tab3:
    st.header("Records & Reports")
    
    if DB_CONNECTED:
        # SECTION 1: Today's Attendance
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
        
        # SECTION 2: MOST FREQUENT ATTENDEES (NEW FEATURE)
        st.subheader("🏆 Most Frequent Attendees (All Time)")
        
        try:
            # Get ALL attendance records to calculate frequency
            all_attendance = supabase.table('attendance').select("*").execute()
            df_all = pd.DataFrame(all_attendance.data)
            
            if not df_all.empty:
                # Calculate attendance frequency per participant
                freq_analysis = df_all.groupby(['participant_id', 'name']).agg({
                    'session_1': 'sum',  # Count of session 1 attendance
                    'session_2': 'sum',  # Count of session 2 attendance
                    'date': 'count'      # Total records (total days attended)
                }).reset_index()
                
                freq_analysis.columns = ['Participant ID', 'Name', 'Session 1 Count', 'Session 2 Count', 'Total Days Attended']
                freq_analysis['Total Sessions'] = freq_analysis['Session 1 Count'] + freq_analysis['Session 2 Count']
                
                # Sort by total days attended (descending)
                freq_analysis = freq_analysis.sort_values('Total Days Attended', ascending=False)
                
                # Add rank
                freq_analysis.insert(0, 'Rank', range(1, len(freq_analysis) + 1))
                
                # Display top 10
                st.write("### Top 10 Most Regular Participants")
                st.dataframe(freq_analysis.head(10), use_container_width=True)
                
                # Statistics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Most Attended (Days)", freq_analysis['Total Days Attended'].max())
                with col2:
                    st.metric("Average Attendance", f"{freq_analysis['Total Days Attended'].mean():.1f} days")
                with col3:
                    st.metric("Total Unique Attendees", len(freq_analysis))
                
                # Download full frequency report
                csv_freq = freq_analysis.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📊 Download Full Frequency Report",
                    data=csv_freq,
                    file_name=f"attendance_frequency_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
                
                # Additional: Session preference analysis
                st.markdown("### 📊 Session Preference Analysis")
                
                total_s1 = freq_analysis['Session 1 Count'].sum()
                total_s2 = freq_analysis['Session 2 Count'].sum()
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Total Session 1 Check-ins", int(total_s1))
                with col2:
                    st.metric("Total Session 2 Check-ins", int(total_s2))
                
                # Show who prefers which session
                st.write("### Session 1 Only Attendees (Never attend Session 2)")
                s1_only = freq_analysis[(freq_analysis['Session 1 Count'] > 0) & (freq_analysis['Session 2 Count'] == 0)]
                if not s1_only.empty:
                    st.dataframe(s1_only[['Rank', 'Name', 'Session 1 Count']].head(10), use_container_width=True)
                else:
                    st.info("No Session 1-only attendees found")
                
                st.write("### Session 2 Only Attendees (Never attend Session 1)")
                s2_only = freq_analysis[(freq_analysis['Session 2 Count'] > 0) & (freq_analysis['Session 1 Count'] == 0)]
                if not s2_only.empty:
                    st.dataframe(s2_only[['Rank', 'Name', 'Session 2 Count']].head(10), use_container_width=True)
                else:
                    st.info("No Session 2-only attendees found")
                
            else:
                st.warning("No attendance records found in database yet")
                
        except Exception as e:
            st.error(f"Error generating frequency report: {e}")
        
        st.markdown("---")
        
        # SECTION 3: Date Range Search
        st.subheader("🔍 Search by Date Range")
        
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("From Date", value=selected_date - timedelta(days=7))
        with col2:
            end_date = st.date_input("To Date", value=selected_date)
        
        if st.button("Search Range", type="primary"):
            try:
                range_data = supabase.table('attendance')\
                    .select("*")\
                    .gte('date', str(start_date))\
                    .lte('date', str(end_date))\
                    .execute()
                
                df_range = pd.DataFrame(range_data.data)
                if not df_range.empty:
                    st.success(f"Found {len(df_range)} records between {start_date} and {end_date}")
                    st.dataframe(df_range, use_container_width=True)
                    
                    csv_range = df_range.to_csv(index=False).encode('utf-8')
                    st.download_button("📥 Download Range Report", csv_range, f"attendance_{start_date}_to_{end_date}.csv", "text/csv")
                else:
                    st.info("No records found for this date range")
            except Exception as e:
                st.error(f"Error: {e}")

with tab4:
    st.header("Indemnity Form Management")
    
    total_parts = len(st.session_state.participants)
    signed_count = sum([1 for p in st.session_state.participants if p.get('indemnity')])
    unsigned_count = total_parts - signed_count
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total", total_parts)
    with col2:
        st.metric("✅ Signed", signed_count)
    with col3:
        st.metric("❌ Not Signed", unsigned_count, delta_color="inverse")
    
    st.markdown("---")
    
    st.subheader("❌ Participants Needing Indemnity Form")
    
    unsigned = [p for p in st.session_state.participants if not p.get('indemnity')]
    
    if unsigned:
        st.warning(f"⚠️ {len(unsigned)} participant(s) haven't signed")
        
        for participant in unsigned:
            with st.container():
                st.markdown(f'<div class="warning-box">', unsafe_allow_html=True)
                
                col1, col2, col3 = st.columns([3, 2, 1])
                
                with col1:
                    st.markdown(f"### 🔴 {participant['name']}")
                    st.caption(f"Contact: {participant['contact']}")
                
                with col2:
                    if participant.get('is_new'):
                        st.markdown("🆕 New")
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
        st.success("🎉 All participants have signed the indemnity form!")
    
    st.markdown("---")
    
    st.subheader("🔍 Search & Update Any Participant")
    
    search_indemnity = st.text_input("Search name", placeholder="Type name...")
    
    if search_indemnity:
        filtered = [p for p in st.session_state.participants if search_indemnity.lower() in p['name'].lower()]
        
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
        df_indemnity['Days Since Registration'] = pd.to_datetime(df_indemnity['registration_date']).apply(
            lambda x: (datetime.now() - x).days if pd.notna(x) else 0
        )
        
        df_export = df_indemnity[['name', 'contact', 'Indemnity Status', 'registration_date', 'Days Since Registration', 'is_new']]
        df_export.columns = ['Name', 'Contact', 'Indemnity Status', 'Registration Date', 'Days Since Registration', 'Is New']
        
        col1, col2 = st.columns(2)
        
        with col1:
            csv_all = df_export.to_csv(index=False).encode('utf-8')
            st.download_button("📄 Download All", csv_all, f"indemnity_all_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv", use_container_width=True)
        
        with col2:
            df_unsigned = df_export[df_export['Indemnity Status'] == 'NOT SIGNED']
            if not df_unsigned.empty:
                csv_unsigned = df_unsigned.to_csv(index=False).encode('utf-8')
                st.download_button(f"⚠️ Download Unsigned ({len(df_unsigned)})", csv_unsigned, f"indemnity_unsigned_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv", use_container_width=True)
            else:
                st.success("No unsigned forms!")

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