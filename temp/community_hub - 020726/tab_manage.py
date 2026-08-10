from config import supabase, refresh_data, PLOT_TYPES, DB_CONNECTED
from utils import mask_phone
from datetime import datetime
import streamlit as st
import random

def load_all_activities():
    """Load ALL activities (active + inactive) for management"""
    try:
        r = supabase.table('activities').select("*").order('id').execute()
        return r.data if r.data else []
    except:
        return []

def show_payment_management():
    """Admin tab to mark garden plot residents as paid/unpaid."""
    st.subheader("💰 Garden Plot Payment Management")
    st.caption("Track and update payment status for garden plot holders")

    if not DB_CONNECTED:
        st.error("Database not connected")
        return

    # Load all plots with owners
    try:
        plots = supabase.table('garden_plots').select("*").eq('occupied', True).order('plot_number').execute().data
    except Exception as e:
        st.error(f"Error loading plots: {e}")
        return

    if not plots:
        st.info("No occupied garden plots found")
        return

    # Load participants for name lookup
    try:
        participants = supabase.table('participants').select("*").execute().data
        part_dict = {p['id'].lower().strip(): p for p in participants}
    except:
        part_dict = {}

    st.write(f"**{len(plots)} occupied plot(s)**")

    # Summary metrics
    paid_count = sum(1 for p in plots if p.get('paid', False))
    unpaid_count = len(plots) - paid_count

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Occupied", len(plots))
    c2.metric("✅ Paid", paid_count)
    c3.metric("❌ Unpaid", unpaid_count)
    st.progress(paid_count / len(plots) if plots else 0, text=f"Payment Rate: {paid_count/len(plots):.1%}" if plots else "0%")
    st.divider()

    # Filter options
    filter_status = st.selectbox("Filter", ["All", "Paid Only", "Unpaid Only"], key="pay_filter")

    # Display each plot
    for plot in plots:
        is_paid = plot.get('paid', False)

        # Skip based on filter
        if filter_status == "Paid Only" and not is_paid:
            continue
        if filter_status == "Unpaid Only" and is_paid:
            continue

        # Look up resident name
        owner_id = str(plot.get('user_id', '')).lower().strip()
        resident = part_dict.get(owner_id)
        owner_name = plot.get('user_name') or (resident['name'] if resident else 'Unknown')
        owner_contact = plot.get('contact') or (resident.get('contact', 'N/A') if resident else 'N/A')

        with st.container():
            col1, col2, col3, col4, col5 = st.columns([1, 2, 2, 2, 1])
            
            with col1:
                ptype = plot.get('plot_type', 'B')
                color = {"A": "#2ca02c", "B": "#ff7f0e", "C": "#1f77b4", "D": "#d62728"}.get(ptype, "#666")
                st.markdown(f'<div style="background:{color};color:white;padding:6px;border-radius:4px;text-align:center;font-weight:bold;font-size:12px;">Plot {plot["plot_number"]}</div>', unsafe_allow_html=True)
            
            with col2:
                st.write(f"**{owner_name}**")
                st.caption(f"ID: {plot.get('user_id', 'N/A')[:15]}...")
            
            with col3:
                st.write(f"📞 {mask_phone(owner_contact)}")
                st.caption(f"Type {ptype} ({PLOT_TYPES.get(ptype, {}).get('area', '?')} m²)")
            
            with col4:
                status_color = "🟢 Paid" if is_paid else "🔴 Unpaid"
                st.write(f"**{status_color}**")
                if plot.get('updated_at'):
                    st.caption(f"Updated: {plot['updated_at'][:10]}")
            
            with col5:
                btn_label = "Mark Unpaid" if is_paid else "Mark Paid"
                btn_type = "secondary" if is_paid else "primary"
                if st.button(btn_label, key=f"pay_btn_{plot['plot_number']}", type=btn_type, use_container_width=True):
                    try:
                        supabase.table('garden_plots').update({
                            'paid': not is_paid,
                            'updated_at': datetime.now().isoformat()
                        }).eq('plot_number', plot['plot_number']).execute()
                        st.success(f"Plot {plot['plot_number']} updated!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

    st.divider()
    
    # Bulk actions
    with st.expander("⚡ Bulk Actions"):
        st.warning("These actions affect ALL filtered plots. Use with caution.")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Mark ALL as Paid", type="primary", use_container_width=True):
                try:
                    for plot in plots:
                        supabase.table('garden_plots').update({
                            'paid': True,
                            'updated_at': datetime.now().isoformat()
                        }).eq('plot_number', plot['plot_number']).execute()
                    st.success("All plots marked as paid!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
        
        with col2:
            if st.button("❌ Mark ALL as Unpaid", type="secondary", use_container_width=True):
                try:
                    for plot in plots:
                        supabase.table('garden_plots').update({
                            'paid': False,
                            'updated_at': datetime.now().isoformat()
                        }).eq('plot_number', plot['plot_number']).execute()
                    st.success("All plots marked as unpaid!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

def show_manage(selected_date):
    st.header("Management")

    tab1, tab2, tab3, tab4 = st.tabs(["Participants", "Activities", "Convert Status", "💰 Payment Status"])

    with tab1:
        with st.expander("Register New Participant"):
            with st.form("new_p"):
                name = st.text_input("Full Name")
                contact = st.text_input("Contact")
                indemnity = st.checkbox("Indemnity Signed")
                if st.form_submit_button("Register"):
                    if name and contact:
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

    with tab4:
        show_payment_management()