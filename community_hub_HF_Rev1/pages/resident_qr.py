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
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    [data-testid="stSidebar"] {display: none;}
    /* Improve contrast for dark theme */
    .stApp { background-color: #0f172a; }  /* slate-900 */
    .stTextInput > div > div > input {
        background-color: #1e293b;
        color: #f1f5f9;
        border: 1px solid #334155;
    }
    .stButton button {
        background-color: #3b82f6;
        color: white;
        border-radius: 8px;
        font-weight: 600;
    }
    .stButton button:hover {
        background-color: #2563eb;
    }
</style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)


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
    """Display QR card and download button for the resident"""
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

    # ✅ Dark-themed card (high contrast, matches your app)
    card_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<script src="https://html2canvas.hertzen.com/dist/html2canvas.min.js"></script>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ 
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
    background: #0f172a; 
    color: #f1f5f9;
    display: flex; 
    flex-direction: column; 
    align-items: center; 
    padding: 10px;
}}
.card {{
    background: #1e293b;
    color: #f1f5f9;
    border-radius: 16px;
    padding: 28px 24px;
    box-shadow: 0 12px 32px rgba(0,0,0,0.3);
    width: 100%;
    max-width: 400px;
    text-align: center;
    border: 1px solid #334155;
}}
.header {{
    display: flex; 
    align-items: center; 
    justify-content: center; 
    gap: 14px; 
    margin-bottom: 22px;
}}
.logo {{
    width: 56px; 
    height: 56px; 
    object-fit: contain; 
    background: #0f172a; 
    border-radius: 12px; 
    padding: 4px;
    flex-shrink: 0;
}}
.title-group {{
    text-align: left;
}}
.title-group h2 {{
    color: #60a5fa;
    margin: 0;
    font-size: 20px;
    font-weight: 700;
    line-height: 1.2;
}}
.title-group p {{
    color: #94a3b8;
    margin: 2px 0 0 0;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 1px;
}}
.divider {{
    border: 0;
    border-top: 1px solid #334155;
    margin: 20px 0;
}}
.resident-name {{
    margin: 12px 0;
    font-size: 28px;
    font-weight: 800;
    color: #f1f5f9;
    word-break: break-word;
}}
.resident-block {{
    font-size: 18px;
    color: #cbd5e1;
    margin: 6px 0 20px 0;
    font-weight: 500;
}}
.qr-wrap {{
    margin: 14px 0;
}}
.qr-wrap img {{
    width: 210px;
    height: 210px;
    border: 2px dashed #60a5fa;
    border-radius: 12px;
    padding: 10px;
    background: #0f172a;
    box-shadow: inset 0 0 0 2px #1e293b;
}}
.qr-hint {{
    font-size: 12px;
    color: #94a3b8;
    margin: 8px 0 0 0;
}}
.id-box {{
    background: #0f172a;
    padding: 14px;
    border-radius: 10px;
    margin: 16px 0;
}}
.id-box p {{
    font-size: 22px;
    font-weight: bold;
    color: #f1f5f9;
    font-family: 'Courier New', monospace;
    margin: 0;
    letter-spacing: 1px;
}}
.footer-text {{
    font-weight: 600;
    color: #60a5fa;
    font-size: 16px;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin: 14px 0;
}}
.download-btn {{
    margin: 20px 0;
    padding: 12px 24px;
    background: #3b82f6;
    color: white;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    font-weight: 600;
    font-size: 16px;
    width: 100%;
    max-width: 400px;
    transition: background 0.2s;
}}
.download-btn:hover {{
    background: #2563eb;
}}
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
<button class="download-btn" onclick="downloadCard()">📥 Download Card as PNG</button>
<script>
function downloadCard() {{
  const card = document.getElementById('residentCard');
  html2canvas(card, {{ backgroundColor: '#0f172a', scale: 2, useCORS: true, allowTaint: true }}).then(canvas => {{
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
    html(card_html, height=720)

    # ✅ Optional: Remove "Download Card Info (Text)" — comment out below if you want to keep it
    # st.caption("💡 You can also take a screenshot or print for physical use.")
    # st.download_button(
    #     label="📥 Download Card Info (Text)",
    #     data=f"""WOODLANDS ZONE 6 - COMMUNITY HUB\nRESIDENT CARD\nName: {resident_name}\nBlock: {resident_block}\nID: {resident_id}\nValid for Community Activities Check-In""",
    #     file_name=f"Resident_Card_{resident_name.replace(' ', '_')}.txt",
    #     mime="text/plain",
    #     key=f"download_qr_{resident_id}_bulk",
    # )

    st.caption("📱 **Tip**: Tap 📥 *Download Card as PNG* to save for printing or screenshot.")


# ───────────────────────────────────────────────
# MAIN LOGIC
# ───────────────────────────────────────────────
st.markdown("<h1 style='text-align: center; color: #f1f5f9;'>📱 Your QR Code</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #94a3b8;'>Enter your 8-digit mobile number to view your personal QR code.</p>", unsafe_allow_html=True)

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

            # 🔗 Shareable link (for admin to copy-paste)
            full_link = f"{APP_URL}/resident_qr?phone={cleaned}"
            st.markdown(f"""
            <div style="background: #1e293b; padding: 14px; border-radius: 10px; margin: 20px 0; text-align: center; border-left: 3px solid #60a5fa;">
                <strong>🔗 Shareable Link:</strong><br>
                <code style="font-size: 13px; background: #0f172a; padding: 4px 8px; border-radius: 4px; color: #60a5fa;">{full_link}</code><br>
                <small style="color: #94a3b8;">✅ Admins can send this link directly to residents.</small>
            </div>
            """, unsafe_allow_html=True)

        else:
            st.info("📱 Phone number not registered. Please contact the admin.")
    else:
        st.warning("⚠️ Please enter a valid 8-digit mobile number.")
else:
    st.info("👉 Enter your phone number above — or open this link with `?phone=YOUR_NUMBER` in the URL.")

st.markdown("<hr><p style='text-align: center; font-size: 12px; color: #64748b;'>This link is personal and secure. Do not share publicly.</p>", unsafe_allow_html=True)