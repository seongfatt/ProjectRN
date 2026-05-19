import streamlit as st
from datetime import datetime
from config import supabase, refresh_data

def show_tab4(selected_date):
    st.header("⚙️ Participant Management")
    
    # New Participant
    with st.expander("➕ Register New Participant"):
        with st.form("new_p"):
            name = st.text_input("Full Name")
            contact = st.text_input("Contact Number")
            indemnity = st.checkbox("Indemnity Signed")
            
            if st.form_submit_button("Register"):
                if name and contact:
                    new_p = {
                        "id": datetime.now().strftime("%Y%m%d%H%M%S"),
                        "name": name.upper(),
                        "contact": contact,
                        "indemnity": indemnity,
                        "is_new": True,
                        "active": True,
                        "registration_date": str(selected_date)
                    }
                    supabase.table('participants').insert(new_p).execute()
                    refresh_data()
                    st.success(f"Added {name}!")
                    st.rerun()
    
    # Convert New to Regular
    with st.expander("🔄 Convert New → Regular"):
        newbies = [p for p in st.session_state.participants if p.get('is_new') and p.get('active', True)]
        for p in newbies:
            cols = st.columns([3, 1])
            cols[0].write(f"{p['name']}")
            if cols[1].button("Make Regular", key=f"reg_{p['id']}"):
                supabase.table('participants').update({'is_new': False}).eq('id', p['id']).execute()
                refresh_data()
                st.rerun()
    
    # Indemnity Status
    with st.expander("📝 Indemnity Status"):
        unsigned = [p for p in st.session_state.participants if not p.get('indemnity') and p.get('active', True)]
        for p in unsigned:
            cols = st.columns([3, 1])
            cols[0].write(f"🔴 {p['name']}")
            if cols[1].button("Mark Signed", key=f"ind_{p['id']}"):
                supabase.table('participants').update({'indemnity': True}).eq('id', p['id']).execute()
                refresh_data()
                st.rerun()