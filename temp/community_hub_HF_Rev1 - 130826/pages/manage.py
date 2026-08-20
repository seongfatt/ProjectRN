def show_manage(selected_date):
    import streamlit as st
    import pandas as pd
    import random
    from datetime import datetime
    from config import supabase, DB_CONNECTED, refresh_data, load_activities
    from utils import mask_phone, clean_phone_number, log_action, find_participant_by_id
    from services import RegistrationService
    from pages.residents import show_face_enrollment

    # ─── HELPER: Get/Set System Settings ──────────────────────
    def get_setting(key, default=None):
        if not DB_CONNECTED: return default
        try:
            r = supabase.table('system_settings').select('setting_value').eq('setting_key', key).single().execute()
            return r.data['setting_value'] if r.data else default
        except:
            return default

    def save_setting(key, value):
        if not DB_CONNECTED: return False
        try:
            supabase.table('system_settings').upsert({
                'setting_key': key, 'setting_value': str(value), 'updated_at': datetime.now().isoformat()
            }, on_conflict='setting_key').execute()
            return True
        except:
            return False

    st.header("Management")
    if not DB_CONNECTED:
        st.error("Database not connected")
        return

    # 🔥 CRITICAL FIX: Force a fresh participant load every time this tab loads
    from utils import load_participants
    st.session_state.participants = load_participants()

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Participants", "Activities", "Convert Status", "💰 Finance & Payment", "📜 Audit Logs"])

    # ── TAB 1: Participants ───────────────────────────────────
    with tab1:
        if st.session_state.user_role == 'admin':
            with st.expander("Register New Participant"):
                name = st.text_input("Full Name", key="new_p_name")
                contact = st.text_input("Contact", key="new_p_contact")
                no_phone = st.checkbox("👴 Elderly without phone", key="new_p_no_phone")
                indemnity = st.checkbox("Indemnity Signed", key="new_p_indemnity")
                st.markdown("---")
                st.markdown("**👤 Member Type:**")
                member_type = st.radio(
                    "Select member category:",
                    ["Resident", "RN Member", "Volunteer Member", "Gardener"],
                    horizontal=True,
                    key="new_p_member_type"
                )
                block_consent = st.checkbox("🏢 I agree to share my block information (Optional)", key="new_p_block_consent")
                block_no = ""
                if block_consent:
                    block_no = st.text_input("Block No.", placeholder="e.g., 622, 624A", key="new_p_block_no").strip().upper()
                
                if st.button("Register", type="primary", use_container_width=True, key="new_p_submit"):
                    if not name.strip():
                        st.error("Name is required")
                    else:
                        # ✅ Use RegistrationService
                        success, message, new_id = RegistrationService.register_resident(
                            name=name,
                            contact=contact,
                            no_phone=no_phone,
                            indemnity=indemnity,
                            member_type=member_type,
                            block_no=block_no,
                            registration_date=str(selected_date)
                        )
                        if success:
                            st.success(f"✅ Added {name} as **{member_type}**!")
                            st.session_state.participants = load_participants()
                            refresh_data()
                            # Clear form fields
                            st.session_state["new_p_name"] = ""
                            st.session_state["new_p_contact"] = ""
                            st.session_state["new_p_block_no"] = ""
                            st.session_state["new_p_no_phone"] = False
                            st.session_state["new_p_indemnity"] = False
                            st.session_state["new_p_block_consent"] = False
                            st.rerun()
                        else:
                            st.error(message)
            
            with st.expander("Indemnity Status"):
                unsigned = [p for p in st.session_state.participants if not p.get('indemnity') and p.get('active', True)]
                for p in unsigned:
                    c1, c2 = st.columns([3, 1])
                    c1.write(f"🔴 {p['name']}")
                    if c2.button("Mark Signed", key=f"ind_{p['id']}"):
                        supabase.table('participants').update({'indemnity': True}).eq('id', p['id']).execute()
                        st.session_state.participants = load_participants()
                        refresh_data()
                        st.rerun()
            
            with st.expander("🗑️ Remove Participant"):
                st.warning("Removing a participant will deactivate them.")
                with st.expander("📋 Show All Active Residents (Click to View)"):
                    active_list_all = [p for p in st.session_state.participants if p.get('active', True)]
                    if active_list_all:
                        st.caption(f"Total Active Residents: {len(active_list_all)}")
                        for p in active_list_all:
                            c1, c2, c3 = st.columns([3, 2, 1])
                            c1.write(f"**{p['name']}**")
                            c2.write(f"{mask_phone(p.get('contact', 'N/A'))} | {p.get('member_type', 'Resident')}")
                            if c3.button("Remove", key=f"list_remove_{p['id']}", type="secondary"):
                                try:
                                    supabase.table('participants').update({'active': False}).eq('id', p['id']).execute()
                                    st.session_state.participants = load_participants()
                                    refresh_data()
                                    st.success(f"✅ {p['name']} removed successfully.")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error removing: {e}")
                    else:
                        st.info("No active residents found.")
                st.divider()
                remove_search = st.text_input("Search to remove by Name or ID", placeholder="Type name or last 4 digits...", key="remove_search")
                st.session_state.participants = load_participants()
                active_list = [p for p in st.session_state.participants if p.get('active', True)]
                if remove_search:
                    s = remove_search.lower()
                    matches = [
                        p for p in active_list
                        if s in p['name'].lower() or s in str(p.get('contact', ''))[-4:]
                    ]
                    if matches:
                        for p in matches:
                            with st.container():
                                c1, c2, c3 = st.columns([3, 2, 1])
                                c1.write(f"**{p['name']}**")
                                c2.write(f" {mask_phone(p.get('contact', 'N/A'))}")
                                if c3.button("Remove", key=f"remove_{p['id']}", type="secondary"):
                                    try:
                                        supabase.table('participants').update({'active': False}).eq('id', p['id']).execute()
                                        st.session_state.participants = load_participants()
                                        refresh_data()
                                        st.success(f"✅ {p['name']} removed successfully.")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Error removing: {e}")
                    else:
                        st.caption("No participants found matching that name.")
            
            with st.expander("✏️ Update Resident Contact Info"):
                st.caption("Use this to add a phone number, block info, or change member type.")
                update_search = st.text_input("Search resident by Name or ID", key="update_search_contact")
                if update_search:
                    s = update_search.lower()
                    matches = [p for p in st.session_state.participants if p.get('active', True) and (s in p['name'].lower() or s in str(p.get('id', '')).lower())]
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
                            if st.session_state.get(f"edit_mode_{p['id']}"):
                                with st.form(f"update_form_{p['id']}"):
                                    new_contact = st.text_input("New Phone Number", value="" if current_contact == "NO_PHONE" else current_contact, key=f"new_phone_{p['id']}")
                                    new_block = st.text_input("Block No.", value="" if current_block == 'Not provided' else current_block, placeholder="e.g., 622, 624A", key=f"new_block_{p['id']}")
                                    member_types = ["Resident", "RN Member", "Volunteer Member", "Gardener"]
                                    default_index = member_types.index(current_type) if current_type in member_types else 0
                                    new_member_type = st.selectbox("👤 Member Type", member_types, index=default_index, key=f"new_member_type_{p['id']}")
                                    col_save, col_cancel = st.columns(2)
                                    with col_save:
                                        if st.form_submit_button("💾 Save Update", type="primary"):
                                            updates = {}
                                            if new_contact.strip():
                                                clean_contact = clean_phone_number(new_contact)
                                                dup_check = supabase.table('participants').select('id, name').eq('contact', clean_contact).eq('active', True).execute()
                                                is_dup = any(d['id'] != p['id'] for d in dup_check.data) if dup_check.data else False
                                                if is_dup:
                                                    st.error(f"⛔ This phone number is already used by: {dup_check.data[0]['name']}")
                                                    st.stop()
                                                else:
                                                    updates['contact'] = clean_contact
                                            elif new_contact.strip() == "" and current_contact != "NO_PHONE":
                                                updates['contact'] = "NO_PHONE"
                                            if new_block.strip():
                                                updates['block_no'] = new_block.strip().upper()
                                            if new_member_type != current_type:
                                                updates['member_type'] = new_member_type
                                            if updates:
                                                try:
                                                    supabase.table('participants').update(updates).eq('id', p['id']).execute()
                                                    st.success("✅ Resident updated successfully!")
                                                    st.session_state.participants = load_participants()
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
            
            # ─── ✅ FACE ENROLLMENT ───
            # This appears at the bottom of the Participants tab
            st.markdown("---")
            show_face_enrollment()
            
        else:
            st.info("🔒 Participant management is restricted to System Admins.")

    # ── TAB 2: Activities ──────────────────────────────────────
    with tab2:
        MAX_SESSIONS = 4
        try:
            acts = supabase.table('activities').select("*").order('id').execute().data or []
        except Exception:
            acts = []
        if not acts:
            st.info("No activities configured.")
        else:
            for a in acts:
                act_id = a['id']
                saved_labels = [(a.get(f'session_{i}_label') or '').strip() for i in range(1, MAX_SESSIONS + 1)]
                saved_count = max([i + 1 for i, l in enumerate(saved_labels) if l] or [1])
                c1, c2, c3, c4 = st.columns([3, 3, 1, 1])
                c1.write(f"**{a['name']}**")
                c2.write(" | ".join([l for l in saved_labels if l]))
                c3.caption("⏰ Time-Gated" if a.get('enable_time_validation') else "🕒 All-Day")
                if not a.get('active'):
                    c3.caption("⚪ INACTIVE")
                with c4:
                    if st.session_state.user_role == 'admin':
                        if not a.get('active'):
                            if st.button("♻️ Restore", key=f"act_restore_{act_id}"):
                                supabase.table('activities').update({'active': True}).eq('id', act_id).execute()
                                refresh_data()
                                st.rerun()
                        else:
                            if st.button("🗑️", key=f"act_del_{act_id}"):
                                supabase.table('activities').update({'active': False}).eq('id', act_id).execute()
                                refresh_data()
                                st.rerun()
                        if st.button("✏️ Edit", key=f"act_edit_{act_id}"):
                            st.session_state[f"edit_act_{act_id}"] = True
                            st.session_state[f"num_sess_{act_id}"] = saved_count
                            st.rerun()
                
                if st.session_state.get(f"edit_act_{act_id}"):
                    st.session_state.setdefault(f"num_sess_{act_id}", saved_count)
                    st.subheader(f"Edit: {a['name']}")
                    bc1, bc2, bc3 = st.columns([1, 1, 2])
                    with bc1:
                        if st.button("➕ Add Session", key=f"add_sess_{act_id}"):
                            if st.session_state[f"num_sess_{act_id}"] < MAX_SESSIONS:
                                st.session_state[f"num_sess_{act_id}"] += 1
                                st.rerun()
                    with bc2:
                        if st.button("➖ Remove Last Session", key=f"rm_sess_{act_id}"):
                            if st.session_state[f"num_sess_{act_id}"] > 1:
                                st.session_state[f"num_sess_{act_id}"] -= 1
                                st.rerun()
                    with bc3:
                        st.caption(f"Editing **{st.session_state[f'num_sess_{act_id}']}** session(s) — max {MAX_SESSIONS}.")
                    enable_time_val = st.checkbox(
                        "✅ Enable Check-In Time Window",
                        value=bool(a.get('enable_time_validation', False)),
                        key=f"edit_enable_time_{act_id}"
                    )
                    num = st.session_state[f"num_sess_{act_id}"]
                    edit_vals = {}
                    for i in range(1, num + 1):
                        st.markdown(f"**Session {i}**")
                        lc, tc1, tc2 = st.columns([2, 1, 1])
                        with lc:
                            edit_vals[f'label_{i}'] = st.text_input(
                                f"Session {i} Label",
                                value=a.get(f'session_{i}_label') or f"Session {i}",
                                key=f"edit_s{i}_label_{act_id}"
                            )
                        with tc1:
                            sv = a.get(f'session_{i}_start_time')
                            try: sv_t = datetime.strptime(sv, "%H:%M").time() if sv else datetime.strptime("19:45", "%H:%M").time()
                            except: sv_t = datetime.strptime("19:45", "%H:%M").time()
                            edit_vals[f'start_{i}'] = st.time_input("Opens", value=sv_t, step=60, key=f"edit_s{i}_start_{act_id}", disabled=not enable_time_val)
                        with tc2:
                            ev = a.get(f'session_{i}_end_time')
                            try: ev_t = datetime.strptime(ev, "%H:%M").time() if ev else datetime.strptime("20:15", "%H:%M").time()
                            except: ev_t = datetime.strptime("20:15", "%H:%M").time()
                            edit_vals[f'end_{i}'] = st.time_input("Closes", value=ev_t, step=60, key=f"edit_s{i}_end_{act_id}", disabled=not enable_time_val)
                    st.markdown("---")
                    with st.form(f"edit_act_form_{act_id}"):
                        edit_name = st.text_input("Activity Name", value=a['name'], key=f"edit_name_{act_id}")
                        col_save, col_cancel = st.columns(2)
                        with col_save:
                            if st.form_submit_button("💾 Save Changes", type="primary"):
                                update_data = {
                                    "name": edit_name.upper(),
                                    "enable_time_validation": enable_time_val,
                                }
                                for i in range(1, MAX_SESSIONS + 1):
                                    if i <= num:
                                        update_data[f"session_{i}_label"] = edit_vals[f"label_{i}"].strip()
                                        update_data[f"session_{i}_start_time"] = edit_vals[f"start_{i}"].strftime("%H:%M") if enable_time_val else None
                                        update_data[f"session_{i}_end_time"] = edit_vals[f"end_{i}"].strftime("%H:%M") if enable_time_val else None
                                    else:
                                        update_data[f"session_{i}_label"] = ""
                                        update_data[f"session_{i}_start_time"] = None
                                        update_data[f"session_{i}_end_time"] = None
                                supabase.table('activities').update(update_data).eq('id', act_id).execute()
                                refresh_data()
                                st.session_state[f"edit_act_{act_id}"] = False
                                st.success("✅ Activity updated!")
                                st.rerun()
                        with col_cancel:
                            if st.form_submit_button("Cancel"):
                                st.session_state[f"edit_act_{act_id}"] = False
                                st.rerun()
        
        if st.session_state.user_role == 'admin':
            with st.expander("➕ Add New Activity"):
                st.session_state.setdefault("num_sess_add", 1)
                ac1, ac2 = st.columns(2)
                with ac1:
                    if st.button("➕ Add Session", key="add_sess_new"):
                        if st.session_state.num_sess_add < MAX_SESSIONS:
                            st.session_state.num_sess_add += 1
                            st.rerun()
                with ac2:
                    if st.button("➖ Remove Session", key="rm_sess_new"):
                        if st.session_state.num_sess_add > 1:
                            st.session_state.num_sess_add -= 1
                            st.rerun()
                st.caption(f"This activity will have **{st.session_state.num_sess_add}** session(s).")
                enable_time = st.checkbox("Enable Check-In Time Window", value=False, key="add_enable_time")
                add_vals = {}
                for i in range(1, st.session_state.num_sess_add + 1):
                    st.markdown(f"**Session {i}**")
                    lc, tc1, tc2 = st.columns([2, 1, 1])
                    with lc:
                        add_vals[f'label_{i}'] = st.text_input(f"Session {i} Label", value=f"Session {i}", key=f"add_s{i}_label")
                    with tc1:
                        add_vals[f'start_{i}'] = st.time_input("Opens", value=datetime.strptime("19:45", "%H:%M").time(), step=60, key=f"add_s{i}_start", disabled=not enable_time)
                    with tc2:
                        add_vals[f'end_{i}'] = st.time_input("Closes", value=datetime.strptime("20:15", "%H:%M").time(), step=60, key=f"add_s{i}_end", disabled=not enable_time)
                st.markdown("---")
                with st.form("add_act"):
                    act_name = st.text_input("Activity Name")
                    if st.form_submit_button("Add Activity"):
                        if act_name:
                            data = {
                                "name": act_name.upper(), "active": True,
                                "enable_time_validation": enable_time,
                            }
                            for i in range(1, MAX_SESSIONS + 1):
                                if i <= st.session_state.num_sess_add:
                                    data[f"session_{i}_label"] = add_vals[f"label_{i}"].strip()
                                    data[f"session_{i}_start_time"] = add_vals[f"start_{i}"].strftime("%H:%M") if enable_time else None
                                    data[f"session_{i}_end_time"] = add_vals[f"end_{i}"].strftime("%H:%M") if enable_time else None
                                else:
                                    data[f"session_{i}_label"] = ""
                                    data[f"session_{i}_start_time"] = None
                                    data[f"session_{i}_end_time"] = None
                            supabase.table('activities').insert(data).execute()
                            refresh_data()
                            st.session_state.num_sess_add = 1
                            st.rerun()

    # ── TAB 3: Convert Status ─────────────────────────────────
    with tab3:
        st.info("Residents automatically convert from 'New' to 'Regular' after 3 attendances.")
        newbies = [p for p in st.session_state.participants if p.get('is_new') and p.get('active', True)]
        st.write(f"**{len(newbies)} New Residents**")
        import time
        for p in newbies:
            c = 0
            for attempt in range(3):
                try:
                    result = supabase.table('attendance').select('*', count='exact').eq('participant_id', p['id']).execute()
                    c = result.count
                    break
                except Exception:
                    if attempt < 2:
                        time.sleep(1)
                    else:
                        c = 0
            st.write(f"{p['name']} - {c} attendances")
            if c >= 3:
                if st.button(f"Convert {p['name']}", key=f"conv_{p['id']}"):
                    supabase.table('participants').update({'is_new': False}).eq('id', p['id']).execute()
                    refresh_data()
                    st.rerun()

    # ── TAB 4: Finance & Payment Status ──────────────────────
    with tab4:
        st.subheader("💰 Garden Finance & Payment Management")
        with st.expander("⚙️ Garden Pricing & Settings (Admins/Chairmen only)", expanded=False):
            if st.session_state.user_role in ['admin', 'chairman']:
                st.markdown("**1. Global Pricing (Default)**")
                current_price = get_setting('garden_monthly_rent', '15.00')
                new_price = st.number_input("Default Monthly Rent ($)", min_value=0.0, max_value=100.0, value=float(current_price), step=0.50, key="garden_price")
                st.divider()
                st.markdown("**2. Per-Plot-Type Pricing**")
                per_plot_enabled = get_setting('garden_per_plot_pricing_enabled', 'false') == 'true'
                enable_per_plot = st.checkbox("Enable Different Prices Per Plot Type", value=per_plot_enabled, key="enable_per_plot_check")
                if enable_per_plot:
                    st.caption("When enabled, the system will ignore the 'Default Monthly Rent' above and use these specific prices.")
                    cA, cB, cC, cD = st.columns(4)
                    with cA:
                        price_A = st.number_input("Type A Price ($)", min_value=0.0, max_value=100.0, value=float(get_setting('garden_price_type_A', '15.00')), step=0.50, key="price_A")
                    with cB:
                        price_B = st.number_input("Type B Price ($)", min_value=0.0, max_value=100.0, value=float(get_setting('garden_price_type_B', '15.00')), step=0.50, key="price_B")
                    with cC:
                        price_C = st.number_input("Type C Price ($)", min_value=0.0, max_value=100.0, value=float(get_setting('garden_price_type_C', '15.00')), step=0.50, key="price_C")
                    with cD:
                        price_D = st.number_input("Type D Price ($)", min_value=0.0, max_value=100.0, value=float(get_setting('garden_price_type_D', '15.00')), step=0.50, key="price_D")
                st.divider()
                if st.button("💾 Save All Pricing Settings", type="primary"):
                    save_setting('garden_monthly_rent', str(new_price))
                    save_setting('garden_per_plot_pricing_enabled', str(enable_per_plot))
                    if enable_per_plot:
                        save_setting('garden_price_type_A', str(price_A))
                        save_setting('garden_price_type_B', str(price_B))
                        save_setting('garden_price_type_C', str(price_C))
                        save_setting('garden_price_type_D', str(price_D))
                    st.success("✅ Pricing settings saved successfully!")
                    st.rerun()
            else:
                st.info("🔒 Pricing settings are restricted to Admins and Chairmen.")
            st.divider()
            st.markdown("**🧾 Log Gardening Expense**")
            st.caption("Record expenses (e.g., soil, tools, water) to track net income.")
            with st.form("expense_form"):
                exp_desc = st.text_input("Expense Description *", placeholder="e.g., Bought 10 bags of soil")
                exp_amt = st.number_input("Amount ($) *", min_value=0.01, step=1.0, format="%.2f")
                exp_submit = st.form_submit_button("➕ Log Expense", type="primary", use_container_width=True)
                if exp_submit:
                    if exp_desc.strip() and exp_amt > 0:
                        try:
                            supabase.table('garden_expenses').insert({
                                "description": exp_desc.strip(),
                                "amount": exp_amt,
                                "logged_by": st.session_state.user_role
                            }).execute()
                            st.success("✅ Expense logged successfully!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error logging expense: {e}")
                    else:
                        st.error("Please provide both a description and a valid amount.")
        
        st.divider()
        
        # ── B. Payment Dashboard ──
        st.caption("Search, filter, and manage payment status for all occupied garden plots.")
        plots = st.session_state.plots
        block_opts = sorted({(p.get('block_name') or '').strip() for p in plots if p.get('occupied') and (p.get('block_name') or '').strip()})
        fin_block = st.selectbox("📍 Filter by Block", ["All Blocks"] + block_opts, key="fin_block")
        occupied_plots = [p for p in plots if p.get('occupied') and (fin_block == "All Blocks" or (p.get('block_name') or '').strip() == fin_block)]
        monthly_rent = float(get_setting('garden_monthly_rent', '15.00'))
        if not occupied_plots:
            st.info("No occupied plots to manage.")
        else:
            dashboard_data = []
            for plot in occupied_plots:
                owner_id = plot.get('user_id')
                owner_data = find_participant_by_id(owner_id) if owner_id else None
                owner_name = owner_data['name'] if owner_data else "Unknown"
                owner_contact = mask_phone(owner_data.get('contact', 'N/A')) if owner_data else "N/A"
                dashboard_data.append({
                    "Plot #": plot['plot_number'],
                    "Block": (plot.get('block_name') or 'Block 622'),
                    "Plot Type": plot['plot_type'],
                    "Owner Name": owner_name,
                    "Contact": owner_contact,
                    "Paid": plot.get('paid', False),
                    "Block": (plot.get('block_name') or '').strip(),
                    "user_id": owner_id
                })
            total_occupied = len(dashboard_data)
            total_paid = sum(1 for d in dashboard_data if d['Paid'])
            total_unpaid = total_occupied - total_paid
            per_plot_enabled = get_setting('garden_per_plot_pricing_enabled', 'false') == 'true'
            if per_plot_enabled:
                price_A = float(get_setting('garden_price_type_A', '15.00'))
                price_B = float(get_setting('garden_price_type_B', '15.00'))
                price_C = float(get_setting('garden_price_type_C', '15.00'))
                price_D = float(get_setting('garden_price_type_D', '15.00'))
                total_revenue_collected = 0.0
                for plot in dashboard_data:
                    if plot['Paid']:
                        ptype = plot['Plot Type']
                        if ptype == 'A': total_revenue_collected += price_A
                        elif ptype == 'B': total_revenue_collected += price_B
                        elif ptype == 'C': total_revenue_collected += price_C
                        elif ptype == 'D': total_revenue_collected += price_D
            else:
                total_revenue_collected = total_paid * monthly_rent
            try:
                exp_data = supabase.table('garden_expenses').select('amount').execute().data
                total_expenses = sum(e['amount'] for e in exp_data) if exp_data else 0.0
            except:
                total_expenses = 0.0
            net_income = total_revenue_collected - total_expenses
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Occupied", total_occupied)
            c2.metric("✅ Paid", total_paid, delta_color="normal")
            c3.metric("❌ Unpaid", total_unpaid, delta_color="inverse")
            c4.metric("💰 Monthly Rent", f"${monthly_rent:.2f}")
            st.caption(f"📍 Showing metrics for: **{fin_block}**")
            st.markdown("---")
            c_fin1, c_fin2, c_fin3 = st.columns(3)
            c_fin1.metric("💵 Revenue Collected", f"${total_revenue_collected:.2f}")
            c_fin2.metric("🧾 Total Expenses", f"${total_expenses:.2f}", delta_color="inverse")
            c_fin3.metric("📈 Net Income (Profit)", f"${net_income:.2f}", delta_color="normal")
            st.divider()
            col_search, col_filter = st.columns([3, 1])
            with col_search:
                search_query = st.text_input("🔍 Search by Plot Number, Owner Name, or Contact", placeholder="e.g., 5, Edmund, 9821...")
            with col_filter:
                filter_status = st.selectbox("Filter by Status", ["All", "Paid", "Unpaid"], index=0)
            filtered_data = dashboard_data
            if search_query:
                s = search_query.lower()
                filtered_data = [
                    d for d in filtered_data
                    if s in str(d['Plot #']) or s in d['Owner Name'].lower() or s in d['Contact'].lower()
                ]
            if filter_status == "Paid":
                filtered_data = [d for d in filtered_data if d['Paid']]
            elif filter_status == "Unpaid":
                filtered_data = [d for d in filtered_data if not d['Paid']]
            st.caption(f"Showing {len(filtered_data)} plot(s)")
            for plot_info in filtered_data:
                plot_num = plot_info['Plot #']
                plot_block = plot_info['Block']
                owner_name = plot_info['Owner Name']
                contact = plot_info['Contact']
                is_paid = plot_info['Paid']
                plot_type = plot_info['Plot Type']
                if is_paid:
                    bg_color = "#e8f5e9"; border_color = "#4caf50"; status_icon = "✅"; status_text = "Paid"; btn_label = "Mark Unpaid"; btn_type = "secondary"
                else:
                    bg_color = "#ffebee"; border_color = "#f44336"; status_icon = "❌"; status_text = "Unpaid"; btn_label = "Mark Paid"; btn_type = "primary"
                per_plot_enabled = get_setting('garden_per_plot_pricing_enabled', 'false') == 'true'
                if per_plot_enabled:
                    if plot_type == 'A': actual_price = float(get_setting('garden_price_type_A', '15.00'))
                    elif plot_type == 'B': actual_price = float(get_setting('garden_price_type_B', '15.00'))
                    elif plot_type == 'C': actual_price = float(get_setting('garden_price_type_C', '15.00'))
                    elif plot_type == 'D': actual_price = float(get_setting('garden_price_type_D', '15.00'))
                    else: actual_price = monthly_rent
                else:
                    actual_price = monthly_rent
                st.markdown(f"""
                <div style="background-color: {bg_color}; border-left: 6px solid {border_color}; padding: 15px; border-radius: 8px; margin: 10px 0; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
                    <div>
                        <strong style="font-size: 18px;">Plot {plot_num}</strong>
                        <span style="background: #667eea; color: white; padding: 2px 10px; border-radius: 12px; font-size: 12px;">{plot_block}</span>
                        <span style="background: #333; color: white; padding: 2px 10px; border-radius: 12px; font-size: 12px;">Type {plot_type}</span>
                        <br>
                        <span style="font-size: 14px;">👤 {owner_name}</span> <span style="color: #777; font-size: 12px;">| 📞 {contact}</span>
                        <br><span style="font-size: 12px; color: #555;">Rent: ${actual_price:.2f}/month</span>
                    </div>
                    <div style="display: flex; align-items: center; gap: 15px;">
                        <span style="font-weight: bold; font-size: 16px; color: {border_color};">{status_icon} {status_text}</span>
                """, unsafe_allow_html=True)
                c1, c2 = st.columns([6, 1])
                with c2:
                    if st.button(btn_label, key=f"pay_dash_{plot_block}_{plot_num}", type=btn_type, use_container_width=True):
                        try:
                            new_status = not is_paid
                            supabase.table('garden_plots').update({'paid': new_status, 'updated_at': datetime.now().isoformat()}).eq('block_name', plot_info.get('Block', '')).eq('plot_number', plot_num).execute()
                            log_action(st.session_state.user_role, "MARK_PAID" if new_status else "MARK_UNPAID", f"Plot {plot_num} ({plot_block}) - {owner_name}", str(plot_num))
                            st.success(f"Plot {plot_num} ({plot_block}) status updated!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")
                st.markdown("</div>", unsafe_allow_html=True)

    # ── TAB 5: Audit Logs ─────────────────────────────────────
    with tab5:
        st.subheader("📜 Audit Logs")
        st.caption("View a chronological record of all significant actions taken in the system.")
        try:
            logs = supabase.table('audit_logs').select('*').order('timestamp', desc=True).limit(100).execute().data
            if logs:
                for log in logs:
                    ts = datetime.fromisoformat(log['timestamp']).strftime("%Y-%m-%d %H:%M:%S")
                    st.write(f"**[{ts}]** {log['user_role']} performed **{log['action']}** on **{log.get('target_id', log.get('target', 'N/A'))}**. Details: {log.get('details', 'N/A')}")
            else:
                st.info("No audit logs available.")
        except Exception as e:
            st.error(f"Error fetching audit logs: {e}")