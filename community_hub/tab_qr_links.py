import streamlit as st
import urllib.parse
from datetime import datetime
from config import supabase, APP_URL, load_activities
from utils import generate_token

def show_qr_links(selected_date):
    st.header("QR Code & WhatsApp Links")

    # ===== INSTRUCTION BOX =====
    st.markdown("""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                color: white; padding: 20px; border-radius: 10px; margin-bottom: 20px;">
        <h3 style="color: white; margin-top: 0;">📖 How to Use Auto Check-In</h3>
        <ol style="margin: 10px 0; padding-left: 20px;">
            <li><strong>Select Activity</strong> below (e.g., "Cardio Drumming")</li>
            <li><strong>Choose Session</strong> — Both / Session 1 / Session 2</li>
            <li>Click <strong>Generate Today's Links</strong></li>
            <li><strong>Scan QR code</strong> with phone — instant check-in!</li>
        </ol>
        <p style="margin-bottom: 0; font-size: 14px;">
            Residents scan QR → Browser opens → Attendance auto-saved → Done!
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # ===== CONFIGURATION SECTION =====
    st.subheader("Step 1: Configure")

    acts = load_activities()
    act_names = [a['name'] for a in acts]
    activity = st.selectbox("🎯 Select Activity", act_names, index=0)

    date_str = selected_date.strftime("%Y%m%d")

    # Session selection - make it very visible
    st.markdown("**📅 Session Selection**")
    session_option = st.radio(
        "Choose which session(s) to auto-register:",
        ["Both Sessions", "Session 1 Only", "Session 2 Only"],
        horizontal=True,
        help="Select what happens when resident scans the QR code"
    )

    # Map selection to URL parameter
    if session_option == "Both Sessions":
        session_param = "both"
        session_display = "Both Sessions (S1 + S2)"
    elif session_option == "Session 1 Only":
        session_param = "1"
        session_display = "Session 1 Only"
    else:
        session_param = "2"
        session_display = "Session 2 Only"

    st.info(f"QR codes will auto-register: **{session_display}** for **{activity}** on **{selected_date.strftime('%d %b %Y')}**")

    st.divider()

    # ===== GENERATE SECTION =====
    st.subheader("Step 2: Generate")

    col1, col2 = st.columns([1, 2])
    with col1:
        if st.button("🔄 Generate Today's Links", type="primary", use_container_width=True):
            with st.spinner("Generating QR codes..."):
                links = []
                for p in st.session_state.participants:
                    if p.get('active', True):
                        token = generate_token(p['id'], date_str)
                        # AUTO mode link - clicking = instant check-in!
                        link = f"{APP_URL}/?mode=auto&pid={p['id']}&date={date_str}&tk={token}&act={urllib.parse.quote(activity)}&session={session_param}"
                        phone = p.get('contact', '').replace(" ", "").replace("-", "")
                        if not phone.startswith("+"): phone = "+65" + phone
                        msg = f"Hello {p['name']}! {activity} {selected_date.strftime('%d %b')}: {link}"
                        wa_url = f"https://wa.me/{phone}?text={urllib.parse.quote(msg)}"
                        links.append({
                            'name': p['name'], 
                            'phone': phone, 
                            'link': link, 
                            'whatsapp': wa_url, 
                            'id': p['id'],
                            'session': session_display
                        })
                st.session_state.whatsapp_links = links
            st.success(f"✅ Generated {len(links)} auto check-in links! ({session_display})")

    with col2:
        st.markdown("""
        <div style="background: #e8f5e9; border-left: 4px solid #4caf50; padding: 15px; border-radius: 4px;">
            <strong>Auto Check-In Mode</strong><br>
            Residents scan QR → Attendance saved instantly<br>
            No form, no checkbox, no confirm button needed!
        </div>
        """, unsafe_allow_html=True)

    # ===== QR CODE DISPLAY SECTION =====
    if not st.session_state.get('whatsapp_links'):
        st.info("👆 Click 'Generate Today's Links' above to create QR codes")
        return

    st.divider()
    st.subheader("Step 3: Scan QR Codes")
    st.caption("Each QR code is personal. Scanning instantly records attendance.")

    # Summary stats
    total = len(st.session_state.whatsapp_links)
    st.markdown(f"**Showing {total} QR codes** | Activity: {activity} | Session: {session_display}")

    # Search
    search = st.text_input("🔍 Search resident name", placeholder="Type name...")
    items = [l for l in st.session_state.whatsapp_links if search.lower() in l['name'].lower()] if search else st.session_state.whatsapp_links

    # Display QR codes in grid
    cols = st.columns(4)
    for i, item in enumerate(items[:20]):
        with cols[i % 4]:
            qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={urllib.parse.quote(item['link'])}"
            st.markdown(f"**{item['name']}**")
            st.markdown(f"<span style='color: #666; font-size: 12px;'>{item.get('session', 'Auto Check-in')}</span>", unsafe_allow_html=True)
            st.image(qr_url, width=200)
            st.caption(f"[📱 WhatsApp]({item['whatsapp']})")

    # ===== BULK SEND SECTION =====
    st.divider()
    st.subheader("Bulk Send Options")

    with st.expander("📱 Auto-Open All WhatsApp Chats"):
        st.warning("⚠️ Disable popup blocker in your browser first!")
        delay = st.slider("Delay between opens (seconds)", 3, 10, 5)

        urls_js = ", ".join([f"'{item['whatsapp']}'" for item in st.session_state.whatsapp_links])
        js = f"<script>var urls=[{urls_js}],c=0;function o(){{if(c<urls.length){{window.open(urls[c],'_blank');c++;setTimeout(o,{delay*1000});}}}}o();</script>"

        if st.button("🚀 OPEN ALL WHATSAPP CHATS", type="primary", use_container_width=True):
            st.components.v1.html(js, height=50)
            st.success(f"Opening {len(st.session_state.whatsapp_links)} WhatsApp chats...")

    with st.expander("📥 Download CSV"):
        import pandas as pd
        # Ensure all items have 'session' key for DataFrame
        links_data = []
        for item in st.session_state.whatsapp_links:
            item_copy = item.copy()
            if 'session' not in item_copy:
                item_copy['session'] = 'Auto Check-in'
            links_data.append(item_copy)
        df = pd.DataFrame(links_data)
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("Download Links CSV", csv, f"links_{date_str}.csv", "text/csv")