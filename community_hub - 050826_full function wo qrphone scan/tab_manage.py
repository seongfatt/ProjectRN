import streamlit as st
import pandas as pd
import random
from datetime import datetime
from config import supabase, DB_CONNECTED, refresh_data, load_activities
from utils import mask_phone, clean_phone_number, log_action

def show_manage(selected_date):
    st.header("Management")
    if not DB_CONNECTED:
        st.error("Database not connected")
        return

    # Define tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Participants", "Activities", "Convert Status", "💰 Payment Status", "📜 Audit Logs"])

    # ─ TAB 1: Participants ───────────────────────────────────
    with tab1:
        # CHAIRMAN RESTRICTION: Hide registration and deletion
        if st.session_state.user_role == 'admin':
            
            with st.expander("Register New Participant"):
                with st.form("new_p"):
                    name = st.text_input("Full Name")
                    contact = st.text_input("Contact")
                    no_phone = st.checkbox("👴 Elderly without phone")
                    indemnity = st.checkbox("Indemnity Signed")
                    
                    # 🔥 NEW: Member Type Selection
                    st.markdown("---")
                    st.markdown("**👤 Member Type:**")
                    member_type = st.radio(
                        "Select member category:",
                        ["Resident", "RN Member", "Volunteer Member"],
                        horizontal=True,
                        key="new_p_member_type",
                        help="RN Member = Resident Network Committee | Volunteer Member = Activity Volunteer"
                    )
                    
                    if st.form_submit_button("Register"):
                        if name:
                            # Handle no phone case
                            final_contact = "NO_PHONE" if no_phone else contact.strip()
                            
                            # 🔥 ULTIMATE DUPLICATE CHECK
                            clean_contact = clean_phone_number(final_contact) if final_contact != "NO_PHONE" else None

                            try:
                                # 1. Check Phone (Strict Block)
                                if clean_contact:
                                    res_phone = supabase.table('participants').select('name').eq('contact', clean_contact).eq('active', True).execute()
                                    if res_phone.data:
                                        st.error(f"⛔ **Phone number already exists!**\n\nResident: **{res_phone.data[0]['name']}**\n\nPlease search for them in the system instead.")
                                        st.stop()

                                # 2. Check Name (Smart Logic)
                                res_name = supabase.table('participants').select('name', 'contact').eq('name', name.strip().upper()).eq('active', True).execute()
                                if res_name.data:
                                    if final_contact == "NO_PHONE":
                                        st.error(f"⛔ **Name already exists!**\n\nA resident named **{name.strip().upper()}** is already registered without a phone number.\n\nTo register a different person with the same name, you MUST provide their phone number to distinguish them.")
                                        st.stop()
                                    else:
                                        st.warning(f"⚠️ **Name Match:** A resident named '{name.strip().upper()}' already exists. Proceeding because phone numbers differ.")
                                        
                            except Exception as e:
                                st.error(f"Error checking duplicates: {e}")
                                st.stop()

                            # If no duplicates, proceed with registration
                            new_p = {
                                "id": datetime.now().strftime("%Y%m%d%H%M%S") + str(random.randint(10, 99)), 
                                "name": name.upper(), 
                                "contact": final_contact,
                                "indemnity": indemnity, 
                                "is_new": True, 
                                "active": True, 
                                "registration_date": str(selected_date),
                                "member_type": member_type  # 🔥 NEW: Save member type
                            }
                            supabase.table('participants').insert(new_p).execute()
                            refresh_data()
                            st.success(f"Added {name} as **{member_type}**!")
                            st.rerun()
                        else:
                            st.error("Name is required")

            with st.expander("Indemnity Status"):
                unsigned = [p for p in st.session_state.participants if not p.get('indemnity') and p.get('active', True)]
                for p in unsigned:
                    c1, c2 = st.columns([3, 1])
                    c1.write(f" {p['name']}")
                    if c2.button("Mark Signed", key=f"ind_{p['id']}"):
                        supabase.table('participants').update({'indemnity': True}).eq('id', p['id']).execute()
                        refresh_data()
                        st.rerun()

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
                                    refresh_data()
                                    st.rerun()

            # 🔥 NEW: Update Resident Contact Info & Block No. & Member Type
            with st.expander("✏️ Update Resident Contact Info"):
                st.caption("Use this to add a phone number, block info, or change member type for existing residents.")
                update_search = st.text_input("Search resident by Name or ID", key="update_search_contact")
                
                if update_search:
                    s = update_search.lower()
                    matches = [p for p in st.session_state.participants if p.get('active', True) and (s in p['name'].lower() or s in str(p.get('id', '')).lower())]
                    
                    if matches:
                        for p in matches:
                            with st.container():
                                c1, c2, c3 = st.columns([3, 2, 1])
                                c1.write(f"**{p['name']}**")
                                current_contact = p.get('contact', 'N/A')
                                current_block = p.get('block_no', 'Not provided')
                                current_type = p.get('member_type', 'Resident')
                                c2.write(f"Phone: {current_contact if current_contact != 'NO_PHONE' else ' No Phone'} | Block: {current_block} | Type: {current_type}")
                                
                                with c3:
                                    if st.button("Edit", key=f"edit_btn_{p['id']}"):
                                        st.session_state[f"edit_mode_{p['id']}"] = True
                                
                                # Show Edit Form if activated
                                if st.session_state.get(f"edit_mode_{p['id']}"):
                                    with st.form(f"update_form_{p['id']}"):
                                        new_contact = st.text_input(
                                            "New Phone Number", 
                                            value="" if current_contact == "NO_PHONE" else current_contact,
                                            key=f"new_phone_{p['id']}"
                                        )
                                        new_block = st.text_input(
                                            "Block No.", 
                                            value="" if current_block == 'Not provided' else current_block,
                                            placeholder="e.g., 622, 624A",
                                            key=f"new_block_{p['id']}"
                                        )
                                        
                                        # 🔥 NEW: Member Type Dropdown
                                        member_types = ["Resident", "RN Member", "Volunteer Member"]
                                        default_index = member_types.index(current_type) if current_type in member_types else 0
                                        
                                        new_member_type = st.selectbox(
                                            "👤 Member Type", 
                                            member_types, 
                                            index=default_index,
                                            key=f"new_member_type_{p['id']}"
                                        )
                                        
                                        col_save, col_cancel = st.columns(2)
                                        with col_save:
                                            if st.form_submit_button("💾 Save Update", type="primary"):
                                                updates = {}
                                                
                                                # Update phone if provided
                                                if new_contact.strip():
                                                    clean_contact = clean_phone_number(new_contact)
                                                    
                                                    # Check for duplicates (excluding the current resident)
                                                    dup_check = supabase.table('participants').select('id, name').eq('contact', clean_contact).eq('active', True).execute()
                                                    is_dup = any(d['id'] != p['id'] for d in dup_check.data) if dup_check.data else False
                                                    
                                                    if is_dup:
                                                        st.error(f" This phone number is already used by: {dup_check.data[0]['name']}")
                                                        st.stop()
                                                    else:
                                                        updates['contact'] = clean_contact
                                                elif new_contact.strip() == "":
                                                    # If field is empty and was NO_PHONE, keep it
                                                    if current_contact != "NO_PHONE":
                                                        updates['contact'] = "NO_PHONE"
                                                
                                                # Update block if provided
                                                if new_block.strip():
                                                    updates['block_no'] = new_block.strip().upper()
                                                    
                                                # 🔥 NEW: Check if Member Type changed
                                                if new_member_type != current_type:
                                                    updates['member_type'] = new_member_type
                                                
                                                if updates:
                                                    try:
                                                        supabase.table('participants').update(updates).eq('id', p['id']).execute()
                                                        st.success("✅ Resident updated successfully!")
                                                        refresh_data()
                                                        st.session_state[f"edit_mode_{p['id']}"] = False
                                                        st.rerun()
                                                    except Exception as e:
                                                        st.error(f"Error: {e}")
                                                else:
                                                    st.error("No changes to save.")
                                        with col_cancel:
                                            if st.form_submit_button("Cancel"):
                                                st.session_state[f"edit_mode_{p['id']}"] = False
                                                st.rerun()
                    else:
                        st.info("No residents found.")
        else:
            st.info("🔒 Participant management is restricted to System Admins.")

            # ── TAB 2: Activities ─────────────────────────────────────
    with tab2:
        acts = load_activities()
        if not acts:
            st.info("No activities configured.")
        else:
            for a in acts:
                c1, c2, c3, c4 = st.columns([3, 2, 1, 1])
                c1.write(f"**{a['name']}**")
                c2.write(f"{a.get('session_1_label', 'S1')} | {a.get('session_2_label', 'S2')}")
                
                # Show time validation status
                time_status = "⏰ Time-Gated" if a.get('enable_time_validation') else "🕒 All-Day"
                c3.caption(time_status)
                
                with c4:
                    if st.session_state.user_role == 'admin':
                        if st.button("✏️ Edit", key=f"act_edit_{a['id']}"):
                            st.session_state[f"edit_act_{a['id']}"] = True
                            st.rerun()
                        if st.button("🗑️", key=f"act_del_{a['id']}"):
                            supabase.table('activities').update({'active': False}).eq('id', a['id']).execute()
                            refresh_data()
                            st.rerun()
                
                # Edit Form
                if st.session_state.get(f"edit_act_{a['id']}"):
                    # 🔥 FIX: Move checkbox OUTSIDE the form so it can trigger rerun
                    st.subheader(f"Edit: {a['name']}")
                    
                    enable_time_val = st.checkbox(
                        "✅ Enable Check-In Time Window",
                        value=bool(a.get('enable_time_validation', False)),
                        key=f"edit_enable_time_{a['id']}"
                    )
                    
                    # Initialize time variables
                    edit_s1_start = edit_s1_end = edit_s2_start = edit_s2_end = None
                    
                    if enable_time_val:
                        col_t1, col_t2 = st.columns(2)
                        with col_t1:
                            st.markdown("**Session 1 Times**")
                            s1_start_val = a.get('session_1_start_time', '19:45')
                            s1_end_val = a.get('session_1_end_time', '20:15')
                            
                            try:
                                start_time_val = datetime.strptime(s1_start_val, "%H:%M").time() if s1_start_val else datetime.strptime("19:45", "%H:%M").time()
                            except:
                                start_time_val = datetime.strptime("19:45", "%H:%M").time()
                            
                            try:
                                end_time_val = datetime.strptime(s1_end_val, "%H:%M").time() if s1_end_val else datetime.strptime("20:15", "%H:%M").time()
                            except:
                                end_time_val = datetime.strptime("20:15", "%H:%M").time()
                            
                            edit_s1_start = st.time_input("Check-in Opens", value=start_time_val, key=f"edit_s1_start_{a['id']}")
                            edit_s1_end = st.time_input("Check-in Closes", value=end_time_val, key=f"edit_s1_end_{a['id']}")
                        
                        with col_t2:
                            st.markdown("**Session 2 Times**")
                            s2_start_val = a.get('session_2_start_time', '20:45')
                            s2_end_val = a.get('session_2_end_time', '21:15')
                            
                            try:
                                start_time_val = datetime.strptime(s2_start_val, "%H:%M").time() if s2_start_val else datetime.strptime("20:45", "%H:%M").time()
                            except:
                                start_time_val = datetime.strptime("20:45", "%H:%M").time()
                            
                            try:
                                end_time_val = datetime.strptime(s2_end_val, "%H:%M").time() if s2_end_val else datetime.strptime("21:15", "%H:%M").time()
                            except:
                                end_time_val = datetime.strptime("21:15", "%H:%M").time()
                            
                            edit_s2_start = st.time_input("Check-in Opens", value=start_time_val, key=f"edit_s2_start_{a['id']}")
                            edit_s2_end = st.time_input("Check-in Closes", value=end_time_val, key=f"edit_s2_end_{a['id']}")
                    
                    st.markdown("---")
                    
                    # Now the form for the rest of the fields
                    with st.form(f"edit_act_form_{a['id']}"):
                        edit_name = st.text_input("Activity Name", value=a['name'], key=f"edit_name_{a['id']}")
                        edit_s1_label = st.text_input("Session 1 Label", value=a.get('session_1_label', ''), key=f"edit_s1_label_{a['id']}")
                        edit_s2_label = st.text_input("Session 2 Label (Optional)", value=a.get('session_2_label', ''), key=f"edit_s2_label_{a['id']}")
                        
                        col_save, col_cancel = st.columns(2)
                        with col_save:
                            if st.form_submit_button("💾 Save Changes", type="primary"):
                                update_data = {
                                    "name": edit_name.upper(),
                                    "session_1_label": edit_s1_label,
                                    "session_2_label": edit_s2_label,
                                    "enable_time_validation": enable_time_val,
                                    "session_1_start_time": edit_s1_start.strftime("%H:%M") if edit_s1_start else None,
                                    "session_1_end_time": edit_s1_end.strftime("%H:%M") if edit_s1_end else None,
                                    "session_2_start_time": edit_s2_start.strftime("%H:%M") if edit_s2_start else None,
                                    "session_2_end_time": edit_s2_end.strftime("%H:%M") if edit_s2_end else None,
                                }
                                supabase.table('activities').update(update_data).eq('id', a['id']).execute()
                                refresh_data()
                                st.session_state[f"edit_act_{a['id']}"] = False
                                st.success("✅ Activity updated!")
                                st.rerun()
                        with col_cancel:
                            if st.form_submit_button("Cancel"):
                                st.session_state[f"edit_act_{a['id']}"] = False
                                st.rerun()
        
        if st.session_state.user_role == 'admin':
            with st.expander("➕ Add New Activity"):
                with st.form("add_act"):
                    act_name = st.text_input("Activity Name")
                    s1 = st.text_input("Session 1 Label", value="Session 1 (7PM-8PM)")
                    s2 = st.text_input("Session 2 Label (Optional)", value="")
                    
                    st.markdown("---")
                    st.markdown("** Time-Gated Check-In (Optional)**")
                    enable_time = st.checkbox("Enable Check-In Time Window", value=False, key="add_enable_time")
                    
                    if enable_time:
                        col_t1, col_t2 = st.columns(2)
                        with col_t1:
                            add_s1_start = st.time_input("Session 1 Opens", value=datetime.strptime("19:45", "%H:%M").time(), key="add_s1_start")
                            add_s1_end = st.time_input("Session 1 Closes", value=datetime.strptime("20:15", "%H:%M").time(), key="add_s1_end")
                        with col_t2:
                            add_s2_start = st.time_input("Session 2 Opens", value=datetime.strptime("20:45", "%H:%M").time(), key="add_s2_start")
                            add_s2_end = st.time_input("Session 2 Closes", value=datetime.strptime("21:15", "%H:%M").time(), key="add_s2_end")
                    else:
                        add_s1_start = add_s1_end = add_s2_start = add_s2_end = None
                    
                    if st.form_submit_button("Add Activity"):
                        if act_name:
                            supabase.table('activities').insert({
                                "name": act_name.upper(),
                                "session_1_label": s1,
                                "session_2_label": s2,
                                "active": True,
                                "enable_time_validation": enable_time,
                                "session_1_start_time": add_s1_start.strftime("%H:%M") if add_s1_start else None,
                                "session_1_end_time": add_s1_end.strftime("%H:%M") if add_s1_end else None,
                                "session_2_start_time": add_s2_start.strftime("%H:%M") if add_s2_start else None,
                                "session_2_end_time": add_s2_end.strftime("%H:%M") if add_s2_end else None,
                            }).execute()
                            refresh_data()
                            st.rerun()

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
                    refresh_data()
                    st.rerun()

    # ── TAB 4: Payment Status ─────────────────────────────────
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