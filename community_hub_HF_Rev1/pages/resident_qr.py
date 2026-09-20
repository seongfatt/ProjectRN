import streamlit as st
import urllib.parse
import base64
import os
import time
from datetime import datetime, timezone, timedelta
from config import supabase, APP_URL, load_activities
from utils import clean_phone_number, mask_phone
from services import AttendanceService

# 🔒 Hide sidebar + header for resident-facing page
st.set_page_config(
    page_title="Your QR Code",
    page_icon="logo.png",  # <--- This changes the browser tab icon!
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


# ═══════════════════════════════════════════════════════════════
#  SELF CHECK-IN SECTION  (added — Option A: above QR badge)
# ═══════════════════════════════════════════════════════════════

SGT = timezone(timedelta(hours=8))


def _now_sgt():
    """Server-side Singapore time. Never trust client clock."""
    return datetime.now(SGT)


def _get_live_activities_now():
    """
    Return list of activities whose session window contains 'now'.
    Each item: {name, session_index, session_label, start, end, flags[4]}
    """
    now_time = _now_sgt().time()

    try:
        acts = load_activities() or []
    except Exception:
        return []

    live = []
    for act in acts:
        flags = [False, False, False, False]
        active_idx = None
        active_label = active_start = active_end = None

        for i in range(1, 5):
            lbl = (act.get(f'session_{i}_label') or '').strip()
            start_str = act.get(f'session_{i}_start_time')
            end_str = act.get(f'session_{i}_end_time')
            if not lbl or not start_str or not end_str:
                continue
            try:
                start_t = datetime.strptime(str(start_str)[:5], "%H:%M").time()
                end_t = datetime.strptime(str(end_str)[:5], "%H:%M").time()
            except Exception:
                continue

            if start_t <= now_time <= end_t:
                flags[i - 1] = True
                if active_idx is None:
                    active_idx = i
                    active_label = lbl
                    active_start = str(start_str)[:5]
                    active_end = str(end_str)[:5]

        if active_idx:
            live.append({
                'name': act['name'],
                'session_index': active_idx,
                'session_label': active_label,
                'start': active_start,
                'end': active_end,
                'flags': flags,
            })
    return live


def _already_checked_in(resident_id, activity_name, date_obj, flags):
    """Return (is_fully_checked_in, existing_record_or_None)."""
    try:
        res = (
            supabase.table('attendance').select("*")
            .eq('participant_id', resident_id)
            .eq('date', date_obj.strftime('%Y-%m-%d'))
            .eq('source', activity_name)
            .execute()
        )
        if not res.data:
            return False, None
        record = res.data[0]
        needed = [i + 1 for i, f in enumerate(flags) if f]
        if not needed:
            return False, record
        if any(not record.get(f'session_{n}', False) for n in needed):
            return False, record
        return True, record
    except Exception:
        return False, None


def _attempt_self_checkin(resident, activity_name, date_obj, flags):
    """Call AttendanceService then flag self_checkin=True."""
    try:
        success, message, _ = AttendanceService.process_checkin(
            resident['id'], date_obj, activity_name,
            flags[0], flags[1], flags[2], flags[3]
        )
        if success:
            try:
                supabase.table('attendance').update({"self_checkin": True}) \
                    .eq('participant_id', resident['id']) \
                    .eq('date', date_obj.strftime('%Y-%m-%d')) \
                    .eq('source', activity_name).execute()
            except Exception:
                pass  # flag update is best-effort; don't fail the check-in
        return success, message
    except Exception as e:
        return False, str(e)


def render_self_checkin_section(resident):
    """Big elderly-friendly check-in area, rendered ABOVE the QR badge."""

    # Big button CSS — applies to primary buttons on this page only
    st.markdown("""
    <style>
    div[data-testid="stButton"] > button[kind="primary"] {
        min-height: 72px !important;
        font-size: 24px !important;
        font-weight: 800 !important;
        border-radius: 14px !important;
        letter-spacing: 1.5px !important;
        background: #28a745 !important;
        border: none !important;
    }
    div[data-testid="stButton"] > button[kind="primary"]:hover {
        background: #218838 !important;
    }
    div[data-testid="stButton"] > button:disabled {
        min-height: 62px !important;
        font-size: 18px !important;
        font-weight: 700 !important;
        border-radius: 14px !important;
    }
    </style>
    """, unsafe_allow_html=True)

    live = _get_live_activities_now()
    today = _now_sgt().date()

    # ── State 3: No live activity ──────────────────────────────
    if not live:
        st.markdown("""
        <div style="background:#f5f5f5; border-left:6px solid #9e9e9e;
                    border-radius:12px; padding:22px; margin:10px 0 22px 0;
                    text-align:center; color:#424242;">
            <div style="font-size:38px; line-height:1;">📅</div>
            <div style="font-size:22px; font-weight:700; margin-top:8px;">
                No events happening right now
            </div>
            <div style="font-size:16px; color:#616161; margin-top:8px;">
                Please show your QR code to the volunteer below.
            </div>
        </div>
        """, unsafe_allow_html=True)
        return

    # ── State 1 / 2: One block per live activity ───────────────
    for activity in live:
        already, record = _already_checked_in(
            resident['id'], activity['name'], today, activity['flags']
        )
        time_str = f"{activity['start']} – {activity['end']}"

        if already:
            # Timestamp (SGT)
            ts_display = "today"
            try:
                if record and record.get('timestamp'):
                    ts = datetime.fromisoformat(
                        str(record['timestamp']).replace('Z', '+00:00')
                    )
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    ts_display = ts.astimezone(SGT).strftime('%I:%M %p')
            except Exception:
                pass

            st.markdown(f"""
            <div style="background:#e8f5e9; border-left:6px solid #28a745;
                        border-radius:14px; padding:24px; margin:10px 0 12px 0;
                        text-align:center;">
                <div style="font-size:52px; line-height:1;">✅</div>
                <div style="font-size:26px; font-weight:800; color:#1e7e34;
                            margin-top:10px; letter-spacing:1px;">
                    YOU'RE CHECKED IN
                </div>
                <div style="font-size:20px; font-weight:700; color:#1a1a1a;
                            margin-top:12px;">
                    {activity['name']}
                </div>
                <div style="font-size:16px; color:#2e7d32; margin-top:6px;
                            font-weight:600;">
                    {activity['session_label']} · {ts_display}
                </div>
            </div>
            """, unsafe_allow_html=True)

            st.button(
                "✅  Checked in for today",
                key=f"self_done_{activity['name']}",
                disabled=True,
                use_container_width=True,
            )

        else:
            # Live + not yet checked in
            st.markdown(f"""
            <div style="background:linear-gradient(135deg,#e8f5e9,#c8e6c9);
                        border-left:6px solid #28a745; border-radius:14px;
                        padding:24px; margin:10px 0 14px 0; text-align:center;">
                <div style="display:inline-block; background:#28a745; color:white;
                            font-size:14px; font-weight:700; padding:5px 14px;
                            border-radius:20px; letter-spacing:1.5px;">
                    🟢 HAPPENING NOW
                </div>
                <div style="font-size:26px; font-weight:800; color:#1a1a1a;
                            margin-top:14px;">
                    {activity['name']}
                </div>
                <div style="font-size:18px; color:#2e7d32; margin-top:8px;
                            font-weight:700;">
                    {activity['session_label']}
                </div>
                <div style="font-size:16px; color:#555; margin-top:6px;">
                    🕐 {time_str}
                </div>
            </div>
            """, unsafe_allow_html=True)

            if st.button(
                "✅  CHECK IN NOW",
                key=f"self_btn_{activity['name']}",
                type="primary",
                use_container_width=True,
            ):
                with st.spinner("Checking you in..."):
                    success, message = _attempt_self_checkin(
                        resident, activity['name'], today, activity['flags']
                    )

                if success:
                    st.success(f"✅ You're checked in for {activity['name']}!")
                    st.balloons()
                    time.sleep(1.2)
                    st.rerun()
                elif 'already' in (message or '').lower():
                    st.info("ℹ️ You're already checked in for this activity.")
                    time.sleep(1.0)
                    st.rerun()
                else:
                    st.error(f"❌ {message or 'Check-in failed. Please try again.'}")

        st.markdown(
            "<div style='text-align:center; font-size:13px; color:#888; "
            "margin:18px 0 6px 0; letter-spacing:1px;'>"
            "─── YOUR QR CODE (for volunteer scan) ───</div>",
            unsafe_allow_html=True,
        )


# ═══════════════════════════════════════════════════════════════
#  QR BADGE (unchanged)
# ═══════════════════════════════════════════════════════════════

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
    <!-- ✅ SWITCHED TO html-to-image FOR RELIABLE BASE64 CAPTURING -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html-to-image/1.11.11/html-to-image.min.js"></script>
    <style>
        body {{
            margin: 0;
            padding: 20px;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: transparent;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
        }}
        .badge {{
            width: 340px;
            background: #ffffff;
            border-radius: 16px;
            overflow: hidden;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
            border: 1px solid #e0e0e0;
            text-align: center;
            color: #1a1a1a;
        }}
        .badge-header {{
            background: linear-gradient(135deg, #4a6cf7, #3b5bdb);
            color: white;
            padding: 20px 15px;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 8px;
        }}
        .badge-header img {{
            width: 50px;
            height: 50px;
            object-fit: contain;
            background: white;
            border-radius: 50%;
            padding: 5px;
        }}
        .badge-header h2 {{
            margin: 0;
            font-size: 18px;
            font-weight: 700;
            letter-spacing: 1px;
        }}
        .badge-header p {{
            margin: 0;
            font-size: 10px;
            text-transform: uppercase;
            letter-spacing: 2px;
            opacity: 0.8;
        }}
        .badge-body {{
            padding: 20px;
        }}
        .resident-name {{
            font-size: 24px;
            font-weight: bold;
            margin: 0 0 5px 0;
            color: #1a1a1a;
            word-break: break-word;
        }}
        .resident-block {{
            font-size: 16px;
            color: #666;
            margin: 0 0 15px 0;
            font-weight: 500;
        }}
        .qr-container {{
            display: inline-block;
            padding: 10px;
            border: 2px dashed #4a6cf7;
            border-radius: 12px;
            background: #fff;
            margin-bottom: 10px;
        }}
        .qr-container img {{
            width: 180px;
            height: 180px;
            display: block;
        }}
        .scan-hint {{
            font-size: 11px;
            color: #888;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin: 0 0 15px 0;
        }}
        .id-box {{
            background: #f8f9fa;
            padding: 10px;
            border-radius: 8px;
            font-family: 'Courier New', monospace;
            font-size: 16px;
            font-weight: bold;
            color: #333;
            letter-spacing: 1px;
            border: 1px solid #eee;
        }}
        .badge-footer {{
            background: #f8f9fa;
            padding: 12px;
            border-top: 1px solid #eee;
            font-size: 11px;
            color: #4a6cf7;
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .actions {{
            margin-top: 20px;
            display: flex;
            gap: 15px;
            justify-content: center;
            width: 100%;
        }}
        .btn {{
            background: #4a6cf7;
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            font-size: 15px;
            cursor: pointer;
            font-weight: bold;
            transition: 0.2s;
        }}
        .btn:hover {{
            background: #3b5bdb;
        }}
        .btn-outline {{
            background: transparent;
            color: #4a6cf7;
            border: 2px solid #4a6cf7;
        }}
        .btn-outline:hover {{
            background: #f0f4ff;
        }}

        /* Print Styles */
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

            // ✅ html-to-image handles Base64 images perfectly without CORS errors
            htmlToImage.toPng(card, {{
                quality: 1.0,
                pixelRatio: 2,
                backgroundColor: '#ffffff'
            }})
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


# ───────────────────────────────────────────────
# MAIN LOGIC
# ───────────────────────────────────────────────
st.markdown("<h2 style='text-align:center;'>📱 Your QR Code</h2>", unsafe_allow_html=True)
st.markdown("<p style='text-align:center; color:#666;'>Enter your 8-digit mobile number to view your personal QR code.</p>", unsafe_allow_html=True)

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

            # 🆕 Self check-in section (Option A: ABOVE QR badge)
            render_self_checkin_section(resident)

            # Existing QR badge (unchanged)
            display_resident_qr_card(resident)

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