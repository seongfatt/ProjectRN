import streamlit as st
import urllib.parse
import base64
import os
from datetime import datetime, timedelta, timezone
from config import supabase, APP_URL, load_activities
from utils import clean_phone_number, mask_phone, validate_checkin_time

# Try to import AttendanceService for robust check-in logic
try:
    from services import AttendanceService
except ImportError:
    AttendanceService = None

# 🔒 Hide sidebar + header for resident-facing page
st.set_page_config(
    page_title="Your QR Code",
    page_icon="logo.png",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ✅ Hide Streamlit UI elements + Sidebar via CSS
hide_streamlit_style = """
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    [data-testid="stSidebar"] {display: none !important;}
    [data-testid="collapsedControl"] {display: none !important;}
</style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)


def _get_logo_base64(logo_path="logo.png"):
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


def _safe_str(value, default="N/A"):
    if value is None:
        return default
    return str(value).strip()


def find_resident_by_phone(phone):
    cleaned_phone = clean_phone_number(phone)
    if not cleaned_phone or len(cleaned_phone) < 8:
        return None, "❌ Invalid phone number — please enter 8 digits."
    try:
        result = supabase.table("participants").select("*").eq("contact", cleaned_phone).eq("active", True).execute()
        if result.data:
            return result.data[0], None
        else:
            return None, "❌ No resident found with this phone number."
    except Exception as e:
        return None, f"⚠️ Database error: {str(e)}"


def get_active_sessions_for_now(activity_config):
    """Auto-detect which sessions are currently active based on SGT time."""
    now_sgt = datetime.now(timezone(timedelta(hours=8)))
    current_time_str = now_sgt.strftime("%H:%M")
    
    sessions = [False, False, False, False]
    for i in range(1, 5):
        start = activity_config.get(f'session_{i}_start_time')
        end = activity_config.get(f'session_{i}_end_time')
        if start and end:
            # Simple string comparison works perfectly for "HH:MM" format
            if start <= current_time_str <= end:
                sessions[i-1] = True
    return sessions


def display_resident_qr_card(resident):
    resident_id = _safe_str(resident.get('id'), "UNKNOWN")
    resident_name = _safe_str(resident.get('name'), "Unknown Resident")
    resident_block = _safe_str(resident.get('block_no'), "N/A")
    
    logo_src = _get_logo_base64()
    qr_data = resident_id
    qr_api_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={urllib.parse.quote(qr_data)}"

    try:
        import requests
        response = requests.get(qr_api_url)
        if response.status_code == 200:
            qr_base64 = base64.b64encode(response.content).decode()
            qr_image_src = f"data:image/png;base64,{qr_base64}"
        else:
            qr_image_src = qr_api_url
    except Exception:
        qr_image_src = qr_api_url

    # 🔗 Build WhatsApp link
    phone = resident.get("contact")
    clean_phone = clean_phone_number(phone) if phone else ""
    wa_phone = f"65{clean_phone}" if clean_phone and len(clean_phone) == 8 else clean_phone
    wa_text = urllib.parse.quote(f"Here is my QR code for Woodlands Zone 6: {APP_URL}/resident_qr?phone={clean_phone}")
    whatsapp_link = f"https://wa.me/{wa_phone}?text={wa_text}" if wa_phone else "#"

    # ✅ Professional Badge HTML/CSS
    card_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html-to-image/1.11.11/html-to-image.min.js"></script>
    <style>
        body {{ margin: 0; padding: 20px; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: transparent; display: flex; flex-direction: column; justify-content: center; align-items: center; min-height: 100vh; }}
        .badge {{ width: 340px; background: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,0.3); border: 1px solid #e0e0e0; text-align: center; color: #1a1a1a; }}
        .badge-header {{ background: linear-gradient(135deg, #4a6cf7, #3b5bdb); color: white; padding: 20px 15px; display: flex; flex-direction: column; align-items: center; gap: 8px; }}
        .badge-header img {{ width: 50px; height: 50px; object-fit: contain; background: white; border-radius: 50%; padding: 5px; }}
        .badge-header h2 {{ margin: 0; font-size: 18px; font-weight: 700; letter-spacing: 1px; }}
        .badge-header p {{ margin: 0; font-size: 10px; text-transform: uppercase; letter-spacing: 2px; opacity: 0.8; }}
        .badge-body {{ padding: 20px; }}
        .resident-name {{ font-size: 24px; font-weight: bold; margin: 0 0 5px 0; color: #1a1a1a; word-break: break-word; }}
        .resident-block {{ font-size: 16px; color: #666; margin: 0 0 15px 0; font-weight: 500; }}
        .qr-container {{ display: inline-block; padding: 10px; border: 2px dashed #4a6cf7; border-radius: 12px; background: #fff; margin-bottom: 10px; }}
        .qr-container img {{ width: 180px; height: 180px; display: block; }}
        .scan-hint {{ font-size: 11px; color: #888; text-transform: uppercase; letter-spacing: 1px; margin: 0 0 15px 0; }}
        .id-box {{ background: #f8f9fa; padding: 10px; border-radius: 8px; font-family: 'Courier New', monospace; font-size: 16px; font-weight: bold; color: #333; letter-spacing: 1px; border: 1px solid #eee; }}
        .badge-footer {{ background: #f8f9fa; padding: 12px; border-top: 1px solid #eee; font-size: 11px; color: #4a6cf7; font-weight: bold; text-transform: uppercase; letter-spacing: 1px; }}
        .actions {{ margin-top: 20px; display: flex; gap: 15px; justify-content: center; width: 100%; }}
        .btn {{ background: #4a6cf7; color: white; border: none; padding: 12px 24px; border-radius: 8px; font-size: 15px; cursor: pointer; font-weight: bold; transition: 0.2s; }}
        .btn:hover {{ background: #3b5bdb; }}
        .btn-outline {{ background: transparent; color: #4a6cf7; border: 2px solid #4a6cf7; }}
        .btn-outline:hover {{ background: #f0f4ff; }}
        @media print {{
            body {{ margin: 0; padding: 0; background: white; }}
            .badge {{ box-shadow: none; border: 1px solid #ccc; width: 100%; max-width: 350px; margin: 0 auto; }}
            .actions {{ display: none !important; }}
        }}
    </style>
</head>
<body>
    <div class="badge" id="badge">
        <div class="badge-header">
            <img src="{logo_src}" alt="Logo">
            <h2>WOODLANDS ZONE 6</h2>
            <p>Community Hub</p>
        </div>
        <div class="badge-body">
            <h1 class="resident-name">{resident_name}</h1>
            <p class="resident-block">Block: {resident_block}</p>
            <div class="qr-container">
                <img src="{qr_image_src}" alt="QR Code" id="qr-img">
            </div>
            <p class="scan-hint">Scan at Kiosk</p>
            <div class="id-box">ID: {resident_id}</div>
        </div>
        <div class="badge-footer">COMMUNITY ACTIVITIES</div>
    </div>
    
    <div class="actions">
        <button class="btn" onclick="downloadCard()">📥 Download PNG</button>
        <button class="btn btn-outline" onclick="window.print()">🖨️ Print Badge</button>
    </div>

    <script>
        function downloadCard() {{
            const card = document.getElementById('badge');
            htmlToImage.toPng(card, {{ quality: 1.0, pixelRatio: 2, backgroundColor: '#ffffff' }})
            .then(function (dataUrl) {{
                const link = document.createElement('a');
                link.download = 'Resident_Badge_{resident_name.replace(" ", "_")}.png';
                link.href = dataUrl;
                link.click();
            }})
            .catch(function (error) {{
                console.error('Download error:', error);
                alert('Could not download image. Please try again.');
            }});
        }}
    </script>
</body>
</html>
"""

    from streamlit.components.v1 import html
    html(card_html, height=780, scrolling=True)

    # External WhatsApp button
    st.markdown(
        f"<div style='text-align:center; margin-top:10px;'>"
        f"<a href='{whatsapp_link}' target='_blank' style='background:#128C7E; color:white; padding:12px 24px; text-decoration:none; border-radius:8px; font-weight:bold; display:inline-block; font-size:16px;'>"
        f"📲 Share via WhatsApp</a></div>",
        unsafe_allow_html=True
    )


def display_self_checkin_section(resident):
    """Displays the elderly-friendly self check-in section."""
    st.divider()
    st.subheader("📅 Today's Check-In")
    st.caption("Tap the button below to check in for today's activities.")
    
    resident_id = resident.get('id')
    today_sgt = datetime.now(timezone(timedelta(hours=8)))
    today_str = today_sgt.strftime("%Y-%m-%d")
    
    # Fetch today's attendance for this resident to disable buttons if already checked in
    try:
        today_att = supabase.table('attendance').select('source').eq('participant_id', resident_id).eq('date', today_str).execute().data
        checked_in_activities = {rec['source'] for rec in (today_att or [])}
    except Exception:
        checked_in_activities = set()

    acts = load_activities()
    if not acts:
        st.info("No activities are currently configured in the system.")
        return

    for act in acts:
        act_name = act['name']
        
        # Auto-detect active sessions based on current time
        sessions = get_active_sessions_for_now(act)
        any_active = any(sessions)
        
        st.markdown(f"### {act_name}")
        
        if act_name in checked_in_activities:
            st.markdown(
                f"<div style='background:#d4edda; color:#155724; padding:15px; border-radius:8px; border-left:5px solid #28a745; margin-bottom:15px; font-weight:bold;'>"
                f"✅ You are already checked in for today!</div>", 
                unsafe_allow_html=True
            )
        elif any_active:
            session_names = []
            for i, is_active in enumerate(sessions):
                if is_active:
                    lbl = act.get(f'session_{i+1}_label') or f"Session {i+1}"
                    session_names.append(lbl)
            
            session_text = " & ".join(session_names) if session_names else "the current session"
            
            if st.button(f"✅ Tap to Check In for {act_name}", key=f"checkin_{act_name}_{resident_id}", use_container_width=True, type="primary"):
                with st.spinner("Checking you in..."):
                    if AttendanceService:
                        success, msg, _ = AttendanceService.process_checkin(resident_id, today_str, act_name, *sessions)
                    else:
                        # Fallback inline check-in if AttendanceService is not available
                        try:
                            supabase.table('attendance').insert({
                                "participant_id": resident_id,
                                "name": resident.get('name'),
                                "date": today_str,
                                "session_1": sessions[0], "session_2": sessions[1], 
                                "session_3": sessions[2], "session_4": sessions[3],
                                "timestamp": today_sgt.isoformat(),
                                "self_checkin": True,
                                "source": act_name,
                                "activities": [act_name]
                            }).execute()
                            success, msg = True, "Checked in successfully."
                        except Exception as e:
                            if 'duplicate' in str(e).lower():
                                success, msg = False, "Already checked in."
                            else:
                                success, msg = False, str(e)

                    if success:
                        st.success(f"✅ Successfully Checked In for {act_name}!")
                        st.info("Thank you! Have a great time.")
                        st.rerun() # Rerun to update the "already checked in" status
                    else:
                        if "already" in msg.lower():
                            st.info(f"ℹ️ You are already checked in for {act_name} today.")
                        else:
                            st.error(f"❌ {msg}")
        else:
            st.markdown(
                f"<div style='background:#f8f9fa; color:#666; padding:15px; border-radius:8px; border-left:5px solid #ccc; margin-bottom:15px;'>"
                f"⏳ <i>Check-in for {act_name} is not currently open.</i></div>", 
                unsafe_allow_html=True
            )


# ───────────────────────────────────────────────
# MAIN LOGIC
# ───────────────────────────────────────────────
st.markdown("<h2 style='text-align:center;'>📱 Your QR Code</h2>", unsafe_allow_html=True)
st.markdown("<p style='text-align:center; color:#666;'>Enter your 8-digit mobile number to view your personal QR code.</p>", unsafe_allow_html=True)

# ✅ Updated to modern st.query_params (replaces deprecated st.experimental_get_query_params)
query_params = st.query_params
default_phone = query_params.get("phone", "").strip()

phone_input = st.text_input(
    "Enter your 8-digit mobile number",
    value=default_phone,
    placeholder="e.g., 91234567",
    key="resident_phone_input",
    label_visibility="collapsed"
)

if phone_input:
    cleaned = clean_phone_number(phone_input)
    if len(cleaned) >= 8:
        with st.spinner("🔍 Looking up your record..."):
            resident, error = find_resident_by_phone(cleaned)
        if error:
            st.error(f"❌ {error}")
        elif resident:
            st.success("✅ Found your QR code!")
            display_resident_qr_card(resident)
            
            # 🆕 NEW: Elderly-friendly self check-in section
            display_self_checkin_section(resident)

            # Personal link shown OUTSIDE the card
            full_link = f"{APP_URL}/resident_qr?phone={cleaned}"
            st.markdown(
                f"<div style='padding:12px; border-radius:8px; margin-top:16px; text-align:center; font-size:14px; border:1px solid #444; background:transparent;'>"
                f"🔗 <strong style='color: #ffffff;'>Your Personal Link</strong><br>"
                f"<code style='font-size:13px; background:transparent; padding:4px 8px; color:#4a6cf7;'>{full_link}</code>"
                f"</div>",
                unsafe_allow_html=True
            )
        else:
            st.info("📱 Phone number not registered. Please contact the admin.")
    else:
        st.warning("⚠️ Please enter a valid 8-digit mobile number.")
else:
    st.info("👉 Enter your phone number above to get your QR code.")

st.markdown(
    "<hr><p style='text-align:center; font-size:12px; color:#999;'>This link is personal and secure. Do not share publicly.</p>",
    unsafe_allow_html=True
)