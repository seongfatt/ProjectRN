import streamlit as st
import urllib.parse, qrcode, io, base64
from PIL import Image
from datetime import datetime
from config import supabase, generate_token, APP_URL, load_activities

def show_qr_links(selected_date):
    st.header("📱 QR Code & WhatsApp Links")

    acts = load_activities()
    act_names = [a['name'] for a in acts]
    activity = st.selectbox("🎯 Select Activity", act_names, index=0)
    date_str = selected_date.strftime("%Y%m%d")

    col1, col2 = st.columns([1, 2])
    with col1:
        if st.button("🔄 Generate Today's Links", type="primary"):
            links = []
            for p in st.session_state.participants:
                if p.get('active', True):
                    token = generate_token(p['id'], date_str)
                    link = f"{APP_URL}/?mode=checkin&pid={p['id']}&date={date_str}&tk={token}&act={urllib.parse.quote(activity)}"
                    phone = p.get('contact', '').replace(" ", "").replace("-", "")
                    if not phone.startswith("+"): phone = "+65" + phone
                    msg = f"Hello *{p['name']}*! 👋 {activity} {selected_date.strftime('%d %b')}: {link}"
                    wa_url = f"https://wa.me/{phone}?text={urllib.parse.quote(msg)}"
                    links.append({'name': p['name'], 'phone': phone, 'link': link, 'whatsapp': wa_url, 'id': p['id']})
            st.session_state.whatsapp_links = links
            st.success(f"Generated {len(links)} links!")

    with col2:
        st.info("Bulk send options below ↓")

    if not st.session_state.get('whatsapp_links'):
        st.info("Click Generate to create links")
        return

    # QR Code Display
    st.divider()
    st.subheader("📷 QR Codes")
    search = st.text_input("Search for QR", placeholder="Type name...")
    items = [l for l in st.session_state.whatsapp_links if search.lower() in l['name'].lower()] if search else st.session_state.whatsapp_links

    cols = st.columns(4)
    for i, item in enumerate(items[:20]):  # Limit to 20 for performance
        with cols[i % 4]:
            qr = qrcode.QRCode(box_size=4, border=2)
            qr.add_data(item['link'])
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            b64 = base64.b64encode(buf.getvalue()).decode()
            st.markdown(f"**{item['name']}**")
            st.markdown(f'<img src="data:image/png;base64,{b64}" width="150"/>', unsafe_allow_html=True)
            st.caption(f"[WhatsApp]({item['whatsapp']})")

    # Bulk Send
    st.divider()
    st.subheader("🚀 Bulk Send Options")

    with st.expander("⚡ Auto-Open All WhatsApp"):
        st.warning("Disable popup blocker first!")
        delay = st.slider("Delay (sec)", 3, 10, 5)
        urls_js = ", ".join([f"'{item['whatsapp']}'" for item in st.session_state.whatsapp_links])
        js = f"<script>var urls=[{urls_js}],c=0;function o(){{if(c<urls.length){{window.open(urls[c],'_blank');c++;setTimeout(o,{delay*1000});}}}}o();</script>"
        if st.button("🚀 OPEN ALL CHATS", type="primary", use_container_width=True):
            st.components.v1.html(js, height=50)
            st.success(f"Opening {len(st.session_state.whatsapp_links)} chats...")

    with st.expander("📋 Download CSV"):
        import pandas as pd
        df = pd.DataFrame(st.session_state.whatsapp_links)
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("Download CSV", csv, f"links_{date_str}.csv", "text/csv")
