import streamlit as st
import random
from datetime import datetime, timedelta, timezone
from config import supabase, DB_CONNECTED, load_activities, refresh_data, APP_URL
from utils import clean_phone_number, find_participant_by_phone, check_returning_guest, mask_phone
import urllib.parse
import base64
import os
from PIL import Image
import cv2
import numpy as np
import io

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

def decode_qr_from_image(image):
    """Decode QR code from PIL Image using OpenCV"""
    try:
        # Convert PIL Image to numpy array
        img_array = np.array(image)
        
        # Convert to grayscale
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        
        # Initialize QRCode detector
        qr_detector = cv2.QRCodeDetector()
        
        # Detect and decode QR code
        data, bbox, _ = qr_detector.detectAndDecode(gray)
        
        if data:
            return data
        return None
    except Exception as e:
        print(f"Error decoding QR: {e}")
        return None

def show_volunteer_portal(token, activity_param=None):
    """UNIFIED VOLUNTEER PORTAL WITH RELIABLE QR SCANNING"""
    from tab_volunteer_access import validate_volunteer_token
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
    .qr-scanner-container .camera-wrapper { max-width: 500px; margin: 0 auto; }
    .qr-scanner-container .camera-wrapper video { border-radius: 10px; width: 100% !important; }
    .status-success { background: #d4edda; color: #155724; padding: 15px; border-radius: 8px; border: 2px solid #28a745; }
    .status-error { background: #f8d7da; color: #721c24; padding: 15px; border-radius: 8px; border: 2px solid #dc3545; }
    .status-info { background: #d1ecf1; color: #0c5460; padding: 15px; border-radius: 8px; border: 2px solid #17a2b8; }
    @media (max-width: 768px) {
        .portal-header-card { padding: 20px 15px; margin: 0 10px 25px 10px; }
        .portal-header-card h2 { font-size: 24px; }
        .method-card { padding: 20px 15px; }
        .qr-scanner-container { padding: 15px; }
    }
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
    s1_label = act_config.get('session_1_label', 'Session 1') if act_config else 'Session 1'
    s2_label = act_config.get('session_2_label', 'Session 2') if act_config else 'Session 2'
    has_s2 = bool(s2_label and s2_label.strip())

    st.subheader("⏰ Step 2: Select Session")
    if has_s2:
        session_option = st.radio("Which session(s)?", ["Both", s1_label, s2_label], horizontal=True, key="portal_session")
        s1 = session_option in ["Both", s1_label]
        s2 = session_option in ["Both", s2_label]
    else:
        st.info(f"ℹ️ This activity has only one session: {s1_label}")
        s1, s2 = True, False

    st.divider()
    st.subheader("📱 Step 3: Choose Check-In Method")
    method = st.radio("How would you like to check in residents?", ["📸 Scan QR Code (Camera)", "⌨️ Phone Number Search", "📝 Register New Resident"], horizontal=False, key="portal_method")

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
        
        # QR Scanner using st.camera_input (RELIABLE!)
        st.markdown("""
        <div class="qr-scanner-container">
            <h4 style="color: #667eea; margin-top: 0;">📸 Camera Scanner</h4>
            <p style="color: #666; font-size: 14px;">Take a photo of the QR code to scan it</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Use the native camera input - THIS WORKS ON MOBILE!
        camera_image = st.camera_input("📸 Position the QR code in the frame and click capture", key="qr_camera")
        
        if camera_image is not None:
            try:
                # Convert to PIL Image
                image = Image.open(camera_image)
                
                # Show preview
                st.image(image, caption="Captured Image", use_column_width=True)
                
                # Decode QR code
                with st.spinner("🔍 Scanning QR code..."):
                    qr_data = decode_qr_from_image(image)
                
                if qr_data:
                    st.markdown(f'<div class="status-success">✅ QR Code detected: <code>{qr_data}</code></div>', unsafe_allow_html=True)
                    
                    # Process the QR code
                    extracted_pid = qr_data
                    if 'pid=' in qr_data:
                        try:
                            parsed_url = urllib.parse.urlparse(qr_data)
                            query_params = urllib.parse.parse_qs(parsed_url.query)
                            extracted_pid = query_params.get('pid', [None])[0]
                        except: 
                            pass
                    
                    if extracted_pid and len(str(extracted_pid)) > 5:
                        # Show resident info and check-in button
                        try:
                            resident = supabase.table('participants').select("*").eq('id', extracted_pid).execute()
                            if resident.data:
                                resident_name = resident.data[0]['name']
                                st.info(f"👤 Resident: **{resident_name}**")
                                
                                if st.button("✅ Check In This Resident", type="primary", use_container_width=True):
                                    process_portal_checkin(extracted_pid, selected_date, selected_activity, s1, s2)
                                    # Clear the camera input after processing
                                    st.rerun()
                            else:
                                st.error("❌ Resident not found in database")
                        except Exception as e:
                            st.error(f"Error finding resident: {e}")
                    else:
                        st.error("❌ Invalid QR code format. Could not extract resident ID.")
                else:
                    st.markdown('<div class="status-error">❌ No QR code detected. Please try again with a clear image.</div>', unsafe_allow_html=True)
                    st.info("💡 Tips:\n- Ensure the QR code is well-lit\n- Hold the camera steady\n- Make sure the QR code is fully visible in the frame")
                    
            except Exception as e:
                st.error(f"Error processing image: {e}")
        
        st.divider()
        st.markdown("<p style='color: #1a1a1a !important; font-weight: bold; margin-bottom: 5px;'>Or enter manually:</p>", unsafe_allow_html=True)
        qr_input = st.text_input("Enter QR Code ID", placeholder="e.g., 2026080316562190", key="portal_qr_input")
        
        if qr_input and len(qr_input.strip()) > 5:
            input_text = qr_input.strip()
            extracted_pid = input_text
            if 'pid=' in input_text:
                try:
                    parsed_url = urllib.parse.urlparse(input_text)
                    query_params = urllib.parse.parse_qs(parsed_url.query)
                    extracted_pid = query_params.get('pid', [None])[0]
                except: 
                    pass
            if extracted_pid and len(str(extracted_pid)) > 5:
                process_portal_checkin(extracted_pid, selected_date, selected_activity, s1, s2)

    elif method == "⌨️ Phone Number Search":
        st.markdown("""
        <div class="method-card">
            <h3>⌨️ Phone Number Search</h3>
            <p style="font-size: 15px; font-weight: 500;">Enter the resident's 8-digit mobile number to find and check them in.</p>
        </div>
        """, unsafe_allow_html=True)
        phone_input = st.text_input("Mobile Number", placeholder="e.g., 91234567", key="portal_phone")
        if phone_input and len(clean_phone_number(phone_input)) >= 8:
            clean_phone = clean_phone_number(phone_input)
            resident = find_participant_by_phone(clean_phone)
            if resident:
                status_text = '⭐ Regular' if not resident.get('is_new') else '🆕 New'
                st.success(f"✅ **Resident Found:** {resident['name']} ({status_text})")
                if st.button("✅ Check In", type="primary", use_container_width=True, key="portal_checkin_phone"):
                    try:
                        existing_att = supabase.table('attendance').select('id').eq('participant_id', resident['id']).eq('date', str(selected_date)).execute()
                        if existing_att.data:
                            supabase.table('attendance').update({"session_1": s1, "session_2": s2, "timestamp": datetime.now(timezone.utc).isoformat(), "source": selected_activity}).eq('id', existing_att.data[0]['id']).execute()
                        else:
                            supabase.table('attendance').insert({"participant_id": resident['id'], "name": resident['name'], "date": str(selected_date), "session_1": s1, "session_2": s2, "timestamp": datetime.now(timezone.utc).isoformat(), "self_checkin": False, "source": selected_activity}).execute()
                        st.success(f"✅ {resident['name']} checked in successfully!")
                        refresh_data()
                        st.rerun()
                    except Exception as e: 
                        st.error(f"Error: {e}")
            else:
                st.warning("📱 Phone number not found. Would you like to register them?")
                if st.button("📝 Register New Resident", key="portal_register_from_phone"):
                    st.session_state.portal_action = "register_new"
                    st.rerun()

    elif method == "📝 Register New Resident":
        st.markdown("""
        <div class="method-card">
            <h3>📝 Register New Resident</h3>
            <p style="font-size: 15px; font-weight: 500;">Register first-time participants and automatically check them in.</p>
        </div>
        """, unsafe_allow_html=True)
        with st.form("portal_register_form", clear_on_submit=True):
            name = st.text_input("Full Name *", placeholder="e.g., AHMAD BIN ISMAIL")
            contact = st.text_input("Contact Number", placeholder="e.g., 91234567")
            no_phone = st.checkbox("👴 I do not have a phone")
            indemnity = st.checkbox("Indemnity Form Signed (Optional)", value=False)
            st.markdown("---")
            st.markdown("**👤 Member Type:**")
            member_type = st.radio("Select member category:", ["Resident", "RN Member", "Volunteer Member"], horizontal=True, key="portal_member_type", help="RN Member = Resident Network Committee | Volunteer Member = Activity Volunteer")
            block_consent = st.checkbox("🏢 I agree to share my block information (Optional)", key="portal_block_consent")
            block_no = ""
            if block_consent: 
                block_no = st.text_input("Block No.", placeholder="e.g., 622, 624A", key="portal_block_no").strip().upper()
            
            if st.form_submit_button("Register & Check In", type="primary", use_container_width=True):
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
                        new_id = datetime.now().strftime("%Y%m%d%H%M%S") + str(random.randint(10, 99))
                        supabase.table('participants').insert({
                            "id": new_id, 
                            "name": name.strip().upper(), 
                            "contact": final_contact,
                            "block_no": block_no if block_no else None, 
                            "indemnity": indemnity,
                            "is_new": True, 
                            "active": True, 
                            "registration_date": datetime.now().strftime("%Y-%m-%d"),
                            "member_type": member_type
                        }).execute()
                        process_portal_checkin(new_id, selected_date, selected_activity, s1, s2)
                        st.success(f"✅ {name.strip().upper()} registered as **{member_type}** & checked in successfully!")
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

def process_portal_checkin(pid, date, activity, s1, s2):
    """Process check-in for portal - WITH TIME VALIDATION"""
    try:
        # 🔥 TIME VALIDATION (The "Bouncer")
        from utils import validate_checkin_time
        
        # Determine which session is being checked in
        session_to_check = 1 if s1 else 2
        
        is_allowed, message = validate_checkin_time(activity, session_to_check)
        
        if not is_allowed:
            st.error(message)
            st.info("💡 If this is incorrect, please contact the admin to adjust the session times or disable time validation.")
            return
        
        existing = supabase.table('attendance').select("*").eq('participant_id', pid).eq('date', str(date)).eq('source', activity).execute()
        
        if existing.data and len(existing.data) > 0:
            st.warning(f"⚠️ This person has already checked in today for {activity}!")
            return
        
        res = supabase.table('participants').select("*").eq('id', pid).execute()
        if not res.data:
            st.error(f"❌ Resident ID not found: {pid}")
            return
        
        resident = res.data[0]
        supabase.table('attendance').insert({
            "participant_id": pid, "name": resident['name'], "date": str(date),
            "session_1": s1, "session_2": s2, "timestamp": datetime.now(timezone.utc).isoformat(),
            "self_checkin": False, "source": activity
        }).execute()
        refresh_data()
        st.success(f"✅ Successfully checked in **{resident['name']}**!")
    except Exception as e:
        error_msg = str(e)
        if 'duplicate key' in error_msg or 'idx_attendance_unique' in error_msg:
            st.info("ℹ️ This person has already checked in today. (Duplicate prevented)")
        else:
            st.error(f"Error: {e}")