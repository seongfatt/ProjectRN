import streamlit as st
import pandas as pd
import random
from datetime import datetime
from config import supabase, DB_CONNECTED, refresh_data, load_activities
from utils import mask_phone, clean_phone_number, log_action

def show_manage(selected_date):
    st.header("Management")
    if not DB_CONNECTED:
        st.error("Database not connected"); return

    # Define tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Participants", "Activities", "Convert Status", "💰 Payment Status", "📜 Audit Logs"])

    # ── TAB 1: Participants ───────────────────────────────────
    with tab1:
        #  CHAIRMAN RESTRICTION: Hide registration and deletion
        if st.session_state.user_role == 'admin':
            with st.expander("Register New Participant"):
                with st.form("new_p"):
                    name = st.text_input("Full Name")
                    contact = st.text_input("Contact")
                    no_phone = st.checkbox("👴 Elderly without phone")
                    indemnity = st.checkbox("Indemnity Signed")
                    
                    if st.form_submit_button("Register"):
                        if name:
                            final_contact = "NO_PHONE" if no_phone else contact.strip()
                            
                            # 🔥 PREVENT DUPLICATE: Check if phone number already exists
                            if final_contact != "NO_PHONE":
                                clean_contact = clean_phone_number(final_contact)
                                existing_check = supabase.table('participants').select('*').eq('contact', clean_contact).execute()
                                if existing_check.data:
                                    st.warning(f"⚠️ **Resident already exists!**\n\nName: **{existing_check.data[0]['name']}**\nPhone: {clean_contact}")
                                    st.stop()
                            
                            new_p = {
                                "id": datetime.now().strftime("%Y%m%d%H%M%S") + str(random.randint(10, 99)), 
                                "name": name.upper(), 
                                "contact": final_contact,
                                "indemnity": indemnity, 
                                "is_new": True, 
                                "active": True, 
                                "registration_date": str(selected_date)
                            }
                            supabase.table('participants').insert(new_p).execute()
                            refresh_data()
                            st.success(f"Added {name}!")
                            st.rerun()
                        else:
                            st.error("Name is required")

            with st.expander("Indemnity Status"):
                unsigned = [p for p in st.session_state.participants if not p.get('indemnity') and p.get('active', True)]
                for p in unsigned:
                    c1, c2 = st.columns([3, 1])
                    c1.write(f"🔴 {p['name']}")
                    if c2.button("Mark Signed", key=f"ind_{p['id']}"):
                        supabase.table('participants').update({'indemnity': True}).eq('id', p['id']).execute()
                        refresh_data(); st.rerun()

            with st.expander("🗑️ Remove Participant"):
                st.warning("Removing a participant will deactivate them.")
                remove_search = st.text_input("Search to remove", placeholder="Type name or last 4 digits...", key="remove_search")
                active_list = [p for p in st.session_state.participants if p.get('active', True)]

                if remove_search:
                    s = remove_search.lower()
                    matches = [p for p in active_list if s in p['name'].lower() or s in p.get('contact', '')[-4:]]
                    if matches:
                        for p in matches:
                            with st.container():
                                c1, c2, c3 = st.columns([3, 2, 1])
                                c1.write(f"**{p['name']}**")
                                c2.write(f" {mask_phone(p.get('contact', 'N/A'))}")
                                if c3.button("Remove", key=f"remove_{p['id']}", type="secondary"):
                                    supabase.table('participants').update({'active': False}).eq('id', p['id']).execute()
                                    refresh_data(); st.rerun()
        else:
            st.info("🔒 Participant management is restricted to System Admins.")

    # ─── TAB 2: Activities ─────────────────────────────────────
    with tab2:
        acts = load_activities()
        if not acts:
            st.info("No activities configured.")
        else:
            for a in acts:
                c1, c2, c3 = st.columns([3, 2, 1])
                c1.write(f"**{a['name']}**")
                c2.write(f"{a.get('session_1_label', 'S1')} | {a.get('session_2_label', 'S2')}")
                with c3:
                    # 🔒 HIDE DELETE FOR CHAIRMAN
                    if st.session_state.user_role == 'admin':
                        if st.button("️ Remove", key=f"act_del_{a['id']}"):
                            supabase.table('activities').update({'active': False}).eq('id', a['id']).execute()
                            refresh_data(); st.rerun()
        
        # 🔒 HIDE ADD FOR CHAIRMAN
        if st.session_state.user_role == 'admin':
            with st.expander("➕ Add New Activity"):
                with st.form("add_act"):
                    act_name = st.text_input("Activity Name")
                    s1 = st.text_input("Session 1 Label", value="Session 1 (7PM-8PM)")
                    s2 = st.text_input("Session 2 Label (Optional)", value="")
                    if st.form_submit_button("Add Activity"):
                        if act_name:
                            supabase.table('activities').insert({
                                "name": act_name.upper(),
                                "session_1_label": s1,
                                "session_2_label": s2,
                                "active": True
                            }).execute()
                            refresh_data(); st.rerun()

    # ─── TAB 3: Convert Status ─────────────────────────────────
    with tab3:
        st.info("Residents automatically convert from 'New' to 'Regular' after 3 attendances.")
        newbies = [p for p in st.session_state.participants if p.get('is_new') and p.get('active', True)]
        st.write(f"**{len(newbies)} New Residents**")
        for p in newbies:
            c = supabase.table('attendance').select('*', count='exact').eq('participant_id', p['id']).execute().count
            st.write(f"{p['name']} - {c} attendances")
            if c >= 3:
                if st.button(f"Convert {p['name']}", key=f"conv_{p['id']}"):
                    supabase.table('participants').update({'is_new': False}).eq('id', p['id']).execute()
                    refresh_data(); st.rerun()

    # ─── TAB 4: Payment Status ─────────────────────────────────
    with tab4:
        st.subheader("Garden Plot Payment Management")
        plots = st.session_state.plots
        occupied_plots = [p for p in plots if p.get('occupied')]
        
        if not occupied_plots:
            st.info("No occupied plots.")
        else:
            for plot in occupied_plots:
                owner_name = plot.get('user_name', 'Unknown')
                is_paid = plot.get('paid', False)
                
                c1, c2, c3, c4 = st.columns([2, 2, 1, 1])
                c1.write(f"**Plot {plot['plot_number']}** (Type {plot['plot_type']})")
                c2.write(f"Owner: {owner_name}")
                c3.write("✅ Paid" if is_paid else "❌ Unpaid")
                
                btn_label = "Mark Unpaid" if is_paid else "Mark Paid"
                btn_type = "secondary" if is_paid else "primary"
                
                with c4:
                    if st.button(btn_label, key=f"pay_btn_{plot['plot_number']}", type=btn_type, use_container_width=True):
                        try:
                            new_status = not is_paid
                            supabase.table('garden_plots').update({
                                'paid': new_status,
                                'updated_at': datetime.now().isoformat()
                            }).eq('plot_number', plot['plot_number']).execute()
                            
                            # 🔥 AUDIT LOG: Record the payment change
                            action_type = "MARK_PAID" if new_status else "MARK_UNPAID"
                            log_action(st.session_state.user_role, action_type, f"Plot {plot['plot_number']} - {owner_name}", str(plot['plot_number']))
                            
                            st.success(f"Plot {plot['plot_number']} updated!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")

    # ─── TAB 5: Audit Logs ─────────────────────────────────────
    with tab5:
        st.subheader("📜 System Audit Logs")
        st.caption("Track critical changes made by Admins and Chairmen.")
        
        try:
            logs = supabase.table('audit_logs').select("*").order('timestamp', desc=True).limit(50).execute().data
            if logs:
                df_logs = pd.DataFrame(logs)
                df_logs = df_logs[['timestamp', 'user_role', 'action', 'details']]
                df_logs['timestamp'] = pd.to_datetime(df_logs['timestamp']).dt.strftime('%d %b %Y, %I:%M %p')
                df_logs.columns = ['Time', 'Role', 'Action', 'Details']
                
                st.dataframe(df_logs, use_container_width=True, hide_index=True)
            else:
                st.info("No audit logs recorded yet.")
        except Exception as e:
            st.error(f"Error loading logs: {e}")