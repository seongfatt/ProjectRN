import streamlit as st
import random
from datetime import datetime, timedelta, timezone
from config import supabase, DB_CONNECTED, load_activities, refresh_data, APP_URL
from utils import clean_phone_number, find_participant_by_phone, check_returning_guest, mask_phone, validate_checkin_time
try:
    from utils import sync_session_attendance_async
except ImportError:
    def sync_session_attendance_async(*args, **kwargs):
        pass
import urllib.parse
import base64
import os
from PIL import Image
import cv2
import numpy as np
import io
from services import AttendanceService, RegistrationService

# ============================================
# LOGO HELPER FUNCTION
# ============================================

def _get_logo_base64(logo_path="logo.png"):
    """Convert local logo to base64 so it renders inside HTML components."""
    try:
        if os.path.exists(logo_path):
            with open(logo_path, "rb") as f:
                data = f.read()
            ext = os.path.splitext(logo_path)[1].lower().replace(".", "")
            if ext == "svg":
                ext = "svg+xml"
            return f"data:image/{ext};base64,{base64.b64encode(data).decode()}"
    except Exception:
        pass
    return (
        "data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+"
        "PHJlY3Qgd2lkdGg9IjYwIiBoZWlnaHQ9IjYwIiBmaWxsPSIjNjY3ZWVhIiByeD0iMTAiLz48dGV4dCB4PSI1MCUiIHk9"
        "IjUwJSIgZG9taW5hbnQtYmFzZWxpbmU9Im1pZGRsZSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZmlsbD0id2hpdGUiIGZvbnQt"
        "ZmFtaWx5PSJBcmlhbCIgZm9udC1zaXplPSIxNCIgZm9udC13ZWlnaHQ9ImJvbGQiPldaNjwvdGV4dD48L3N2Zz4="
    )

# ============================================
# QR DECODING FUNCTION
# ============================================

def decode_qr_from_image(image):
    """Decode QR code from PIL Image using OpenCV"""
    try:
        img_array = np.array(image)
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        qr_detector = cv2.QRCodeDetector()
        data, bbox, _ = qr_detector.detectAndDecode(gray)
        if data:
            return data
        return None
    except Exception as e:
        print(f"Error decoding QR: {e}")
        return None

# ============================================
# PROCESS CHECK-IN FUNCTION (1-4 SESSIONS)
# ============================================

def process_portal_checkin(pid, date, activity, s1, s2, s3=False, s4=False):
    """Core logic: Time Validation + SESSION UPDATE (1-4 sessions). Returns True/False."""
    try:
        selected = [s1, s2, s3, s4]

        if isinstance(date, str):
            if len(date) == 8 and date.isdigit():
                formatted_date = datetime.strptime(date, "%Y%m%d").strftime("%Y-%m-%d")
            else:
                formatted_date = date
        else:
            formatted_date = date.strftime("%Y-%m-%d")

        res = supabase.table('participants').select("*").eq('id', pid).execute()
        if not res.data:
            st.error(f"❌ Resident ID not found: {pid}")
            return False
        resident = res.data[0]

        existing = supabase.table('attendance').select("*") \
            .eq('participant_id', pid).eq('date', formatted_date).eq('source', activity).execute()

        if existing.data and len(existing.data) > 0:
            record = existing.data[0]
            missing = [i + 1 for i, f in enumerate(selected) if f and not record.get(f'session_{i + 1}', False)]

            if not missing:
                st.info(f"ℹ️ **{resident['name']}** is already fully checked in for {activity} today.")
                return False

            is_allowed, message = validate_checkin_time(activity, missing[0])
            if not is_allowed:
                st.error(message)
                st.info("💡 If this is incorrect, please contact the admin to adjust the session times or disable time validation.")
                return False

            updates = {"timestamp": datetime.now(timezone(timedelta(hours=8))).isoformat()}
            for n in missing:
                updates[f'session_{n}'] = True
            current_activities = record.get('activities') or []
            if activity not in current_activities:
                current_activities.append(activity)
            updates['activities'] = current_activities
            supabase.table('attendance').update(updates).eq('id', record['id']).execute()

            sync_session_attendance_async(pid, resident['name'], activity, formatted_date,
                                          st.session_state.get('user_role', 'volunteer'))
            st.success(f"✅ Updated {resident['name']} with additional session(s)!")
            return True

        first_selected = next((i + 1 for i, f in enumerate(selected) if f), 1)
        is_allowed, message = validate_checkin_time(activity, first_selected)
        if not is_allowed:
            st.error(message)
            st.info("💡 If this is incorrect, please contact the admin to adjust the session times or disable time validation.")
            return False

        supabase.table('attendance').insert({
            "participant_id": pid, "name": resident['name'], "date": formatted_date,
            "session_1": s1, "session_2": s2, "session_3": s3, "session_4": s4,
            "timestamp": datetime.now(timezone(timedelta(hours=8))).isoformat(),
            "self_checkin": False, "source": activity,
            "activities": [activity]
        }).execute()
        refresh_data()

        sync_session_attendance_async(pid, resident['name'], activity, formatted_date,
                                      st.session_state.get('user_role', 'volunteer'))

        # Safe success message formatting
        session_text = []
        if s1: session_text.append("Session 1")
        if s2: session_text.append("Session 2")
        if s3: session_text.append("Session 3")
        if s4: session_text.append("Session 4")
        session_display = " & ".join(session_text) if session_text else "Attendance"
        
        st.markdown(f"""
        <div style="background: #e8f5e9; color: #1e7e34; padding: 20px; border-radius: 8px; border-left: 5px solid #28a745; margin: 15px 0;">
            <div style="display: flex; align-items: center; gap: 12px;">
                <span style="font-size: 28px;">✅</span>
                <div>
                    <h4 style="margin: 0; color: #1e7e34;">Check-in Successful</h4>
                    <p style="margin: 4px 0 0 0; font-size: 16px; font-weight: 500;">{resident['name']}</p>
                </div>
            </div>
            <hr style="margin: 12px 0; border: none; border-top: 1px solid #c8e6c9;">
            <div style="display: flex; flex-wrap: wrap; gap: 16px; font-size: 14px; color: #2e7d32;">
                <span>🕐 {datetime.now().strftime('%I:%M %p')}</span>
                <span>📅 {datetime.strptime(formatted_date, '%Y-%m-%d').strftime('%d %b %Y')}</span>
                <span>📋 {activity}</span>
                <span>✅ {session_display}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.session_state.checkin_success = True
        return True
    except Exception as e:
        if 'duplicate key' in str(e):
            st.info(f"ℹ️ Already checked in for **{activity}** today.")
            return False
        else:
            st.error(f"Error: {e}")
            return False

# ============================================
# MAIN VOLUNTEER PORTAL FUNCTION
# ============================================

def show_volunteer_portal(token, activity_param=None):
    """UNIFIED VOLUNTEER PORTAL WITH RELIABLE QR SCANNING"""
    from pages.volunteer_access import validate_volunteer_token
    is_valid, msg = validate_volunteer_token(token)
    
    if not is_valid:
        st.error(f"❌ {msg}")
        st.markdown("""
        <div style="background: #ffebee; border-left: 4px solid #f44336; padding: 20px; border-radius: 8px; text-align: center; color: #1a1a1a;">
            <h3 style="color: #d32f2f; margin-top: 0;">⏰ Access Expired</h3>
            <p style="color: #1a1a1a; font-size: 16px; font-weight: bold;">This volunteer link is no longer valid.</p>
            <p style="color: #555; font-size: 14px;">Please contact the admin for a new link.</p>
        </div>
        """, unsafe_allow_html=True)
        st.stop()

    logo_src = _get_logo_base64()
    
    # CSS
    st.markdown("""
    <style>
    .portal-header-card { background: #ffffff; color: #1a1a1a; border-radius: 20px; padding: 30px 24px; box-shadow: 0 10px 30px rgba(0,0,0,0.12); max-width: 600px; margin: 0 auto 25px auto; text-align: center; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
    .portal-header-card .header-row { display: flex; align-items: center; justify-content: center; gap: 15px; margin-bottom: 20px; }
    .portal-header-card .header-row img { width: 60px; height: 60px; object-fit: contain; background: #f8f9fa; border-radius: 10px; padding: 5px; flex-shrink: 0; }
    .portal-header-card .title-group { text-align: left; }
    .portal-header-card .title-group h1 { color: #667eea; margin: 0; font-size: 24px; font-weight: 800; line-height: 1.1; }
    .portal-header-card .title-group p { color: #666; margin: 2px 0 0 0; font-size: 12px; text-transform: uppercase; letter-spacing: 1px; }
    .portal-header-card .divider { border: 0; border-top: 2px solid #eee; margin: 20px 0; }
    .portal-header-card h2 { margin: 10px 0 5px 0; font-size: 28px; font-weight: bold; color: #1a1a1a; letter-spacing: 1px; }
    .portal-header-card .subtitle { margin: 0; font-size: 16px; color: #555; font-weight: 500; }
    .method-card { background: white; border-radius: 12px; padding: 25px; margin: 15px 0; box-shadow: 0 2px 10px rgba(0,0,0,0.08); border-left: 5px solid #667eea; }
    .method-card h3 { margin-top: 0; color: #667eea; }
    .method-card p, .method-card div, .method-card span { color: #1a1a1a !important; }
    .stats-box { background: #e3f2fd; padding: 15px; border-radius: 10px; margin: 20px 0; text-align: center; }
    .qr-scanner-container { background: white; padding: 20px; border-radius: 15px; margin: 20px 0; text-align: center; border: 2px dashed #667eea; }
    .status-success { background: #d4edda; color: #155724; padding: 15px; border-radius: 8px; border: 2px solid #28a745; animation: fadeIn 0.5s; }
    .status-error { background: #f8d7da; color: #721c24; padding: 15px; border-radius: 8px; border: 2px solid #dc3545; animation: fadeIn 0.5s; }
    .status-info { background: #d1ecf1; color: #0c5460; padding: 15px; border-radius: 8px; border: 2px solid #17a2b8; animation: fadeIn 0.5s; }
    @keyframes fadeIn { from { opacity: 0; transform: translateY(-10px); } to { opacity: 1; transform: translateY(0); } }
    @media (max-width: 768px) {
        .portal-header-card { padding: 20px 15px; margin: 0 10px 25px 10px; }
        .portal-header-card h2 { font-size: 24px; }
        .method-card { padding: 20px 15px; }
        .qr-scanner-container { padding: 15px; }
    }
    .time-info-box { background: #e8f4fd; padding: 15px; border-radius: 8px; margin: 10px 0; border-left: 4px solid #667eea; }
    </style>
    """, unsafe_allow_html=True)

    # Header
    st.markdown(f"""
    <div class="portal-header-card">
        <div class="header-row">
            <img src="{logo_src}" alt="Logo">
            <div class="title-group">
                <h1>WOODLANDS ZONE 6</h1>
                <p>Community Hub</p>
            </div>
        </div>
        <hr class="divider">
        <h2>VOLUNTEER PORTAL</h2>
        <p class="subtitle">Fast & Easy Check-In System</p>
    </div>
    """, unsafe_allow_html=True)

    # Token expiry
    try:
        token_data = supabase.table('volunteer_tokens').select("*").eq('token', token).single().execute().data
        expires_str = token_data['expires_at']
        if expires_str.endswith('Z'): expires_str = expires_str.replace('Z', '+00:00')
        expires = datetime.fromisoformat(expires_str)
        if expires.tzinfo is None: expires = expires.replace(tzinfo=timezone.utc)
        sgt_timezone = timezone(timedelta(hours=8))
        expires_sgt = expires.astimezone(sgt_timezone)
        st.markdown(f"""
        <div style="background: #fff3cd; padding: 12px; border-radius: 8px; text-align: center; margin-bottom: 20px; color: #1a1a1a;">
            <strong>🔑 Access Valid Until:</strong> {expires_sgt.strftime('%d %b %Y, %I:%M %p')} (SG Time)
        </div>
        """, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Error displaying expiry: {e}")

    if not DB_CONNECTED:
        st.error("Database not connected")
        return

    # Activity selection
    st.subheader("📅 Step 1: Select Activity")
    acts = load_activities()
    act_names = [a['name'] for a in acts] if acts else ["Cardio Drumming"]
    default_index = act_names.index(activity_param) if activity_param and activity_param in act_names else 0
    selected_activity = st.selectbox("Choose Activity", act_names, index=default_index, key="portal_activity")
    selected_date = st.date_input("Date", value=datetime.now().date(), key="portal_date")
    
    act_config = next((a for a in acts if a['name'] == selected_activity), None)
    
    # 🔥 Dynamic sessions (1-4)
    session_labels = []
    if act_config:
        for i in range(1, 5):
            lbl = (act_config.get(f'session_{i}_label') or '').strip()
            if lbl:
                session_labels.append(lbl)
    if not session_labels:
        session_labels = ['Session 1']

    st.subheader("⏰ Step 2: Select Session")
    if len(session_labels) == 1:
        st.info(f"ℹ️ This activity has only one session: {session_labels[0]}")
        flags = [True]
    else:
        session_option = st.radio("Which session(s)?", ["All Sessions"] + session_labels, horizontal=True, key="portal_session")
        flags = [(session_option == "All Sessions") or (session_option == lbl) for lbl in session_labels]
    flags = (flags + [False, False, False, False])[:4]
    s1, s2, s3, s4 = flags

    # Show session time info if available (🔥 Dynamically checks up to 4 sessions)
    if act_config:
        time_info = []
        for i in range(1, 5):
            lbl = act_config.get(f'session_{i}_label', '')
            start = act_config.get(f'session_{i}_start_time', '')
            end = act_config.get(f'session_{i}_end_time', '')
            if lbl and start and end:
                time_info.append(f"🕐 {lbl}: {start} - {end}")
        
        if time_info:
            st.markdown('<div class="time-info-box">', unsafe_allow_html=True)
            st.markdown("📋 **Session Times:**")
            for info in time_info:
                st.markdown(f"- {info}")
            st.markdown('</div>', unsafe_allow_html=True)

    st.divider()
    st.subheader("📱 Step 3: Choose Check-In Method")
    method = st.radio("How would you like to check in residents?", ["📸 Scan QR Code (Camera)", "⌨️ Phone / Name Search", "📝 Register New Resident"], horizontal=False, key="portal_method")

    if method == "📸 Scan QR Code (Camera)":
        st.markdown("""
        <div class="method-card">
            <h3>📸 Scan QR Code</h3>
            <p style="font-size: 15px; font-weight: 500;">Use your camera to scan the resident's QR code instantly.</p>
            <div style="background: #e3f2fd; padding: 15px; border-radius: 8px; margin: 15px 0; color: #1a1a1a;">
                <strong>📱 How it works:</strong> Click "Take Photo" to open your camera. Position the QR code within the frame and capture.<br>
                <span style="font-size: 14px; color: #666;">✅ Works reliably on both iOS and Android devices.</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        if st.session_state.get('checkin_success', False):
            st.session_state.checkin_success = False
            st.rerun()
        
        st.markdown("""
        <div class="qr-scanner-container">
            <h4 style="color: #667eea; margin-top: 0;">📸 Camera Scanner</h4>
            <p style="color: #666; font-size: 14px;">Take a photo of the QR code to scan it</p>
        </div>
        """, unsafe_allow_html=True)
        
        camera_image = st.camera_input(
            "📸 Position the QR code in the frame and click capture", 
            key="qr_camera",
            disabled=False,
            label_visibility="visible"
        )
        
        if camera_image is not None:
            try:
                image = Image.open(camera_image)
                st.image(image, caption="📸 Captured Image", width=None, use_container_width=True)
                
                with st.spinner("🔍 Scanning QR code..."):
                    qr_data = decode_qr_from_image(image)
                
                if qr_data:
                    st.markdown('<div class="status-success">✅ QR Code detected successfully!</div>', unsafe_allow_html=True)
                    with st.expander("📋 View QR Data"):
                        st.code(qr_data, language="text")
                    
                    extracted_pid = qr_data
                    if 'pid=' in qr_data:
                        try:
                            parsed_url = urllib.parse.urlparse(qr_data)
                            query_params = urllib.parse.parse_qs(parsed_url.query)
                            extracted_pid = query_params.get('pid', [None])[0]
                        except: pass
                    
                    if extracted_pid and len(str(extracted_pid)) > 5:
                        try:
                            resident = supabase.table('participants').select("*").eq('id', extracted_pid).execute()
                            if resident.data:
                                resident_name = resident.data[0]['name']
                                resident_type = "🆕 New" if resident.data[0].get('is_new') else "⭐ Regular"
                                col1, col2 = st.columns([3, 1])
                                with col1:
                                    st.info(f"👤 **Resident:** {resident_name}\n\n📋 **Status:** {resident_type}")
                                with col2:
                                    if st.button("✅ Check In Now", type="primary", use_container_width=True, key="checkin_btn"):
                                        with st.spinner("Processing check-in..."):
                                            # 🔥 Pass s1, s2, s3, s4
                                            success, message, _ = AttendanceService.process_checkin(extracted_pid, selected_date, selected_activity, s1, s2, s3, s4)
                                            if success:
                                                st.rerun()
                            else:
                                st.markdown('<div class="status-error">❌ Resident not found in database. Please check the QR code.</div>', unsafe_allow_html=True)
                        except Exception as e:
                            st.error(f"Error finding resident: {e}")
                    else:
                        st.markdown('<div class="status-error">❌ Invalid QR code format. Could not extract resident ID.</div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="status-error">❌ No QR code detected. Please try again with a clear image.</div>', unsafe_allow_html=True)
                    with st.expander("💡 Tips for better scanning"):
                        st.markdown("""
                        - **💡 Ensure good lighting** - Avoid shadows or glare on the QR code
                        - **📱 Hold steady** - Keep the camera still when taking the photo
                        - **📏 Proper distance** - QR code should fill about 30-50% of the frame
                        - **🎯 Focus** - Tap the screen to focus on the QR code
                        """)
            except Exception as e:
                st.error(f"Error processing image: {e}")
                st.info("Please try taking another photo.")
        else:
            st.markdown("""
            <div style="text-align: center; color: #666; padding: 10px;">
                <span style="font-size: 14px;">📷 Ready for next scan. Take a photo to continue.</span>
            </div>
            """, unsafe_allow_html=True)
        
        st.divider()
        st.markdown("<p style='color: #1a1a1a !important; font-weight: bold; margin-bottom: 5px;'>⌨️ Or enter manually:</p>", unsafe_allow_html=True)
        
        if 'clear_manual_qr' not in st.session_state:
            st.session_state.clear_manual_qr = False
            
        qr_input_value = ""
        if st.session_state.get('clear_manual_qr'):
            qr_input_value = ""
            st.session_state.clear_manual_qr = False
        else:
            qr_input_value = st.session_state.get('portal_qr_input', '')
            
        qr_input = st.text_input(
            "Enter QR Code ID", 
            placeholder="e.g., 2026080316562190", 
            value=qr_input_value,
            key="portal_qr_input"
        )
        
        if qr_input and len(qr_input.strip()) > 5:
            input_text = qr_input.strip()
            extracted_pid = input_text
            if 'pid=' in input_text:
                try:
                    parsed_url = urllib.parse.urlparse(input_text)
                    query_params = urllib.parse.parse_qs(parsed_url.query)
                    extracted_pid = query_params.get('pid', [None])[0]
                except: pass
            if extracted_pid and len(str(extracted_pid)) > 5:
                # 🔥 Pass s1, s2, s3, s4
                success = process_portal_checkin(extracted_pid, selected_date, selected_activity, s1, s2, s3, s4)
                if success:
                    st.session_state.clear_manual_qr = True
                    st.rerun()

    elif method == "⌨️ Phone / Name Search":
        st.markdown("""
        <div class="method-card">
            <h3>⌨️ Smart Resident Browser</h3>
            <p style="font-size: 15px; font-weight: 500;">Search by Phone, Name, or ID. Filter by activity to find the right person.</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("**📞 Quick Phone Check-In**")
        phone_input = st.text_input("Enter 8-digit mobile number", placeholder="e.g., 91234567", key="portal_phone")
        if phone_input and len(clean_phone_number(phone_input)) >= 8:
            clean_phone = clean_phone_number(phone_input)
            resident = find_participant_by_phone(clean_phone)
            if resident:
                status_text = '⭐ Regular' if not resident.get('is_new') else '🆕 New'
                st.success(f"✅ **Resident Found:** {resident['name']} ({status_text})")
                if st.button("✅ Check In (Phone)", type="primary", use_container_width=True, key="portal_checkin_phone"):
                    with st.spinner("Processing check-in..."):
                        # 🔥 Pass s1, s2, s3, s4
                        success, message, _ = AttendanceService.process_checkin(resident['id'], selected_date, selected_activity, s1, s2, s3, s4)
                        if success:
                            st.rerun()
            else:
                st.info("📱 Phone number not found. Try searching by name below.")

        st.divider()
        st.markdown("**🔍 Browse Residents**")
        
        browse_mode = st.radio(
            "Select mode:",
            ["🔎 Search by Name or ID", "📋 Show All (All Active Residents)"],
            horizontal=True,
            key="portal_browse_mode"
        )
        
        try:
            fresh_participants = supabase.table('participants').select("*").eq('active', True).execute().data
        except:
            fresh_participants = []
        
        filtered_participants = []
        
        if browse_mode == "🔎 Search by Name or ID":
            name_search = st.text_input("Type Name or ID...", placeholder="e.g., AHMAD, 2026", key="portal_name_search")
            if name_search:
                s = name_search.lower()
                filtered_participants = [
                    p for p in fresh_participants 
                    if s in p['name'].lower() or s in p['id'].lower()
                ]
            else:
                filtered_participants = []
        else:
            st.caption(f"Showing ALL active residents in the system.")
            filtered_participants = fresh_participants
        
        try:
            att_data = supabase.table('attendance').select('participant_id').eq('source', selected_activity).execute().data
            activity_attendees = {rec['participant_id'] for rec in att_data}
        except:
            activity_attendees = set()
            
        sort_az = st.checkbox("📋 Sort A–Z (Alphabetical)", value=False, key="portal_sort_az")
        
        if sort_az:
            filtered_participants.sort(key=lambda p: p['name'].lower())
        else:
            filtered_participants.sort(key=lambda p: p['id'] in activity_attendees, reverse=True)
        
        if not filtered_participants:
            st.info("No residents found matching your search.")
        else:
            st.caption(f"Showing {len(filtered_participants)} resident(s). Tap the button to check in.")
            for p in filtered_participants:
                is_regular = p['id'] in activity_attendees
                badge = "⭐ Regular" if is_regular else "🆕 New"
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**{p['name']}**")
                    st.caption(f"ID: {p['id'][:8]}... | {badge}")
                with col2:
                    if st.button(f"✅ Check In", key=f"portal_name_check_{p['id']}", use_container_width=True):
                        with st.spinner("Processing..."):
                            # 🔥 Pass s1, s2, s3, s4
                            success = process_portal_checkin(p['id'], selected_date, selected_activity, s1, s2, s3, s4)
                            if success:
                                st.rerun()

    elif method == "📝 Register New Resident":
        st.markdown("""
        <div class="method-card">
            <h3>📝 Register New Resident</h3>
            <p style="font-size: 15px; font-weight: 500;">Register first-time participants and automatically check them in.</p>
        </div>
        """, unsafe_allow_html=True)
        
        name = st.text_input("Full Name *", placeholder="e.g., AHMAD BIN ISMAIL", key="portal_reg_name")
        contact = st.text_input("Contact Number", placeholder="e.g., 91234567", key="portal_reg_contact")
        no_phone = st.checkbox("👴 I do not have a phone", key="portal_reg_no_phone")
        indemnity = st.checkbox("Indemnity Form Signed (Optional)", value=False, key="portal_reg_indemnity")
        
        st.markdown("---")
        st.markdown("**👤 Member Type:**")
        member_type = st.radio("Select member category:", ["Resident", "RN Member", "Volunteer Member", "Gardener"], horizontal=True, key="portal_reg_member_type", help="RN Member = Resident Network Committee | Volunteer Member = Activity Volunteer")
        
        block_consent = st.checkbox("🏢 I agree to share my block information (Optional)", key="portal_reg_block_consent")
        block_no = ""
        if block_consent: 
            block_no = st.text_input("Block No.", placeholder="e.g., 622, 624A", key="portal_reg_block_no").strip().upper()
        
        if st.button("Register & Check In", type="primary", use_container_width=True, key="portal_reg_submit"):
            if not name.strip(): 
                st.error("❌ Name is required")
            elif not no_phone and not contact.strip(): 
                st.error("❌ Contact number is required")
            else:
                final_contact = "NO_PHONE" if no_phone else contact.strip()
                clean_contact = clean_phone_number(final_contact) if final_contact != "NO_PHONE" else None
                try:
                    if clean_contact and clean_contact != "NO_PHONE":
                        res_phone = supabase.table('participants').select('name').eq('contact', clean_contact).eq('active', True).execute()
                        if res_phone.data: 
                            st.error(f"⛔ **Phone number already exists!**\n\nResident: **{res_phone.data[0]['name']}**")
                            st.stop()
                    res_name = supabase.table('participants').select('name', 'contact').eq('name', name.strip().upper()).eq('active', True).execute()
                    if res_name.data: 
                        st.error(f"⛔ **Name already exists!**")
                        st.stop()
                except Exception as e: 
                    st.error(f"Error checking for duplicates: {e}")
                    st.stop()
                
                try:
                    success, message, new_id = RegistrationService.register_resident(
                        name=name,
                        contact=contact,
                        no_phone=no_phone,
                        indemnity=indemnity,
                        member_type=member_type,
                        block_no=block_no
                    )
                    if success:
                        # Then check them in
                        success2, msg2, _ = AttendanceService.process_checkin(new_id, selected_date, selected_activity, s1, s2, s3, s4)
                        if success2:
                            st.success(f"✅ {name.strip().upper()} registered & checked in successfully!")
                            st.info(f"Resident ID: `{new_id}`")
                            st.rerun()
                except Exception as e: 
                    st.error(f"Registration failed: {e}")

    # Statistics
    st.divider()
    st.subheader("📊 Today's Statistics")
    try:
        today_str = str(selected_date)
        today_attendance = supabase.table('attendance').select("*").eq('date', today_str).eq('source', selected_activity).execute().data
        total_checked_in = len(today_attendance) if today_attendance else 0
        today_registrations = supabase.table('participants').select("*").eq('registration_date', today_str).eq('is_new', True).execute().data
        total_new = len(today_registrations) if today_registrations else 0
        st.markdown(f"""
        <div class="stats-box">
            <h3 style="margin: 0 0 10px 0; color: #1a1a1a;">📅 {selected_date.strftime('%d %B %Y')}</h3>
            <div style="display: flex; justify-content: space-around;">
                <div><div style="font-size: 32px; font-weight: bold; color: #667eea;">{total_checked_in}</div><div style="font-size: 14px; color: #666;">Checked In</div></div>
                <div><div style="font-size: 32px; font-weight: bold; color: #4CAF50;">{total_new}</div><div style="font-size: 14px; color: #666;">New Registrations</div></div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    except Exception as e: 
        st.error(f"Error loading stats: {e}")
    
    st.caption("Woodlands Zone 6 Community Hub | Volunteer Portal | Token-based access")