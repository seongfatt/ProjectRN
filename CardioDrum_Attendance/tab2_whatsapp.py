import streamlit as st
import urllib.parse
from datetime import datetime
from config import supabase, generate_token

def show_tab2(selected_date):
    st.header("📱 WhatsApp Self Check-in Links")
    
    date_str = selected_date.strftime("%Y%m%d")
    base_url = "https://wrnz6-cardiodrum.hf.space"
    
    col1, col2 = st.columns([1, 2])
    with col1:
        if st.button("🔄 Generate Today's Links", type="primary"):
            with st.spinner("Generating..."):
                links_data = []
                for p in st.session_state.participants:
                    if p.get('active', True):
                        token = generate_token(p['id'], date_str)
                        personal_link = f"{base_url}/?mode=checkin&pid={p['id']}&date={date_str}&tk={token}"
                        phone = p['contact'].replace(" ", "").replace("-", "")
                        if not phone.startswith("+"):
                            phone = "+65" + phone
                        
                        message = f"Hello *{p['name']}*! 👋 Cardio Drumming {selected_date.strftime('%d %b')}: {personal_link}"
                        wa_url = f"https://wa.me/{phone}?text={urllib.parse.quote(message)}"
                        
                        links_data.append({
                            'name': p['name'],
                            'phone': phone,
                            'link': personal_link,
                            'whatsapp': wa_url
                        })
                
                st.session_state.whatsapp_links = links_data
                st.success(f"Generated {len(links_data)} links!")
    
    with col2:
        st.info("Bulk send available below ↓")
    
    if not st.session_state.whatsapp_links:
        st.info("Click Generate to create links")
        return
    
    # BULK SEND OPTIONS
    st.divider()
    st.subheader("🚀 Bulk Send Options")
    
    # Option 1: Auto-open All
    with st.expander("⚡ Option 1: Auto-Open All WhatsApp (Fastest)"):
        st.warning("Disable popup blocker first!")
        delay = st.slider("Delay between opens (sec)", 3, 10, 5)
        
        if st.button("🚀 OPEN ALL WHATSAPP CHATS", type="primary", use_container_width=True):
            urls_js = ", ".join([f"'{item['whatsapp']}'" for item in st.session_state.whatsapp_links])
            
            js_code = f"""
            <script>
                var urls = [{urls_js}];
                var current = 0;
                function openNext() {{
                    if (current < urls.length) {{
                        window.open(urls[current], '_blank');
                        current++;
                        setTimeout(openNext, {delay * 1000});
                    }}
                }}
                openNext();
            </script>
            """
            st.components.v1.html(js_code, height=50)
            st.success(f"Opening {len(st.session_state.whatsapp_links)} chats...")
    
    # Option 2: Download CSV
    with st.expander("📋 Option 2: Download for Bulk Tools"):
        import pandas as pd
        df = pd.DataFrame(st.session_state.whatsapp_links)
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("Download CSV", csv, f"links_{date_str}.csv", "text/csv")
    
    # Individual List
    st.divider()
    st.subheader("👤 Individual Links")
    
    search = st.text_input("Search", placeholder="Type name...")
    items = [l for l in st.session_state.whatsapp_links if search.lower() in l['name'].lower()] if search else st.session_state.whatsapp_links
    
    for item in items:
        cols = st.columns([3, 2])
        cols[0].write(f"**{item['name']}**")
        cols[1].markdown(f"[WhatsApp]({item['whatsapp']})")