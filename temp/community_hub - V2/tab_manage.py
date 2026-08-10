import streamlit as st
from datetime import datetime
from config import supabase, refresh_data

def load_all_activities():
    """Load ALL activities (active + inactive) for management"""
    try:
        r = supabase.table('activities').select("*").order('id').execute()
        return r.data if r.data else []
    except:
        return []

def show_manage(selected_date):
    st.header("Management")

    tab1, tab2, tab3 = st.tabs(["Participants", "Activities", "Convert Status"])

    with tab1:
        with st.expander("Register New Participant"):
            with st.form("new_p"):
                name = st.text_input("Full Name")
                contact = st.text_input("Contact")
                indemnity = st.checkbox("Indemnity Signed")
                if st.form_submit_button("Register"):
                    if name and contact:
                        import random
                        new_p = {"id": datetime.now().strftime("%Y%m%d%H%M%S") + str(random.randint(10, 99)), "name": name.upper(), "contact": contact,
                                 "indemnity": indemnity, "is_new": True, "active": True, "registration_date": str(selected_date)}
                        supabase.table('participants').insert(new_p).execute()
                        refresh_data(); st.success(f"Added {name}!"); st.rerun()

        with st.expander("Indemnity Status"):
            unsigned = [p for p in st.session_state.participants if not p.get('indemnity') and p.get('active', True)]
            for p in unsigned:
                c1, c2 = st.columns([3, 1])
                c1.write(f"🔴 {p['name']}")
                if c2.button("Mark Signed", key=f"ind_{p['id']}"):
                    supabase.table('participants').update({'indemnity': True}).eq('id', p['id']).execute()
                    refresh_data(); st.rerun()

        with st.expander("🗑️ Remove Participant"):
            st.warning("Removing a participant will deactivate them. They will no longer appear in check-ins or reports.")
            st.info("Garden plots assigned to them will NOT be auto-released. Please release plots manually in the Garden tab.")

            remove_search = st.text_input("Search to remove", placeholder="Type name or last 4 digits...", key="remove_search")
            active_list = [p for p in st.session_state.participants if p.get('active', True)]

            if remove_search:
                s = remove_search.lower()
                matches = [p for p in active_list if s in p['name'].lower() or s in p.get('contact', '')[-4:]]
                if matches:
                    st.write(f"**{len(matches)} match(es) found:**")
                    for p in matches:
                        with st.container():
                            c1, c2, c3 = st.columns([3, 2, 1])
                            c1.write(f"**{p['name']}**")
                            c2.write(f"📞 {p.get('contact', 'N/A')}")
                            c2.write(f"ID: `{p['id']}`")
                            if c3.button("Remove", key=f"remove_{p['id']}", type="secondary"):
                                try:
                                    # Soft delete: set active=False instead of hard delete
                                    supabase.table('participants').update({'active': False}).eq('id', p['id']).execute()
                                    refresh_data()
                                    st.success(f"Removed {p['name']}. They are now inactive.")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error: {e}")
                else:
                    st.info("No matches found")
            else:
                st.caption("Type a name above to search for participants to remove")

    with tab2:
        st.subheader("Manage Activities")
        st.caption("All activities are shown here. Inactive ones are hidden from dropdowns but kept in the database.")

        acts = load_all_activities()

        if not acts:
            st.info("No activities found in database")
        else:
            for a in acts:
                status_icon = "🟢" if a.get('active') else "⚪"
                with st.expander(f"{status_icon} {a['name']} (ID: {a['id']})"):
                    c1, c2, c3 = st.columns([3, 1, 1])
                    with c1:
                        st.write(f"**Session 1:** {a.get('session_1_label', 'Session 1')}")
                        st.write(f"**Session 2:** {a.get('session_2_label', 'Session 2')}")
                        st.write(f"**Status:** {'Active' if a.get('active') else 'Inactive'}")
                    with c2:
                        toggle_label = "Deactivate" if a.get('active') else "Reactivate"
                        if st.button(toggle_label, key=f"act_toggle_{a['id']}"):
                            supabase.table('activities').update({'active': not a.get('active', True)}).eq('id', a['id']).execute()
                            refresh_data(); st.rerun()
                    with c3:
                        if st.button("🗑️ Remove", key=f"act_del_{a['id']}"):
                            supabase.table('activities').delete().eq('id', a['id']).execute()
                            refresh_data(); st.success(f"Removed '{a['name']}'"); st.rerun()

                    # Edit Activity Form
                    with st.form(key=f"edit_act_{a['id']}"):
                        st.markdown("**Edit Activity**")
                        edit_name = st.text_input("Activity Name", value=a.get('name', ''), key=f"edit_name_{a['id']}")
                        edit_s1 = st.text_input("Session 1 Label", value=a.get('session_1_label', 'Session 1'), key=f"edit_s1_{a['id']}")
                        edit_s2 = st.text_input("Session 2 Label", value=a.get('session_2_label', 'Session 2'), key=f"edit_s2_{a['id']}")
                        if st.form_submit_button("Update Activity", type="primary"):
                            if edit_name.strip():
                                supabase.table('activities').update({
                                    'name': edit_name.strip(),
                                    'session_1_label': edit_s1.strip(),
                                    'session_2_label': edit_s2.strip()
                                }).eq('id', a['id']).execute()
                                refresh_data()
                                st.success(f"Updated '{edit_name}'!")
                                st.rerun()

        st.divider()
        with st.expander("➕ Add New Activity"):
            st.info("Adding a new activity will NOT remove existing ones. Old activities remain in the list.")
            with st.form("new_act"):
                act_name = st.text_input("Activity Name *")
                s1_label = st.text_input("Session 1 Label", value="Session 1 (7PM-8PM)")
                s2_label = st.text_input("Session 2 Label", value="Session 2 (8PM-9PM)")
                if st.form_submit_button("Add Activity", type="primary"):
                    if act_name.strip():
                        # Insert without specifying ID — let Supabase auto-generate
                        supabase.table('activities').insert({
                            "name": act_name.strip(),
                            "session_1_label": s1_label.strip(),
                            "session_2_label": s2_label.strip(),
                            "active": True
                        }).execute()
                        refresh_data()
                        st.success(f"Added '{act_name}'! It will now appear in the activity dropdown.")
                        st.rerun()
                    else:
                        st.error("Activity name is required")

    with tab3:
        newbies = [p for p in st.session_state.participants if p.get('is_new') and p.get('active', True)]
        if not newbies:
            st.info("No new residents pending conversion")
        else:
            st.write(f"**{len(newbies)} new resident(s) ready to convert to Regular**")
            for p in newbies:
                c1, c2 = st.columns([3, 1])
                c1.write(f"{p['name']}")
                if c2.button("Make Regular", key=f"reg_{p['id']}"):
                    supabase.table('participants').update({'is_new': False}).eq('id', p['id']).execute()
                    refresh_data(); st.rerun()
