import streamlit as st
import urllib.parse
import base64
import os
from datetime import datetime
from config import supabase, APP_URL
from utils import clean_phone_number, mask_phone

# 🔒 Hide sidebar + header for resident-facing page
st.set_page_config(
    page_title="Your QR Code",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Hide Streamlit UI elements via CSS
hide_streamlit_style = """
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)


def _get_logo_base64(logo_path="logo.png"):
    """Convert local logo to base64 so it renders inside HTML component."""
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
    # Fallback: minimal SVG logo
    return (
        "data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+"
        "PHJlY3Qgd2lkdGg9IjYwIiBoZWlnaHQ9IjYwIiBmaWxsPSIjNjY3ZWVhIiByeD0iMTAiLz48dGV4dCB4PSI1MCUiIHk9"
        "IjUwJSIgZG9taW5hbnQtYmFzZWxpbmU9Im1pZGRsZSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZmlsbD0id2hpdGUiIGZvbnQt"
        "ZmFtaWx5PSJBcmlhbCIgZm9udC1zaXplPSIxNCIgZm9udC13ZWlnaHQ9ImJvbGQiPldaNjwvdGV4dD48L3N2Zz4="
    )


def find_resident_by_phone(phone):
    """Find active resident by phone number"""
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


def display_resident_qr_card(resident):
    """Render QR card with white background, no download button in image, and shareable link"""
    resident_id = str(resident['id']).strip()
    resident_name = resident['name'].strip()
    resident_block = resident.get('block_no', 'N/A').strip()
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

    # ✅ Clean white-background card (print-friendly, no buttons in PNG)
    card_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            margin: 0;
            padding: 20px;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #ffffff;
            color: #000000;
            display: flex;
            flex-direction: column;
            align-items: center;
            max-width: 400px;
            width: 100%;
        }}
        .header {{
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 12px;
            margin-bottom: 20px;
            width: 100%;
        }}
        .logo {{
            width: 60px;
            height: 60px;
            object-fit: contain;
            background: #f8f9fa;
            border-radius: 10px;
            padding: 5px;
        }}
        .title-group {{
            text-align: left;
        }}
        .title-group h2 {{
            color: #4a6cf7;
            margin: 0;
            font-size: 22px;
            font-weight: 700;
            line-height: 1.2;
        }}
        .title-group p {{
            color: #666;
            margin: 2px 0 0 0;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .divider {{
            border: 0;
            border-top: 1px solid #eee;
            margin: 20px 0;
            width: 100%;
        }}
        .resident-name {{
            margin: 10px 0;
            font-size: 28px;
            font-weight: bold;
            color: #000;
            word-break: break-word;
        }}
        .resident-block {{
            font-size: 18px;
            color: #555;
            margin: 5px 0;
            font-weight: 500;
        }}
        .qr-wrap {{
            margin: 15px 0;
            display: flex;
            justify-content: center;
        }}
        .qr-wrap img {{
            width: 220px;
            height: 220px;
            border: 2px dashed #4a6cf7;
            border-radius: 8px;
            padding: 8px;
            background: #fff;
            box-shadow: 0 2px 6px rgba(0,0,0,0.05);
        }}
        .qr-hint {{
            font-size: 12px;
            color: #666;
            margin: 8px 0 0 0;
            text-align: center;
        }}
        .id-box {{
            background: #f8f9fa;
            padding: 12px;
            border-radius: 8px;
            margin-top: 15px;
            text-align: center;
            font-family: 'Courier New', monospace;
        }}
        .id-box p {{
            font-size: 20px;
            font-weight: bold;
            color: #000;
            margin: 0;
            letter-spacing: 1px;
        }}
        .footer-link {{
            margin-top: 20px;
            padding: 10px;
            background: #f0f4ff;
            border-radius: 8px;
            font-size: 13px;
            color: #2c3e50;
            text-align: center;
            word-break: break-all;
            border: 1px dashed #4a6cf7;
        }}
        .footer-text {{
            font-weight: 600;
            color: #4a6cf7;
            font-size: 16px;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-top: 20px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <img src="{logo_src}" class="logo" alt="Logo">
        <div class="title-group">
            <h2>WOODLANDS ZONE 6</h2>
            <p>Community Hub</p>
        </div>
    </div>
    <hr class="divider">
    <h1 class="resident-name">{resident_name}</h1>
    <p class="resident-block">Block: {resident_block}</p>
    <hr class="divider">
    <div class="qr-wrap">
        <img src="{qr_image_src}" alt="QR Code">
    </div>
    <p class="qr-hint">Scan at Kiosk</p>
    <div class="id-box">
        <p>ID: {resident_id}</p>
    </div>
    <div class="footer-link">
        🔗 Shareable Link:<br>
        {APP_URL}/resident_qr?phone={urllib.parse.quote(clean_phone_number(resident.get('contact', '')))}
    </div>
    <p class="footer-text">COMMUNITY ACTIVITIES</p>
</body>
</html>
"""

    from streamlit.components.v1 import html
    html(card_html, height=720)

    # ✅ Optional: Add *external* download button (outside card, for browser only — NOT in PNG)
    st.download_button(
        label="📥 Download Card as PNG",
        data=card_html.encode("utf-8"),
        file_name=f"Resident_Card_{resident_name.replace(' ', '_')}.png",
        mime="image/png",
        key="download_qr_card",
    )
    st.caption("💡 Tip: Save this card to your phone or print it for kiosk check-in.")


# ───────────────────────────────────────────────
# MAIN LOGIC
# ───────────────────────────────────────────────
st.markdown("<h2 style='text-align:center;'>📱 Your QR Code</h2>", unsafe_allow_html=True)
st.markdown("<p style='text-align:center; color:#666;'>Enter your 8-digit mobile number to view your personal QR code.</p>", unsafe_allow_html=True)

# Extract phone from URL query param (e.g., ?phone=97907043)
query_params = st.experimental_get_query_params()
default_phone = query_params.get("phone", [""])[0].strip()

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

            # 🔗 Show shareable link (for reference, not in PNG)
            full_link = f"{APP_URL}/resident_qr?phone={cleaned}"
            st.markdown(
                f"<div style='background:#f8f9fa; padding:12px; border-radius:8px; margin-top:16px; text-align:center; font-size:14px;'>"
                f"🔗 <strong>Shareable Link</strong><br>"
                f"<code style='font-size:13px; background:#eef2f7; padding:4px 8px; border-radius:4px;'>{full_link}</code>"
                f"</div>",
                unsafe_allow_html=True
            )

        else:
            st.info("📱 Phone number not registered. Please contact the admin.")
    else:
        st.warning("⚠️ Please enter a valid 8-digit mobile number.")
else:
    st.info("👉 Enter your phone number above — or open this link with `?phone=YOUR_NUMBER` in the URL.")

st.markdown(
    "<hr><p style='text-align:center; font-size:12px; color:#999;'>This link is personal and secure. Do not share publicly.</p>",
    unsafe_allow_html=True
)