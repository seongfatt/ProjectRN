import streamlit as st
import base64
import os
from datetime import datetime, timezone

import urllib
from config import supabase, APP_URL
from utils import clean_phone_number, mask_phone


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


def find_resident_by_phone(phone):
    """Find active resident by phone number"""
    cleaned_phone = clean_phone_number(phone)
    if not cleaned_phone or len(cleaned_phone) < 8:
        return None, "Invalid phone number"
    try:
        result = supabase.table("participants").select("*").eq("contact", cleaned_phone).eq("active", True).execute()
        if result.data:
            return result.data[0], None
        else:
            return None, "No resident found with this phone number"
    except Exception as e:
        return None, f"Database error: {e}"


def display_resident_qr_card(resident):
    """Display QR card and download button for the resident"""
    resident_id = str(resident['id']).strip()
    resident_name = resident['name']
    resident_block = resident.get('block_no', 'N/A')
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

    card_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<script src="https://html2canvas.hertzen.com/dist/html2canvas.min.js"></script>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: transparent; display: flex; flex-direction: column; align-items: center; padding: 10px; }}
.card {{ background: #ffffff; color: #1a1a1a; border-radius: 20px; padding: 30px 24px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); width: 100%; max-width: 400px; text-align: center; }}
.header {{ display: flex; align-items: center; justify-content: center; gap: 15px; margin-bottom: 20px; }}
.logo {{ width: 60px; height: 60px; object-fit: contain; background: #f8f9fa; border-radius: 10px; padding: 5px; flex-shrink: 0; }}
.title-group {{ text-align: left; }}
.title-group h2 {{ color: #667eea; margin: 0; font-size: 22px; font-weight: 800; line-height: 1.1; }}
.title-group p {{ color: #666; margin: 2px 0 0 0; font-size: 12px; text-transform: uppercase; letter-spacing: 1px; }}
.divider {{ border: 0; border-top: 2px solid #eee; margin: 20px 0; }}
.resident-name {{ margin: 10px 0; font-size: 36px; font-weight: bold; color: #1a1a1a; word-break: break-word; }}
.resident-block {{ font-size: 20px; color: #555; margin: 5px 0 20px 0; font-weight: 500; }}
.qr-wrap {{ margin: 10px 0; }}
.qr-wrap img {{ width: 220px; height: 220px; border: 2px dashed #667eea; border-radius: 10px; padding: 10px; background: #fff; }}
.qr-hint {{ font-size: 12px; color: #888; margin: 8px 0 0 0; }}
.id-box {{ background: #f8f9fa; padding: 15px; border-radius: 10px; margin-top: 20px; }}
.id-box p {{ font-size: 24px; font-weight: bold; color: #1a1a1a; font-family: 'Courier New', monospace; margin: 0; letter-spacing: 1px; }}
.footer-text {{ font-weight: bold; color: #667eea; font-size: 16px; text-transform: uppercase; letter-spacing: 1px; margin-top: 15px; }}
.download-btn {{ margin-top: 20px; padding: 12px 24px; background: #667eea; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: bold; font-size: 16px; width: 100%; max-width: 400px; }}
</style>
</head>
<body>
<div class="card" id="residentCard">
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
  <div class="qr-wrap"><img src="{qr_image_src}" alt="QR Code"></div>
  <p class="qr-hint">Scan at Kiosk</p>
  <div class="id-box"><p>ID: {resident_id}</p></div>
  <p class="footer-text">Community Activities</p>
</div>
<button class="download-btn" onclick="downloadCard()">Download Card as PNG</button>
<script>
function downloadCard() {{
  const card = document.getElementById('residentCard');
  html2canvas(card, {{ backgroundColor: '#ffffff', scale: 2, useCORS: true, allowTaint: true }}).then(canvas => {{
    const link = document.createElement('a');
    link.download = 'Resident_Card_{resident_id}.png';
    link.href = canvas.toDataURL('image/png');
    link.click();
  }});
}}
</script>
</body>
</html>"""

    from streamlit.components.v1 import html
    html(card_html, height=750)

    st.download_button(
        label="📥 Download Card Info (Text)",
        data=f"""WOODLANDS ZONE 6 - COMMUNITY HUB
RESIDENT CARD
Name: {resident_name}
Block: {resident_block}
ID: {resident_id}
Valid for Community Activities Check-In
""",
        file_name=f"Resident_Card_{resident_name.replace(' ', '_')}.txt",
        mime="text/plain"
    )
    st.caption("💡 You can also take a screenshot or print the card for physical use.")


def show_resident_qr_page():
    st.set_page_config(page_title="Your QR Code", layout="centered")

    st.markdown("""
    <style>
    .stTextInput input {
        font-size: 20px;
        padding: 15px;
    }
    .stButton button {
        font-size: 18px;
        padding: 12px;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("## 📱 Your QR Code")
    st.markdown("🔑 Please enter your 8-digit mobile number to view your QR code.")

    phone = st.text_input("Enter Your Mobile Number", placeholder="e.g., 91234567", key="resident_qr_phone")

    if phone:
        cleaned_phone = clean_phone_number(phone)
        if len(cleaned_phone) < 8:
            st.warning("⚠️ Please enter a full 8-digit mobile number.")
        else:
            with st.spinner("🔍 Looking up your record..."):
                resident, error = find_resident_by_phone(cleaned_phone)
            if error:
                st.error(f"❌ {error}")
            elif resident:
                st.success("✅ Found your QR code!")
                display_resident_qr_card(resident)
            else:
                st.warning("⚠️ No resident found with this phone number.")
    else:
        st.info("📱 Please enter your mobile number to proceed.")
        st.markdown("""
        <div style="background: #e3f2fd; padding: 15px; border-radius: 10px; margin: 20px 0; text-align: center;">
            <p>Woodlands Zone 6 Community Hub</p>
            <p>QR Code Portal</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("""
    <div style="margin-top: 40px; text-align: center; color: #666; font-size: 14px;">
        <p>This link is personal and temporary.</p>
        <p>Please do not share it publicly.</p>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    show_resident_qr_page()