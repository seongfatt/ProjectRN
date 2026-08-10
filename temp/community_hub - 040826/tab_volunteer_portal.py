import streamlit as st
import random
from datetime import datetime, timedelta, timezone
from config import supabase, DB_CONNECTED, load_activities, refresh_data, APP_URL
from utils import clean_phone_number, find_participant_by_phone, check_returning_guest, mask_phone
import urllib.parse
import base64
import os


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
    # Fallback: purple square with "WZ6" text
    return (
        "data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+"
        "PHJlY3Qgd2lkdGg9IjYwIiBoZWlnaHQ9IjYwIiBmaWxsPSIjNjY3ZWVhIiByeD0iMTAiLz48dGV4dCB4PSI1MCUiIHk9"
        "IjUwJSIgZG9taW5hbnQtYmFzZWxpbmU9Im1pZGRsZSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZmlsbD0id2hpdGUiIGZvbnQt"
        "ZmFtaWx5PSJBcmlhbCIgZm9udC1zaXplPSIxNCIgZm9udC13ZWlnaHQ9ImJvbGQiPldaNjwvdGV4dD48L3N2Zz4="
    )


def show_volunteer_portal(token, activity_param=None):
    """
    UNIFIED VOLUNTEER PORTAL
    """

    # Validate token
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

    # ──────────────────────────────────────────────────
    # CSS STYLING
    # ──────────────────────────────────────────────────
    st.markdown("""
    <style>
    .portal-header-card {
        background: #ffffff;
        color: #1a1a1a;
        border-radius: 20px;
        padding: 30px 24px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.12);
        max-width: 600px;
        margin: 0 auto 25px auto;
        text-align: center;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    .portal-header-card .header-row {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 15px;
        margin-bottom: 20px;
    }
    .portal-header-card .header-row img {
        width: 60px;
        height: 60px;
        object-fit: contain;
        background: #f8f9fa;
        border-radius: 10px;
        padding: 5px;
        flex-shrink: 0;
    }
    .portal-header-card .title-group {
        text-align: left;
    }
    .portal-header-card .title-group h1 {
        color: #667eea;
        margin: 0;
        font-size: 24px;
        font-weight: 800;
        line-height: 1.1;
    }
    .portal-header-card .title-group p {
        color: #666;
        margin: 2px 0 0 0;
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .portal-header-card .divider {
        border: 0;
        border-top: 2px solid #eee;
        margin: 20px 0;
    }
    .portal-header-card h2 {
        margin: 10px 0 5px 0;
        font-size: 28px;
        font-weight: bold;
        color: #1a1a1a;
        letter-spacing: 1px;
    }
    .portal-header-card .subtitle {
        margin: 0;
        font-size: 16px;
        color: #555;
        font-weight: 500;
    }

    .method-card {
        background: white;
        border-radius: 12px;
        padding: 25px;
        margin: 15px 0;
        box-shadow: 0 2px 10px rgba(0,0,0,0.08);
        border-left: 5px solid #667eea;
    }
    .method-card h3 { margin-top: 0; color: #667eea; }

    .stats-box {
        background: #e3f2fd;
        padding: 15px;
        border-radius: 10px;
        margin: 20px 0;
        text-align: center;
    }

    #reader {
        width: 100%;
        max-width: 500px;
        margin: 0 auto;
        border-radius: 10px;
        overflow: hidden;
    }
    .scanner-container {
        background: white;
        padding: 20px;
        border-radius: 15px;
        margin: 20px 0;
        text-align: center;
    }
    </style>

    <script src="https://unpkg.com/html5-qrcode" type="text/javascript"></script>
    <script>
    let html5QrCode;
    let isScanning = false;

    function startScanner() {
        if (isScanning) return;
        html5QrCode = new Html5Qrcode("reader");
        Html5Qrcode.getCameras().then(cameras => {
            if (cameras && cameras.length) {
                const cameraId = cameras.length > 1 ? cameras[1].id : cameras[0].id;
                html5QrCode.start(cameraId, { fps: 10, qrbox: { width: 250, height: 250 } }, onScanSuccess, onScanFailure)
                .then(() => { isScanning = true; })
                .catch(err => { console.error("Unable to start scanning", err); });
            }
        }).catch(err => { console.error("Unable to get cameras", err); });
    }

    function stopScanner() {
        if (html5QrCode && isScanning) {
            html5QrCode.stop().then(() => { isScanning = false; })
            .catch(err => { console.error("Unable to stop scanning", err); });
        }
    }

    function onScanSuccess(decodedText, decodedResult) {
        const input = document.getElementById('portal_qr_input');
        if (input) {
            input.value = decodedText;
            input.dispatchEvent(new Event('input', { bubbles: true }));
        }
        stopScanner();
    }

    function onScanFailure(error) {
        console.warn(`Code scan error = ${error}`);
    }
    </script>
    """, unsafe_allow_html=True)

    # ──────────────────────────────────────────────────
    # WHITE HEADER CARD (logo embedded as base64)
    # ──────────────────────────────────────────────────
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

    # Show token expiry info in SINGAPORE TIME
    try:
        token_data = supabase.table('volunteer_tokens').select("*").eq('token', token).single().execute().data
        expires_str = token_data['expires_at']

        if expires_str.endswith('Z'):
            expires_str = expires_str.replace('Z', '+00:00')

        expires = datetime.fromisoformat(expires_str)
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)

        sgt_timezone = timezone(timedelta(hours=8))
        expires_sgt = expires.astimezone(sgt_timezone)
        expires_display = expires_sgt.strftime("%d %b %Y, %I:%M %p")

        st.markdown(f"""
        <div style="background: #fff3cd; padding: 12px; border-radius: 8px; text-align: center; margin-bottom: 20px; color: #1a1a1a;">
            <strong>⏰ Access Valid Until:</strong> {expires_display} (SG Time)
        </div>
        """, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Error displaying expiry: {e}")

    if not DB_CONNECTED:
        st.error("Database not connected")
        return

    # ──────────────────────────────────────────────────
    # STEP 1: SELECT ACTIVITY
    # ──────────────────────────────────────────────────
    st.subheader("📅 Step 1: Select Activity")

    acts = load_activities()
    act_names = [a['name'] for a in acts] if acts else ["Cardio Drumming"]

    default_index = 0
    if activity_param and activity_param in act_names:
        default_index = act_names.index(activity_param)

    selected_activity = st.selectbox("Choose Activity", act_names, index=default_index, key="portal_activity")
    selected_date = st.date_input("Date", value=datetime.now().date(), key="portal_date")

    act_config = next((a for a in acts if a['name'] == selected_activity), None)
    s1_label = act_config.get('session_1_label', 'Session 1') if act_config else 'Session 1'
    s2_label = act_config.get('session_2_label', 'Session 2') if act_config else 'Session 2'
    has_s2 = bool(s2_label and s2_label.strip())

    st.subheader("🕐 Step 2: Select Session")
    if has_s2:
        session_option = st.radio("Which session(s)?", ["Both", s1_label, s2_label], horizontal=True, key="portal_session")
        s1 = session_option in ["Both", s1_label]
        s2 = session_option in ["Both", s2_label]
    else:
        st.info(f"ℹ️ This activity has only one session: {s1_label}")
        s1, s2 = True, False

    st.divider()

    # ───────────────────────────────────────────────────
    # STEP 3: CHOOSE CHECK-IN METHOD
    # ───────────────────────────────────────────────────
    st.subheader("📱 Step 3: Choose Check-In Method")

    method = st.radio(
        "How would you like to check in residents?",
        ["📱 Scan QR Code (Manual ID)", "⌨️ Phone Number Search", "📝 Register New Resident"],
        horizontal=False,
        key="portal_method"
    )

    # ───────────────────────────────────────────────────
    # METHOD 1: QR CODE SCANNER
    # ───────────────────────────────────────────────────
    if method == "📱 Scan QR Code (Manual ID)":
        st.markdown("""
        <div class="method-card">
            <h3>📱 Scan QR Code</h3>
            <p>Enter the ID from the resident's QR code card for instant check-in.</p>
        </div>
        """, unsafe_allow_html=True)

        qr_input = st.text_input("Enter QR Code ID", placeholder="e.g., 2026080316562190", key="portal_qr_input")

        if qr_input and len(qr_input.strip()) > 5:
            input_text = qr_input.strip()
            if 'pid=' in input_text:
                try:
                    parsed_url = urllib.parse.urlparse(input_text)
                    query_params = urllib.parse.parse_qs(parsed_url.query)
                    extracted_pid = query_params.get('pid', [None])[0]
                    if extracted_pid:
                        process_portal_checkin(extracted_pid, selected_date, selected_activity, s1, s2)
                except Exception as e:
                    st.error(f"Error parsing URL: {e}")
            else:
                process_portal_checkin(input_text, selected_date, selected_activity, s1, s2)

    # ───────────────────────────────────────────────────
    # METHOD 2: PHONE NUMBER SEARCH
    # ───────────────────────────────────────────────────
    elif method == "⌨️ Phone Number Search":
        st.markdown("""
        <div class="method-card">
            <h3>⌨️ Phone Number Search</h3>
            <p>Enter the resident's 8-digit mobile number to find and check them in.</p>
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
                            supabase.table('attendance').update({
                                "session_1": s1, "session_2": s2,
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "source": selected_activity
                            }).eq('id', existing_att.data[0]['id']).execute()
                        else:
                            supabase.table('attendance').insert({
                                "participant_id": resident['id'], "name": resident['name'],
                                "date": str(selected_date), "session_1": s1, "session_2": s2,
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "self_checkin": False, "source": selected_activity
                            }).execute()

                        st.success(f"✅ {resident['name']} checked in successfully!")
                        refresh_data()
                    except Exception as e:
                        st.error(f"Error: {e}")
            else:
                st.warning("📱 Phone number not found. Would you like to register them?")
                if st.button("📝 Register New Resident", key="portal_register_from_phone"):
                    st.session_state.portal_action = "register_new"

    # ──────────────────────────────────────────────────
    # METHOD 3: REGISTER NEW RESIDENT
    # ──────────────────────────────────────────────────
    elif method == "📝 Register New Resident":
        st.markdown("""
        <div class="method-card">
            <h3>📝 Register New Resident</h3>
            <p>Register first-time participants and automatically check them in.</p>
        </div>
        """, unsafe_allow_html=True)

        with st.form("portal_register_form", clear_on_submit=True):
            name = st.text_input("Full Name *", placeholder="e.g., AHMAD BIN ISMAIL")
            contact = st.text_input("Contact Number", placeholder="e.g., 91234567")
            no_phone = st.checkbox("👴 I do not have a phone")
            indemnity = st.checkbox("Indemnity Form Signed (Optional)", value=False)

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
                            "id": new_id, "name": name.strip().upper(), "contact": final_contact,
                            "block_no": block_no if block_no else None, "indemnity": indemnity,
                            "is_new": True, "active": True, "registration_date": datetime.now().strftime("%Y-%m-%d")
                        }).execute()

                        supabase.table('attendance').insert({
                            "participant_id": new_id, "name": name.strip().upper(),
                            "date": str(selected_date), "session_1": s1, "session_2": s2,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "self_checkin": False, "source": selected_activity
                        }).execute()

                        refresh_data()
                        st.success(f"✅ {name.strip().upper()} registered & checked in successfully!")
                        st.info(f"Resident ID: `{new_id}`")
                    except Exception as e:
                        st.error(f"Registration failed: {e}")

    # ──────────────────────────────────────────────────
    # TODAY'S STATS
    # ───────────────────────────────────────────────────
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
                <div>
                    <div style="font-size: 32px; font-weight: bold; color: #667eea;">{total_checked_in}</div>
                    <div style="font-size: 14px; color: #666;">Checked In</div>
                </div>
                <div>
                    <div style="font-size: 32px; font-weight: bold; color: #4CAF50;">{total_new}</div>
                    <div style="font-size: 14px; color: #666;">New Registrations</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Error loading stats: {e}")

    st.caption("Woodlands Zone 6 Community Hub | Volunteer Portal | Token-based access")


def process_portal_checkin(pid, date, activity, s1, s2):
    """Process check-in for portal"""
    try:
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