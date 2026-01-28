import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from supabase import create_client
import json

# Page config - elderly friendly (large text)
st.set_page_config(page_title="Cardio Drumming Attendance", layout="wide")

# Custom CSS for elderly-friendly large buttons
st.markdown("""
<style>
    .big-button {
        font-size: 24px !important;
        padding: 20px !important;
        background-color: #0066CC;
        color: white;
        border-radius: 10px;
    }
    .stCheckbox label {
        font-size: 20px !important;
    }
    .stTextInput label {
        font-size: 20px !important;
    }
    .success-msg {
        font-size: 24px;
        color: green;
        font-weight: bold;
        padding: 15px;
        background-color: #E8F5E9;
        border-radius: 10px;
        text-align: center;
    }
    .participant-card {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        margin: 10px 0;
        border-left: 5px solid #0066CC;
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

# FIX 1: Load participants from Supabase on startup (not empty list)
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
    
    # Refresh button to reload data from database
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
    
    # Date selection (in case of replacement dates)
    selected_date = st.date_input("📅 Session Date", value=st.session_state.today_date)
    
    st.markdown("---")
    st.info(f"**Location:**\nBlock 622 Woodlands Drive 52\n#01-22")
    st.info(f"**1st:** {session1_start.strftime('%I:%M %p')} - {session1_end.strftime('%I:%M %p')}\n\n**2nd:** {session2_start.strftime('%I:%M %p')} - {session2_end.strftime('%I:%M %p')}")

# Main App
st.title("🥁 Woodlands Zone 6 - Cardio Drumming")
st.subheader(f"Attendance for {selected_date.strftime('%d %B %Y')}")

# Create tabs for different functions
tab1, tab2, tab3 = st.tabs(["📝 Mark Attendance", "➕ New Participant", "📊 View Records"])

with tab1:
    st.header("Check In")
    
    # Show total participants count
    st.info(f"Total Participants in Database: {len(st.session_state.participants)}")
    
    # Search participant
    col1, col2 = st.columns([3, 1])
    with col1:
        search_name = st.text_input("Search Name", placeholder="Type name here...", key="search")
    
    # Filter participants
    filtered = [p for p in st.session_state.participants if search_name.lower() in p['name'].lower()] if search_name else st.session_state.participants
    
    if filtered:
        st.write(f"Found {len(filtered)} participant(s)")
        
        for participant in filtered:
            with st.container():
                # Create a card-like container
                st.markdown('<div class="participant-card">', unsafe_allow_html=True)
                
                col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                
                with col1:
                    status_icon = "🟢" if participant.get('indemnity') else "🔴"
                    st.markdown(f"### {status_icon} {participant['name']}")
                    st.caption(f"Contact: {participant['contact']}")
                    if participant.get('is_new'):
                        st.markdown("🆕 **NEW PARTICIPANT**")
                    else:
                        st.markdown("⭐ Regular")
                
                with col2:
                    session1 = st.checkbox("1st Session", key=f"s1_{participant['id']}")
                with col3:
                    session2 = st.checkbox("2nd Session", key=f"s2_{participant['id']}")
                with col4:
                    if st.button("✅ Confirm", key=f"btn_{participant['id']}", type="primary", use_container_width=True):
                        # Save attendance - ID is auto-generated by Supabase (don't include it)
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
            st.info("No participants yet. Add participants using the 'New Participant' tab.")

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
                        
                        # FIX 2: Refresh the list from Supabase immediately
                        response = supabase.table('participants').select("*").execute()
                        st.session_state.participants = response.data
                        
                        st.success(f"✅ {name} registered successfully!")
                        st.rerun()  # Refresh page to show updated list
                        
                    except Exception as e:
                        st.error(f"Error saving: {e}")
                else:
                    st.session_state.participants.append(new_participant)
                    st.success(f"✅ {name} added to local list!")
            else:
                st.error("Please fill in Name and Contact")

with tab3:
    st.header("Records & Export")
    
    # View Attendance Records
    st.subheader("Today's Attendance")
    
    if DB_CONNECTED:
        try:
            # Fetch attendance for selected date
            attendance_data = supabase.table('attendance')\
                .select("*")\
                .eq('date', str(selected_date))\
                .execute()
            
            df = pd.DataFrame(attendance_data.data)
            
            if not df.empty:
                st.success(f"Found {len(df)} attendance records for {selected_date}")
                st.dataframe(df, use_container_width=True)
                
                # Summary stats
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Check-ins", len(df))
                with col2:
                    st.metric("Session 1 Attendees", df['session_1'].sum())
                with col3:
                    st.metric("Session 2 Attendees", df['session_2'].sum())
                
                # Export to CSV
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download Today's Attendance (CSV)",
                    data=csv,
                    file_name=f"attendance_{selected_date}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            else:
                st.info(f"No attendance records for {selected_date} yet")
                
        except Exception as e:
            st.error(f"Error loading attendance: {e}")
    else:
        st.warning("Database not connected - cannot show records")

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 20px;'>
    <small>
    ⏰ Time and date are subject to change.<br>
    Participants will be informed of any replacement or updated schedule.<br>
    All participants are required to fill in the Indemnity Form once only, before joining the Cardio Drumming session.
    </small>
</div>
""", unsafe_allow_html=True)