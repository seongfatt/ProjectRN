import streamlit as st
st.set_page_config(page_title="Cardio Drumming Attendance", layout="wide", initial_sidebar_state="collapsed")

import pandas as pd
from datetime import datetime, timedelta
from supabase import create_client
import hashlib

# ============== CONFIGURATION ==============
SUPABASE_URL = "https://nqmvsjubgsghjpzojaxm.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5xbXZzanViZ3NnaGpwem9qYXhtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njk1NzQ3ODMsImV4cCI6MjA4NTE1MDc4M30.OukUcFvR1J5-DJVoPGmgjf34dBv7lrB1198YCp_uRIw"

def generate_token(participant_id, date_str):
    secret = SUPABASE_KEY[:20]
    return hashlib.sha256(f"{participant_id}{date_str}{secret}".encode()).hexdigest()[:16]

def verify_token(participant_id, date_str, token):
    return token == generate_token(participant_id, date_str)

# ============== DETECT SELF CHECK-IN MODE FIRST ==============
# This must run BEFORE any other st commands
is_self_checkin = False
checkin_pid = None
checkin_date = None
checkin_token = None

try:
    # Try new Streamlit syntax
    params = st.query_params
    if params.get("mode") == "checkin":
        is_self_checkin = True
        checkin_pid = params.get("pid")
        checkin_date = params.get("date", datetime.now().strftime("%Y%m%d"))
        checkin_token = params.get("tk")
except:
    pass

# ============== SELF CHECK-IN PAGE (ELDERLY VIEW) ==============
if is_self_checkin and checkin_pid and checkin_token:
    # Verify token first
    if not verify_token(checkin_pid, checkin_date, checkin_token):
        st.error("❌ Invalid or expired link. Please contact administrator.")
        st.stop()
    
    # Load THIS participant directly from DB (don't rely on session state)
    try:
        supabase_temp = create_client(SUPABASE_URL, SUPABASE_KEY)
        participant_data = supabase_temp.table('participants').select("*").eq('id', checkin_pid).execute().data
        if not participant_data:
            st.error("❌ Participant not found.")
            st.stop()
        participant = participant_data[0]
    except Exception as e:
        st.error(f"❌ Error loading your data: {e}")
        st.stop()
    
    # ELDERLY-FRIENDLY UI
    st.title("🥁 Cardio Drumming")
    st.header(f"Hello {participant['name']}!")
    st.subheader(f"📅 {datetime.strptime(checkin_date, '%Y%m%d').strftime('%d %B %Y')}")
    
    st.divider()
    st.markdown("### Which session will you attend?")
    
    # Large buttons for elderly
    col1, col2 = st.columns(2)
    with col1:
        s1 = st.checkbox("## Session 1\n### 7:00 PM - 8:00 PM", key="s1")
    with col2:
        s2 = st.checkbox("## Session 2\n### 8:00 PM - 9:00 PM", key="s2")
    
    st.divider()
    
    if st.button("✅ CONFIRM MY ATTENDANCE", type="primary", use_container_width=True):
        if not s1 and not s2:
            st.warning("⚠️ Please select at least one session")
        else:
            try:
                supabase_temp.table('attendance').insert({
                    "participant_id": checkin_pid,
                    "name": participant['name'],
                    "date": datetime.strptime(checkin_date, "%Y%m%d").strftime("%Y-%m-%d"),
                    "session_1": s1,
                    "session_2": s2,
                    "timestamp": datetime.now().isoformat(),
                    "self_checkin": True
                }).execute()
                
                st.balloons()
                st.success("## ✅ Thank You!")
                st.info("Your attendance is confirmed. See you at Woodlands Zone 6!")
                st.markdown("### 📍 Block 622 Woodlands Drive 52 #01-22")
                if s1:
                    st.markdown("**Session 1:** 7:00 PM - 8:00 PM")
                if s2:
                    st.markdown("**Session 2:** 8:00 PM - 9:00 PM")
                
            except Exception as e:
                st.error(f"❌ Error: {e}")
    
    st.divider()
    st.caption("Need help? Contact admin")
    st.stop()  # CRITICAL: Stop here so admin UI never loads

# ============== ADMIN APP BELOW (NORMAL VIEW) ==============
st.title("🥁 Woodlands Zone 6 - Cardio Drumming")
st.subheader("Admin Dashboard")

# Database setup for admin
@st.cache_resource
def get_db():
    try:
        return create_client(SUPABASE_URL, SUPABASE_KEY), True
    except:
        return None, False

supabase, DB_CONNECTED = get_db()

@st.cache_data(ttl=300)
def load_participants():
    if not DB_CONNECTED:
        return []
    try:
        return supabase.table('participants').select("*").execute().data
    except:
        return []

@st.cache_data(ttl=60)
def get_attendance_counts():
    if not DB_CONNECTED:
        return {}
    try:
        data = supabase.table('attendance').select('participant_id').execute().data
        counts = {}
        for row in data:
            pid = row['participant_id']
            counts[pid] = counts.get(pid, 0) + 1
        return counts
    except:
        return {}

def refresh_data():
    st.cache_data.clear()

# State
if 'participants' not in st.session_state:
    st.session_state.participants = load_participants()
if 'attendance_counts' not in st.session_state:
    st.session_state.attendance_counts = get_attendance_counts()
if 'whatsapp_links' not in st.session_state:
    st.session_state.whatsapp_links = []
if 'today_date' not in st.session_state:
    st.session_state.today_date = datetime.now()

# Sidebar
with st.sidebar:
    st.title("⚡ Quick Actions")
    if st.button("🔄 Refresh Data", use_container_width=True):
        refresh_data()
        st.session_state.participants = load_participants()
        st.session_state.attendance_counts = get_attendance_counts()
        st.rerun()
    
    selected_date = st.date_input("📅 Session Date", value=st.session_state.today_date)
    
    st.divider()
    st.markdown("**⏰ Session Times**")
    st.markdown("1st: 7:00 PM - 8:00 PM")
    st.markdown("2nd: 8:00 PM - 9:00 PM")

# Styles
st.markdown("""
<style>
    .stButton>button {font-size: 20px !important; padding: 20px !important;}
    .stCheckbox {font-size: 18px !important;}
</style>
""", unsafe_allow_html=True)

# Tabs
tab1, tab2, tab3, tab4 = st.tabs(["📝 Quick Check-In", "📱 WhatsApp Links", "📊 Reports", "⚙️ Manage"])

with tab1:
    st.header("Mark Attendance")
    
    participants = st.session_state.participants
    counts = st.session_state.attendance_counts
    
    cols = st.columns([2, 2, 1])
    with cols[0]:
        search = st.text_input("🔍 Search name", placeholder="Type here...")
    with cols[1]:
        filter_type = st.selectbox("Filter", ["All", "New Only", "Regular Only", "Unsigned Indemnity"])
    with cols[2]:
        st.metric("Total", len(participants))
    
    filtered = [p for p in participants if p.get('active', True)]
    if search:
        filtered = [p for p in filtered if search.lower() in p['name'].lower()]
    if filter_type == "New Only":
        filtered = [p for p in filtered if p.get('is_new')]
    elif filter_type == "Regular Only":
        filtered = [p for p in filtered if not p.get('is_new')]
    elif filter_type == "Unsigned Indemnity":
        filtered = [p for p in filtered if not p.get('indemnity')]
    
    if filtered:
        st.divider()
        cols = st.columns([4, 2, 2, 2])
        cols[0].markdown("**Name**")
        cols[1].markdown("**S1**")
        cols[2].markdown("**S2**")
        cols[3].markdown("**Action**")
        
        for p in filtered:
            pid = p['id']
            attend_count = counts.get(pid, 0)
            
            cols = st.columns([4, 2, 2, 2])
            with cols[0]:
                status = "🟢" if p.get('indemnity') else "🔴"
                badge = "🆕" if p.get('is_new') else "⭐"
                st.write(f"{status} {badge} **{p['name']}**")
                if p.get('is_new') and attend_count > 0:
                    st.caption(f"{attend_count}/3 attendances")
            
            with cols[1]:
                s1 = st.checkbox("", key=f"s1_{pid}", label_visibility="collapsed")
            with cols[2]:
                s2 = st.checkbox("", key=f"s2_{pid}", label_visibility="collapsed")
            with cols[3]:
                if st.button("✓", key=f"btn_{pid}", type="primary"):
                    try:
                        supabase.table('attendance').insert({
                            "participant_id": pid,
                            "name": p['name'],
                            "date": str(selected_date),
                            "session_1": s1,
                            "session_2": s2,
                            "timestamp": datetime.now().isoformat()
                        }).execute()
                        counts[pid] = counts.get(pid, 0) + 1
                        st.session_state.attendance_counts = counts
                        
                        if counts[pid] >= 3 and p.get('is_new'):
                            supabase.table('participants').update({'is_new': False}).eq('id', pid).execute()
                            refresh_data()
                            st.success(f"🎉 {p['name']} is now REGULAR!")
                        else:
                            st.success(f"✓ {p['name']} recorded!")
                    except Exception as e:
                        st.error(f"Error: {e}")

with tab2:
    st.header("📱 WhatsApp Self Check-in Links")
    st.info("Each participant gets their own personal link!")
    
    date_str = selected_date.strftime("%Y%m%d")
    base_url = "https://wrnz6-cardiodrum.hf.space"  # Make sure no trailing space!
    
    col1, col2 = st.columns([1, 2])
    with col1:
        if st.button("🔄 Generate Today's Links", type="primary"):
            with st.spinner("Generating..."):
                links_data = []
                for p in st.session_state.participants:
                    if p.get('active', True):
                        # Generate secure link
                        token = generate_token(p['id'], date_str)
                        personal_link = f"{base_url}/?mode=checkin&pid={p['id']}&date={date_str}&tk={token}"
                        
                        # Format phone number
                        phone = p['contact'].replace(" ", "").replace("-", "")
                        if not phone.startswith("+"):
                            phone = "+65" + phone
                        
                        # Create WhatsApp message with full link
                        # Use line breaks and emojis for clarity
                        wa_message = f"""Hello *{p['name']}*! 👋

Cardio Drumming - {selected_date.strftime('%d %B %Y')}

Please confirm your attendance:
{personal_link}

Tap the link above ☝️ and click the green button to confirm.

📍 Location: Block 622 Woodlands Drive 52 #01-22
⏰ Session 1: 7:00-8:00 PM
⏰ Session 2: 8:00-9:00 PM

Thank you!"""
                        
                        # Properly encode for WhatsApp URL
                        import urllib.parse
                        encoded_message = urllib.parse.quote(wa_message)
                        wa_url = f"https://wa.me/{phone}?text={encoded_message}"
                        
                        links_data.append({
                            'name': p['name'],
                            'phone': phone,
                            'link': personal_link,
                            'whatsapp': wa_url,
                            'message': wa_message
                        })
                
                st.session_state.whatsapp_links = links_data
                st.success(f"Generated {len(links_data)} links!")
    
    with col2:
        st.markdown("""
        **How it works:**
        1. Click Generate
        2. Click "Open WhatsApp" for each person
        3. Send the message
        4. They tap link → See ONLY their name → Confirm
        """)
    
    if st.session_state.whatsapp_links:
        st.divider()
        st.subheader(f"Send Links ({len(st.session_state.whatsapp_links)} participants)")
        
        # Add search for large lists
        if len(st.session_state.whatsapp_links) > 10:
            search_term = st.text_input("🔍 Search participant", placeholder="Type name...")
            display_links = [l for l in st.session_state.whatsapp_links if search_term.lower() in l['name'].lower()] if search_term else st.session_state.whatsapp_links
        else:
            display_links = st.session_state.whatsapp_links
        
        # Show links in a clean table
        for item in display_links:
            with st.expander(f"📱 {item['name']} - {item['phone']}"):
                st.markdown("**Full Message Preview:**")
                st.text(item['message'])  # Show full message text
                
                st.markdown("**Personal Link:**")
                st.code(item['link'])  # Show the complete link
                
                cols = st.columns(2)
                with cols[0]:
                    st.markdown(f"[📲 Click to Open WhatsApp]({item['whatsapp']})")
                with cols[1]:
                    if st.button(f"📋 Copy Link", key=f"copy_{item['name']}"):
                        st.write(f"Link copied! {item['link']}")
        
        # Download all
        st.divider()
        df_links = pd.DataFrame(st.session_state.whatsapp_links)
        csv = df_links.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download All Links (CSV)", csv, f"whatsapp_links_{date_str}.csv", "text/csv")
        
        # Bulk WhatsApp Web option
        st.info("💡 Tip: You can also copy the link and paste into WhatsApp Web if you prefer")

with tab3:
    st.header("📊 Reports")
    if DB_CONNECTED:
        today_data = supabase.table('attendance').select("*").eq('date', str(selected_date)).execute().data
        if today_data:
            df_today = pd.DataFrame(today_data)
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total", len(df_today))
            with col2:
                st.metric("Session 1", int(df_today['session_1'].sum()))
            with col3:
                st.metric("Session 2", int(df_today['session_2'].sum()))
            
            st.dataframe(df_today[['name', 'session_1', 'session_2', 'timestamp']], use_container_width=True)
        else:
            st.info("No records for selected date")

with tab4:
    st.header("⚙️ Manage")
    
    with st.expander("➕ New Participant"):
        with st.form("new_p"):
            name = st.text_input("Name")
            contact = st.text_input("Contact")
            indemnity = st.checkbox("Indemnity Signed")
            if st.form_submit_button("Register"):
                if name and contact:
                    new_p = {
                        "id": datetime.now().strftime("%Y%m%d%H%M%S"),
                        "name": name.upper(),
                        "contact": contact,
                        "indemnity": indemnity,
                        "is_new": True,
                        "active": True,
                        "registration_date": str(selected_date)
                    }
                    supabase.table('participants').insert(new_p).execute()
                    refresh_data()
                    st.success(f"Added {name}")
                    st.rerun()

st.divider()
st.caption("Woodlands Zone 6 - Cardio Drumming System")