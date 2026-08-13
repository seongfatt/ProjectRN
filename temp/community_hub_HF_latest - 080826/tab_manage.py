def show_manage(selected_date):
    import streamlit as st
    import pandas as pd
    import random
    from datetime import datetime
    from config import supabase, DB_CONNECTED, refresh_data, load_activities
    from utils import mask_phone, clean_phone_number, log_action, find_participant_by_id

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

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Participants", "Activities", "Convert Status", "💰 Finance & Payment", "📜 Audit Logs"])

    # ── TAB 1: Participants ───────────────────────────────────
    with tab1:
        if st.session_state.user_role == 'admin':
            with st.expander("Register New Participant"):
                with st.form("new_p"):
                    name = st.text_input("Full Name")
                    contact = st.text_input("Contact")
                    no_phone = st.checkbox("👴 Elderly without phone")
                    indemnity = st.checkbox("Indemnity Signed")
                    
                    st.markdown("---")
                    st.markdown("**👤 Member Type:**")
                    member_type = st.radio(
                        "Select member category:",
                        ["Resident", "RN Member", "Volunteer Member", "Gardener"],
                        horizontal=True,
                        key="new_p_member_type"
                    )
                    
                    if st.form_submit_button("Register"):
                        if name:
                            final_contact = "NO_PHONE" if no_phone else contact.strip()
                            clean_contact = clean_phone_number(final_contact) if final_contact != "NO_PHONE" else None

                            try:
                                if clean_contact:
                                    res_phone = supabase.table('participants').select('name').eq('contact', clean_contact).eq('active', True).execute()
                                    if res_phone.data:
                                        st.error(f"⛔ **Phone number already exists!**\n\nResident: **{res_phone.data[0]['name']}**")
                                        st.stop()

                                res_name = supabase.table('participants').select('name', 'contact').eq('name', name.strip().upper()).eq('active', True).execute()
                                if res_name.data:
                                    if final_contact == "NO_PHONE":
                                        st.error(f"⛔ **Name already exists!**\n\nA resident named **{name.strip().upper()}** is already registered without a phone number.")
                                        st.stop()
                                    else:
                                        st.warning(f"⚠️ **Name Match:** A resident named '{name.strip().upper()}' already exists. Proceeding because phone numbers differ.")
                            except Exception as e:
                                st.error(f"Error checking duplicates: {e}")
                                st.stop()

                            new_p = {
                                "id": datetime.now().strftime("%Y%m%d%H%M%S") + str(random.randint(10, 99)), 
                                "name": name.upper(), "contact": final_contact, "indemnity": indemnity, 
                                "is_new": True, "active": True, "registration_date": str(selected_date),
                                "member_type": member_type
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
                    c1.write(f"🔴 {p['name']}")
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
                    for p in matches:
                        with st.container():
                            c1, c2, c3 = st.columns([3, 2, 1])
                            c1.write(f"**{p['name']}**")
                            c2.write(f" {mask_phone(p.get('contact', 'N/A'))}")
                            if c3.button("Remove", key=f"remove_{p['id']}", type="secondary"):
                                supabase.table('participants').update({'active': False}).eq('id', p['id']).execute()
                                refresh_data()
                                st.rerun()

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
                
                # Edit Form (Checkbox OUTSIDE the form for instant reactivity)
                if st.session_state.get(f"edit_act_{a['id']}"):
                    st.subheader(f"Edit: {a['name']}")
                    
                    enable_time_val = st.checkbox(
                        "✅ Enable Check-In Time Window",
                        value=bool(a.get('enable_time_validation', False)),
                        key=f"edit_enable_time_{a['id']}"
                    )
                    
                    edit_s1_start = edit_s1_end = edit_s2_start = edit_s2_end = None
                    
                    if enable_time_val:
                        col_t1, col_t2 = st.columns(2)
                        with col_t1:
                            st.markdown("**Session 1 Times**")
                            s1_start_val = a.get('session_1_start_time', '19:45')
                            s1_end_val = a.get('session_1_end_time', '20:15')
                            try: start_time_val = datetime.strptime(s1_start_val, "%H:%M").time() if s1_start_val else datetime.strptime("19:45", "%H:%M").time()
                            except: start_time_val = datetime.strptime("19:45", "%H:%M").time()
                            try: end_time_val = datetime.strptime(s1_end_val, "%H:%M").time() if s1_end_val else datetime.strptime("20:15", "%H:%M").time()
                            except: end_time_val = datetime.strptime("20:15", "%H:%M").time()
                            edit_s1_start = st.time_input("Check-in Opens", value=start_time_val, key=f"edit_s1_start_{a['id']}")
                            edit_s1_end = st.time_input("Check-in Closes", value=end_time_val, key=f"edit_s1_end_{a['id']}")
                        
                        with col_t2:
                            st.markdown("**Session 2 Times**")
                            s2_start_val = a.get('session_2_start_time', '20:45')
                            s2_end_val = a.get('session_2_end_time', '21:15')
                            try: start_time_val = datetime.strptime(s2_start_val, "%H:%M").time() if s2_start_val else datetime.strptime("20:45", "%H:%M").time()
                            except: start_time_val = datetime.strptime("20:45", "%H:%M").time()
                            try: end_time_val = datetime.strptime(s2_end_val, "%H:%M").time() if s2_end_val else datetime.strptime("21:15", "%H:%M").time()
                            except: end_time_val = datetime.strptime("21:15", "%H:%M").time()
                            edit_s2_start = st.time_input("Check-in Opens", value=start_time_val, key=f"edit_s2_start_{a['id']}")
                            edit_s2_end = st.time_input("Check-in Closes", value=end_time_val, key=f"edit_s2_end_{a['id']}")
                    
                    st.markdown("---")
                    
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
                    st.markdown("**⏰ Time-Gated Check-In (Optional)**")
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
                                "name": act_name.upper(), "session_1_label": s1, "session_2_label": s2, "active": True,
                                "enable_time_validation": enable_time,
                                "session_1_start_time": add_s1_start.strftime("%H:%M") if add_s1_start else None,
                                "session_1_end_time": add_s1_end.strftime("%H:%M") if add_s1_end else None,
                                "session_2_start_time": add_s2_start.strftime("%H:%M") if add_s2_start else None,
                                "session_2_end_time": add_s2_end.strftime("%H:%M") if add_s2_end else None,
                            }).execute()
                            refresh_data()
                            st.rerun()

        # ── TAB 3: Convert Status ─────────────────────────────────
    with tab3:
        st.info("Residents automatically convert from 'New' to 'Regular' after 3 attendances.")
        newbies = [p for p in st.session_state.participants if p.get('is_new') and p.get('active', True)]
        st.write(f"**{len(newbies)} New Residents**")
        
        import time
        for p in newbies:
            # 🔥 SAFE RETRY LOOP: Try 3 times before giving up
            c = 0
            for attempt in range(3):
                try:
                    result = supabase.table('attendance').select('*', count='exact').eq('participant_id', p['id']).execute()
                    c = result.count
                    break  # Success! Exit loop
                except Exception:
                    if attempt < 2:
                        time.sleep(1)  # Wait 1 second and retry
                    else:
                        c = 0  # Fallback to 0 if Supabase is truly unreachable
            
            st.write(f"{p['name']} - {c} attendances")
            if c >= 3:
                if st.button(f"Convert {p['name']}", key=f"conv_{p['id']}"):
                    supabase.table('participants').update({'is_new': False}).eq('id', p['id']).execute()
                    refresh_data()
                    st.rerun()

    # ── TAB 4: Finance & Payment Status ──────────────────────
    with tab4:
        st.subheader("💰 Garden Finance & Payment Management")
        
        # ── A. Dynamic Pricing Settings ──
        with st.expander("⚙️ Garden Pricing & Settings (Admins/Chairmen only)", expanded=False):
            if st.session_state.user_role in ['admin', 'chairman']:
                st.markdown("**1. Global Pricing (Default)**")
                current_price = get_setting('garden_monthly_rent', '15.00')
                new_price = st.number_input("Default Monthly Rent ($)", min_value=0.0, max_value=100.0, value=float(current_price), step=0.50, key="garden_price")
                
                st.divider()
                st.markdown("**2. Per-Plot-Type Pricing**")
                
                # Check if per-plot pricing is enabled
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
                    # Save Global
                    save_setting('garden_monthly_rent', str(new_price))
                    # Save Toggle
                    save_setting('garden_per_plot_pricing_enabled', str(enable_per_plot))
                    # Save Type Prices
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
        occupied_plots = [p for p in plots if p.get('occupied')]
        monthly_rent = float(get_setting('garden_monthly_rent', '15.00'))
        
        if not occupied_plots:
            st.info("No occupied plots to manage.")
        else:
            # ── 1. Build Data ──
            dashboard_data = []
            for plot in occupied_plots:
                owner_id = plot.get('user_id')
                owner_data = find_participant_by_id(owner_id) if owner_id else None
                owner_name = owner_data['name'] if owner_data else "Unknown"
                owner_contact = mask_phone(owner_data.get('contact', 'N/A')) if owner_data else "N/A"
                
                dashboard_data.append({
                    "Plot #": plot['plot_number'],
                    "Plot Type": plot['plot_type'],
                    "Owner Name": owner_name,
                    "Contact": owner_contact,
                    "Paid": plot.get('paid', False),
                    "user_id": owner_id
                })
            
            # ── 2. Metrics ──
            total_occupied = len(dashboard_data)
            total_paid = sum(1 for d in dashboard_data if d['Paid'])
            total_unpaid = total_occupied - total_paid
            
            # 🔥 NEW: Calculate revenue based on whether Per-Plot pricing is enabled
            per_plot_enabled = get_setting('garden_per_plot_pricing_enabled', 'false') == 'true'
            
            if per_plot_enabled:
                # Fetch individual type prices
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
                # Use the global default price
                total_revenue_collected = total_paid * monthly_rent
            
            # Fetch Expenses
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
            
            st.markdown("---")
            c_fin1, c_fin2, c_fin3 = st.columns(3)
            c_fin1.metric("💵 Revenue Collected", f"${total_revenue_collected:.2f}")
            c_fin2.metric("🧾 Total Expenses", f"${total_expenses:.2f}", delta_color="inverse")
            c_fin3.metric("📈 Net Income (Profit)", f"${net_income:.2f}", delta_color="normal")
            
            st.divider()
            
            # ── 3. Search & Filter ──
            col_search, col_filter = st.columns([3, 1])
            with col_search:
                search_query = st.text_input("🔍 Search by Plot Number, Owner Name, or Contact", placeholder="e.g., 5, Edmund, 9821...")
            with col_filter:
                filter_status = st.selectbox("Filter by Status", ["All", "Paid", "Unpaid"], index=0)
            
            # ── 4. Apply Filters ──
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
            
            # ── 5. Render Cards ──
            for plot_info in filtered_data:
                plot_num = plot_info['Plot #']
                owner_name = plot_info['Owner Name']
                contact = plot_info['Contact']
                is_paid = plot_info['Paid']
                plot_type = plot_info['Plot Type']
                
                if is_paid:
                    bg_color = "#e8f5e9"; border_color = "#4caf50"; status_icon = "✅"; status_text = "Paid"; btn_label = "Mark Unpaid"; btn_type = "secondary"
                else:
                    bg_color = "#ffebee"; border_color = "#f44336"; status_icon = "❌"; status_text = "Unpaid"; btn_label = "Mark Paid"; btn_type = "primary"
                
                # 🔥 Calculate specific price for this plot type
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
                        <strong style="font-size: 18px;">Plot {plot_num}</strong> <span style="background: #333; color: white; padding: 2px 10px; border-radius: 12px; font-size: 12px;">Type {plot_type}</span>
                        <br>
                        <span style="font-size: 14px;">👤 {owner_name}</span> <span style="color: #777; font-size: 12px;">| 📞 {contact}</span>
                        <br><span style="font-size: 12px; color: #555;">Rent: ${actual_price:.2f}/month</span>
                    </div>
                    <div style="display: flex; align-items: center; gap: 15px;">
                        <span style="font-weight: bold; font-size: 16px; color: {border_color};">{status_icon} {status_text}</span>
                """, unsafe_allow_html=True)
                
                c1, c2 = st.columns([6, 1])
                with c2:
                    if st.button(btn_label, key=f"pay_dash_{plot_num}", type=btn_type, use_container_width=True):
                        try:
                            new_status = not is_paid
                            supabase.table('garden_plots').update({'paid': new_status, 'updated_at': datetime.now().isoformat()}).eq('plot_number', plot_num).execute()
                            log_action(st.session_state.user_role, "MARK_PAID" if new_status else "MARK_UNPAID", f"Plot {plot_num} - {owner_name}", str(plot_num))
                            st.success(f"Plot {plot_num} status updated!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")
                
                st.markdown("</div>", unsafe_allow_html=True)

    # ── TAB 5: Audit Logs ─────────────────────────────────────
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