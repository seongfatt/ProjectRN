import streamlit as st
from datetime import datetime
from config import supabase, refresh_data, load_activities

def show_manage(selected_date):
    st.header("⚙️ Management")

    tab1, tab2, tab3 = st.tabs(["👤 Participants", "🎯 Activities", "🔄 Convert Status"])

    # Participants
    with tab1:
        with st.expander("➕ Register New Participant"):
            with st.form("new_p"):
                name = st.text_input("Full Name")
                contact = st.text_input("Contact")
                indemnity = st.checkbox("Indemnity Signed")
                if st.form_submit_button("Register"):
                    if name and contact:
                        new_p = {
                            "id": datetime.now().strftime("%Y%m%d%H%M%S"),
                            "name": name.upper(), "contact": contact,
                            "indemnity": indemnity, "is_new": True,
                            "active": True, "registration_date": str(selected_date)
                        }
                        supabase.table('participants').insert(new_p).execute()
                        refresh_data(); st.success(f"Added {name}!"); st.rerun()

        with st.expander("📝 Indemnity Status"):
            unsigned = [p for p in st.session_state.participants if not p.get('indemnity') and p.get('active', True)]
            for p in unsigned:
                c1, c2 = st.columns([3, 1])
                c1.write(f"🔴 {p['name']}")
                if c2.button("Mark Signed", key=f"ind_{p['id']}"):
                    supabase.table('participants').update({'indemnity': True}).eq('id', p['id']).execute()
                    refresh_data(); st.rerun()

    # Activities
    with tab2:
        st.subheader("🎯 Manage Activities")
        acts = load_activities()
        for a in acts:
            with st.expander(f"{a['name']} {'✅' if a.get('active') else '❌'}"):
                c1, c2 = st.columns(2)
                with c1:
                    st.write(f"S1: {a.get('session_1_label', 'Session 1')}")
                    st.write(f"S2: {a.get('session_2_label', 'Session 2')}")
                with c2:
                    if st.button("Toggle Active", key=f"act_toggle_{a['id']}"):
                        supabase.table('activities').update({'active': not a.get('active', True)}).eq('id', a['id']).execute()
                        refresh_data(); st.rerun()

        with st.expander("➕ Add New Activity"):
            with st.form("new_act"):
                act_name = st.text_input("Activity Name")
                s1_label = st.text_input("Session 1 Label", value="Session 1")
                s2_label = st.text_input("Session 2 Label", value="Session 2")
                if st.form_submit_button("Add Activity"):
                    if act_name:
                        supabase.table('activities').insert({
                            "name": act_name, "session_1_label": s1_label,
                            "session_2_label": s2_label, "active": True
                        }).execute()
                        refresh_data(); st.success(f"Added {act_name}!"); st.rerun()

    # Convert Status
    with tab3:
        newbies = [p for p in st.session_state.participants if p.get('is_new') and p.get('active', True)]
        for p in newbies:
            c1, c2 = st.columns([3, 1])
            c1.write(f"{p['name']}")
            if c2.button("Make Regular", key=f"reg_{p['id']}"):
                supabase.table('participants').update({'is_new': False}).eq('id', p['id']).execute()
                refresh_data(); st.rerun()
