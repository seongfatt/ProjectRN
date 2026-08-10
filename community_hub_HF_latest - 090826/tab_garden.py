import streamlit as st
from datetime import datetime
import pandas as pd
from config import supabase, PLOT_TYPES, TOTAL_PLOTS, TYPE_MAP, DB_CONNECTED
from utils import (mask_phone, get_plot, update_plot, get_user_plot, 
                   get_occupied_count, load_plots, log_action, find_participant_by_id)

# ─── GLOBAL HELPERS ──────────────────────────────────────────

def get_setting(key, default=None):
    if not DB_CONNECTED: return default
    try:
        r = supabase.table('system_settings').select('setting_value').eq('setting_key', key).single().execute()
        return r.data['setting_value'] if r.data else default
    except Exception as e:
        print(f"Error getting setting {key}: {e}")
        return default

def load_garden_layout(block_name):
    if not DB_CONNECTED: return []
    try:
        r = supabase.table('garden_layout').select('*').eq('block_name', block_name).order('plot_number').execute()
        return r.data if r.data else []
    except Exception as e:
        print(f"Error loading layout: {e}")
        return []

def save_garden_layout(block_name, plot_num, row, col, plot_type):
    if not DB_CONNECTED: return False
    try:
        supabase.table('garden_layout').upsert({
            'block_name': block_name,
            'plot_number': plot_num,
            'grid_row': row,
            'grid_col': col,
            'plot_type': plot_type
        }, on_conflict='block_name, plot_number').execute()
        return True
    except Exception as e:
        print(f"Error saving layout: {e}")
        return False

def remove_garden_layout(block_name, plot_num):
    if not DB_CONNECTED: return False
    try:
        supabase.table('garden_layout').delete().eq('block_name', block_name).eq('plot_number', plot_num).execute()
        return True
    except Exception as e:
        print(f"Error removing layout: {e}")
        return False

def clear_garden_layout(block_name):
    if not DB_CONNECTED: return False
    try:
        supabase.table('garden_layout').delete().eq('block_name', block_name).execute()
        return True
    except Exception as e:
        print(f"Error clearing layout: {e}")
        return False

def get_plot_type_color(plot_type):
    return PLOT_TYPES[plot_type]["colour"]

def generate_default_layout(block_name):
    rows = []
    for i in range(1, 77):
        rows.append({
            'block_name': block_name,
            'plot_number': i,
            'grid_row': (i - 1) // 10,
            'grid_col': (i - 1) % 10,
            'plot_type': 'B'
        })
    return rows

def rename_garden_block(old_name, new_name):
    if not DB_CONNECTED: return False
    try:
        supabase.table('garden_layout').update({'block_name': new_name}).eq('block_name', old_name).execute()
        return True
    except Exception as e:
        print(f"Error renaming block: {e}")
        return False

def delete_garden_block(block_name):
    if not DB_CONNECTED: return False
    try:
        supabase.table('garden_layout').delete().eq('block_name', block_name).execute()
        return True
    except Exception as e:
        print(f"Error deleting block: {e}")
        return False

# ─── MAIN FUNCTION ───────────────────────────────────────────
def show_garden():
    st.header("🌱 Roof Top Garden")

    if not DB_CONNECTED:
        st.error("Database not connected"); return

    # ── 1. Block Selector ──────────────────────────────────────
    try:
        blocks_data = supabase.table('garden_layout').select('block_name').execute().data
        existing_blocks = sorted(list(set(b['block_name'] for b in blocks_data)))
    except:
        existing_blocks = ['Block 622']
    
    if not existing_blocks:
        existing_blocks = ['Block 622']
        
    selected_block = st.selectbox("📍 Select Garden Block", existing_blocks, index=0, key="garden_block_selector")

    # ── 2. Load Data (STRICT BLOCK ISOLATION) ─────────────────
    plots = load_plots()
    
    current_block_layout = load_garden_layout(selected_block)
    
    if not current_block_layout:
        st.info(f"ℹ️ {selected_block} has no plots yet. Use the Admin Editor below to design the map.")
        st.subheader("0 / 0 occupied (0.0%)")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("💲 Paid", 0)
        c2.metric("🤝 Unpaid (Pending)", 0)
        c3.metric("🌱 Community Stewarded", 0)
        c4.metric("🟩 Available", 0)
        
        total_occupied_all_blocks = len([p for p in plots if p.get('occupied')])
        st.caption(f"📊 **System Wide:** {total_occupied_all_blocks} plots occupied across all blocks.")
        st.markdown("---")
        st.markdown("### Garden Grid Overview")
        st.info("No plots to display for this block.")
        st.divider()
        
    else:
        current_block_plot_nums = [item['plot_number'] for item in current_block_layout]
        total_plots_in_block = len(current_block_plot_nums)
        
        occupied = 0
        paid_count = 0
        unpaid_count = 0
        community_count = 0
        
        for p in plots:
            # 🔥 CRITICAL FIX: Only count plots that exist in the current block's layout
            if p['plot_number'] not in current_block_plot_nums:
                continue
            
            if p.get('occupied'):
                occupied += 1
                if p.get('paid'):
                    paid_count += 1
                else:
                    unpaid_count += 1
            else:
                community_count += 1
                
        pct = occupied / total_plots_in_block if total_plots_in_block > 0 else 0
        
        st.progress(pct)
        st.subheader(f"{occupied} / {total_plots_in_block} occupied ({pct:.1%})")
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("💲 Paid", paid_count)
        c2.metric("🤝 Unpaid (Pending)", unpaid_count)
        c3.metric("🌱 Community Stewarded", community_count)
        c4.metric("🟩 Available", total_plots_in_block - occupied)

        total_occupied_all_blocks = len([p for p in plots if p.get('occupied')])
        st.caption(f"📊 **System Wide:** {total_occupied_all_blocks} plots occupied across all blocks.")
        st.markdown("---")

        # ── Professional Legend ──
        st.markdown("### Legend")
        l1, l2, l3, l4 = st.columns(4)
        with l1:
            st.markdown("💲 **Paid** – Solid color")
        with l2:
            st.markdown("🤝 **Pending/Unpaid** – Solid color (Awaiting payment)")
        with l3:
            st.markdown("🌱 **Community Stewarded** – Dashed border")
        with l4:
            st.markdown("⬛ **Empty Plot** – Unplanted")
        st.markdown("---")

        # ── 3. Visual Grid Display ─────────────────────────────────
        st.markdown("### Garden Grid Overview")

        layout_data = load_garden_layout(selected_block)
        plots_dict = {p['plot_number']: p for p in plots}
        price = float(get_setting('garden_monthly_rent', '15.00'))
        
        if layout_data:
            sections = {}
            for item in layout_data:
                if item['plot_number'] <= 9: sec = "Section 1"
                elif item['plot_number'] <= 20: sec = "Section 2"
                elif item['plot_number'] <= 29: sec = "Section 3"
                elif item['plot_number'] <= 38: sec = "Section 4"
                elif item['plot_number'] <= 47: sec = "Section 5"
                elif item['plot_number'] <= 58: sec = "Section 6"
                elif item['plot_number'] <= 67: sec = "Section 7"
                else: sec = "Section 8"
                
                if sec not in sections:
                    sections[sec] = []
                sections[sec].append(item)

            for sec_name, sec_items in sections.items():
                st.subheader(sec_name)
                
                max_row = max([i['grid_row'] for i in sec_items]) + 1
                max_col = max([i['grid_col'] for i in sec_items]) + 1
                
                grid = [[None for _ in range(max_col)] for _ in range(max_row)]
                for item in sec_items:
                    grid[item['grid_row']][item['grid_col']] = item['plot_number']

                for row in grid:
                    cols_ui = st.columns(len(row))
                    for col_idx, plot_num in enumerate(row):
                        with cols_ui[col_idx]:
                            if plot_num is None:
                                st.empty()
                                continue
                            
                            is_in_current_block = any(item['plot_number'] == plot_num for item in layout_data)
                            if not is_in_current_block:
                                st.empty()
                                continue
                            
                            layout_item = next((item for item in layout_data if item['plot_number'] == plot_num), None)
                            plot_type = layout_item['plot_type'] if layout_item and 'plot_type' in layout_item else 'B'
                            
                            pd_item = plots_dict.get(plot_num, {'occupied': False, 'user_id': None})
                            occ = pd_item.get('occupied', False)
                            is_paid = pd_item.get('paid', False)
                            color = get_plot_type_color(plot_type)
                            
                            if occ and is_paid:
                                border_style = "border: 2px solid #ffffff; box-shadow: 0 2px 5px rgba(255,255,255,0.2);"
                                opacity_style = "opacity: 1.0;"
                                icon_html = '<div style="position:absolute; top:4px; right:6px; font-size:14px; font-weight:bold; color:#ffffff; text-shadow: 0 0 4px rgba(0,0,0,0.8), 0 0 8px rgba(0,0,0,0.6), 0 0 12px rgba(0,0,0,0.4);">💲</div>'
                                renewal_date_str = pd_item.get('renewal_due_date')
                                if renewal_date_str:
                                    try:
                                        renewal_date = datetime.strptime(str(renewal_date_str)[:10], "%Y-%m-%d").date()
                                        days_left = (renewal_date - datetime.now().date()).days
                                        if 0 <= days_left <= 30:
                                            border_style = "border: 3px solid #ff4444; box-shadow: 0 0 10px #ff4444;"
                                    except:
                                        pass
                            
                            elif occ and not is_paid:
                                border_style = "border: 2px solid #ffffff; box-shadow: 0 2px 5px rgba(255,255,255,0.2);"
                                opacity_style = "opacity: 1.0;"
                                icon_html = '<div style="position:absolute; top:4px; right:6px; font-size:12px;">🤝</div>'
                            
                            elif not occ:
                                border_style = "border: 2px dashed #00ffff; box-shadow: 0 0 8px #00ffff;"
                                opacity_style = "opacity: 0.8;"
                                icon_html = '<div style="position:absolute; top:4px; right:6px; font-size:12px;">🌱</div>'
                            
                            area = PLOT_TYPES[plot_type]["area"]
                            box_count = PLOT_TYPES[plot_type].get("boxes", 0)
                            
                            st.markdown(
                                f'<div style="position:relative; background:{color}; {opacity_style} {border_style} border-radius:8px; width:100px; height:85px; margin:0 auto; display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; color:white; font-weight:bold; font-size:16px; box-sizing:border-box;">'
                                f'{icon_html}'
                                f'{plot_num}'
                                f'<div style="font-size:10px;color:#fff;margin-top:2px;">${price:.0f}/mo</div>'
                                f'<div style="font-size:8px;color:#ddd;margin-top:1px;">{box_count} boxes</div>'
                                f'</div>',
                                unsafe_allow_html=True
                            )

    st.divider()

    # ── 4. Admin Operation Panel ──────────────────────────────
    if st.session_state.user_role == 'admin':
        st.subheader("🛠️ Admin Operation Panel")
        
        if 'admin_garden_tab' not in st.session_state:
            st.session_state.admin_garden_tab = "🗺️ Edit Garden Map"
            
        tab_assign, tab_list, tab_layout = st.tabs(["➕ Smart Assignment", "📋 Manage Existing", "🗺️ Edit Garden Map"])
        
        with tab_assign:
            st.session_state.admin_garden_tab = "➕ Smart Assignment"
            st.markdown("#### Quick Assign or Swap a Plot")
            st.caption("Search for a participant, pick a plot, and assign it.")

            search_query = st.text_input("🔍 Search Resident (Type Name, Phone, or ID)", placeholder="e.g., 91234567 or AHMAD", key="admin_search")
            
            selected_participant = None
            current_plot_num = None

            if search_query:
                s = search_query.strip().lower()
                participants = st.session_state.participants
                
                from utils import clean_phone_number, find_participant_by_phone
                clean_phone = clean_phone_number(search_query)
                if len(clean_phone) >= 8:
                    selected_participant = find_participant_by_phone(clean_phone)
                
                if not selected_participant:
                    matches = [p for p in participants if p.get('active', True) and (s in p.get('name', '').lower() or s in p.get('id', '').lower())]
                    if matches:
                        match_dict = {f"{p['name']} (ID: {p['id'][:8]}...)": p for p in matches}
                        selected_label = st.selectbox("Select Resident", list(match_dict.keys()), key="admin_match_select")
                        if selected_label:
                            selected_participant = match_dict[selected_label]

            if selected_participant:
                st.success(f"✅ Selected: **{selected_participant['name']}**")
                
                existing_plot = get_user_plot(selected_participant['id'])
                if existing_plot:
                    current_plot_num = existing_plot['plot_number']
                    st.warning(f"⚠️ {selected_participant['name']} currently owns **Plot {current_plot_num}**. You can swap them to a new plot below.")
                
                # 🔥 CRITICAL FIX: Only show plots that belong to the current block
                available_plots = []
                if current_block_layout:
                    for layout_item in current_block_layout:
                        plot_num = layout_item['plot_number']
                        plot_data = plots_dict.get(plot_num, {})
                        if not plot_data.get('occupied'):
                            available_plots.append(plot_data)
                
                if current_plot_num:
                    available_plots = [p for p in available_plots if p.get('plot_number') != current_plot_num]
                
                if not available_plots:
                    st.error("❌ No available plots to assign in this block.")
                else:
                    plot_options = {f"Plot {p['plot_number']} (Type {p['plot_type']})": p['plot_number'] for p in available_plots}
                    selected_plot_label = st.selectbox("Select Target Plot", list(plot_options.keys()), key="admin_plot_select")
                    selected_plot_num = plot_options[selected_plot_label]

                    renewal_date = st.date_input("📅 Renewal Due Date (Optional)", value=None, key="admin_assign_renewal")
                    button_label = "🔄 Swap to New Plot" if current_plot_num else "✅ Assign New Plot"
                    
                    if st.button(button_label, type="primary", use_container_width=True):
                        try:
                            updates = {
                                'user_id': selected_participant['id'], 
                                'change_log': f"Admin assigned to {selected_participant['id']}",
                                'block_name': selected_block  # 🔥 CRITICAL: Save the block name!
                            }
                            if renewal_date:
                                updates['renewal_due_date'] = str(renewal_date)
                                updates['renewal_status'] = 'active'
                            
                            if current_plot_num:
                                update_plot(current_plot_num, {
                                    'occupied': False, 
                                    'user_id': None, 
                                    'renewal_due_date': None, 
                                    'renewal_status': None,
                                    'change_log': f"Auto-released due to swap to {selected_plot_num}"
                                })

                            updates['occupied'] = True
                            if update_plot(selected_plot_num, updates):
                                if 'Gardener' not in selected_participant.get('member_type', ''):
                                    new_type = (selected_participant.get('member_type', 'Resident') + ', Gardener').strip(', ')
                                    supabase.table('participants').update({'member_type': new_type}).eq('id', selected_participant['id']).execute()

                                log_action('admin', 'ASSIGN_PLOT', f"Plot {selected_plot_num} - {selected_participant['name']}", str(selected_plot_num))
                                st.success(f"✅ Successfully assigned to {selected_participant['name']}!")
                                st.rerun()
                        except Exception as e:
                            st.error(f"Error during assignment: {e}")
            else:
                st.info("🔍 Start typing above to search for a resident.")

        with tab_list:
            st.session_state.admin_garden_tab = "📋 Manage Existing"
            st.markdown("#### Manage All Plots")
            st.caption("Search by plot number to edit size, payment, or renewal for ANY plot in this block.")
            
            plot_edit_num = st.number_input("🔍 Enter Plot Number to Edit", min_value=1, max_value=76, value=1, step=1, key="plot_edit_search")
            
            found_plot = next((p for p in plots if p['plot_number'] == plot_edit_num and p['plot_number'] in current_block_plot_nums), None)
            found_layout = next((l for l in layout_data if l['plot_number'] == plot_edit_num), None)
            
            if not found_layout:
                st.warning(f"⚠️ Plot {plot_edit_num} does not exist in the layout for {selected_block}. Please add it first in 'Edit Garden Map'.")
            else:
                is_occupied = found_plot.get('occupied', False) if found_plot else False
                owner_id = found_plot.get('user_id') if found_plot else None
                owner_data = find_participant_by_id(owner_id) if owner_id else None
                owner_name = owner_data['name'] if owner_data else "Unoccupied"
                is_paid = found_plot.get('paid', False) if found_plot else False
                
                current_plot_type = found_layout.get('plot_type', 'B')
                plot_color = get_plot_type_color(current_plot_type)
                
                st.markdown(f"""
                <div style="border-left: 6px solid {plot_color}; padding: 15px; border-radius: 8px; margin: 10px 0; background: #1e1e1e;">
                    <h4 style="margin:0;">Plot {plot_edit_num} (Type {current_plot_type})</h4>
                    <div style="font-size:14px; color:#aaa;">Owner: {owner_name}</div>
                    <div style="font-size:14px; color:#aaa;">Status: {'✅ Occupied' if is_occupied else '🟩 Available (Community Stewarded)'}</div>
                </div>
                """, unsafe_allow_html=True)
                
                c1, c2 = st.columns(2)
                
                with c1:
                    st.markdown("**📐 Manage Plot Size**")
                    st.caption(f"Current: Type {current_plot_type} ({PLOT_TYPES[current_plot_type]['area']} m²)")
                    
                    new_plot_type = st.selectbox(
                        "Select New Size", 
                        ["A", "B", "C", "D"], 
                        index=["A", "B", "C", "D"].index(current_plot_type) if current_plot_type in ["A", "B", "C", "D"] else 1,
                        key=f"size_change_{plot_edit_num}"
                    )
                    
                    if st.button(f"💾 Update Plot Size", key=f"save_size_{plot_edit_num}", use_container_width=True):
                        if new_plot_type != current_plot_type:
                            try:
                                # Update garden_layout
                                supabase.table('garden_layout').update({
                                    'plot_type': new_plot_type
                                }).eq('block_name', selected_block).eq('plot_number', plot_edit_num).execute()
                                
                                # Update garden_plots if it exists
                                if found_plot:
                                    supabase.table('garden_plots').update({
                                        'plot_type': new_plot_type
                                    }).eq('plot_number', plot_edit_num).execute()
                                
                                log_action(st.session_state.user_role, "CHANGE_PLOT_SIZE", f"Plot {plot_edit_num} changed from {current_plot_type} to {new_plot_type}", str(plot_edit_num))
                                st.success(f"✅ Plot {plot_edit_num} size updated to Type {new_plot_type}!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error updating size: {e}")
                        else:
                            st.info("No change detected.")
                
                with c2:
                    if is_occupied:
                        st.markdown("**💰 Payment & Ownership**")
                        st.write(f"**Paid Status:** {'✅ Paid' if is_paid else '❌ Unpaid'}")
                        if st.button(f"Toggle Payment Status", key=f"pay_btn_{plot_edit_num}", use_container_width=True):
                            try:
                                new_status = not is_paid
                                supabase.table('garden_plots').update({'paid': new_status, 'updated_at': datetime.now().isoformat()}).eq('plot_number', plot_edit_num).execute()
                                log_action(st.session_state.user_role, "MARK_PAID" if new_status else "MARK_UNPAID", f"Plot {plot_edit_num} - {owner_name}", str(plot_edit_num))
                                st.success(f"Plot {plot_edit_num} payment status updated!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")
                        
                        if owner_data:
                            new_name = st.text_input("Rename Resident", value=owner_data['name'], key=f"rename_{plot_edit_num}")
                            if st.button("💾 Update Name", key=f"save_name_{plot_edit_num}", use_container_width=True):
                                if new_name.strip() and new_name != owner_data['name']:
                                    supabase.table('participants').update({'name': new_name.strip().upper()}).eq('id', owner_id).execute()
                                    st.success("Name updated in master database!")
                                    st.rerun()
                    
                    st.markdown("**📅 Renewal Date**")
                    current_renewal = found_plot.get('renewal_due_date') if found_plot else None
                    try:
                        default_date = datetime.strptime(str(current_renewal)[:10], "%Y-%m-%d").date() if current_renewal else None
                    except:
                        default_date = None
                    
                    new_renewal = st.date_input("Renewal Date", value=default_date, key=f"renew_{plot_edit_num}")
                    if st.button("💾 Update Renewal", key=f"save_renew_{plot_edit_num}", use_container_width=True):
                        if found_plot:
                            update_plot(plot_edit_num, {'renewal_due_date': str(new_renewal), 'renewal_status': 'active'})
                            st.success("Renewal date updated!")
                            st.rerun()
                        else:
                            st.warning("Renewal dates are only applicable for occupied plots.")
                    
                    if is_occupied:
                        st.divider()
                        if st.button("❌ Force Release Plot", type="secondary", key=f"release_{plot_edit_num}", use_container_width=True):
                            other_plots = [p for p in plots if p.get('user_id') == owner_id and p.get('plot_number') != plot_edit_num]
                            if owner_data and not other_plots:
                                updated_types = [t.strip() for t in owner_data.get('member_type', '').split(',') if t.strip() != 'Gardener']
                                new_type = ', '.join(updated_types) if updated_types else 'Resident'
                                supabase.table('participants').update({'member_type': new_type}).eq('id', owner_id).execute()
    
                            if update_plot(plot_edit_num, {'occupied': False, 'user_id': None, 'renewal_due_date': None, 'renewal_status': None, 'change_log': f"Force released by admin"}):
                                log_action('admin', 'RELEASE_PLOT', f"Plot {plot_edit_num} force released", str(plot_edit_num))
                                st.success(f"Plot {plot_edit_num} released!")
                                st.rerun()

        with tab_layout:
            st.session_state.admin_garden_tab = "🗺️ Edit Garden Map"
            st.markdown("#### Design Your Garden Map")
            st.caption("💡 Create, rename, or delete blocks. Bulk generate layouts, or manually design with custom rows/cols.")
            
            col_left, col_right = st.columns([1, 2])
            
            with col_left:
                # CREATE NEW BLOCK
                with st.expander("➕ Create New Block", expanded=False):
                    new_block_name = st.text_input("New Block Name", placeholder="e.g., Block 624, WCC RTG", key="new_block_input_garden")
                    if st.button("Create New Block", type="secondary", use_container_width=True):
                        if new_block_name.strip():
                            existing = load_garden_layout(new_block_name.strip())
                            if existing:
                                st.error(f"Layout for {new_block_name.strip()} already exists.")
                            else:
                                default_data = generate_default_layout(new_block_name.strip())
                                for item in default_data:
                                    save_garden_layout(item['block_name'], item['plot_number'], item['grid_row'], item['grid_col'], item['plot_type'])
                                st.success(f"✅ Created layout for {new_block_name.strip()}!")
                                st.info(f"👉 Select '{new_block_name.strip()}' from the dropdown at the top to edit it.")
                        else:
                            st.error("Please enter a name.")

                # RENAME BLOCK
                with st.expander("✏️ Rename Current Block", expanded=False):
                    st.caption(f"Rename '{selected_block}' to a new name.")
                    new_block_name_rename = st.text_input("New Name", placeholder="e.g., Woodlands CC RTG", key="rename_block_input")
                    if st.button("Rename Block", type="secondary", use_container_width=True):
                        if new_block_name_rename.strip() and new_block_name_rename.strip() != selected_block:
                            existing = load_garden_layout(new_block_name_rename.strip())
                            if existing:
                                st.error(f"A block named '{new_block_name_rename.strip()}' already exists.")
                            else:
                                if rename_garden_block(selected_block, new_block_name_rename.strip()):
                                    st.success(f"✅ Renamed '{selected_block}' to '{new_block_name_rename.strip()}'!")
                                    st.rerun()
                                else:
                                    st.error("Error renaming block.")
                        else:
                            st.error("Please enter a valid new name.")

                # DELETE BLOCK
                with st.expander("🗑️ Delete Current Block", expanded=False):
                    st.warning(f"⚠️ This will permanently delete '{selected_block}' and all its plot data from the database. This action cannot be undone.")
                    confirm_delete = st.checkbox("I understand this action is permanent.", key="confirm_delete_block")
                    if confirm_delete:
                        if st.button(f"🚨 Permanently Delete '{selected_block}'", type="primary", use_container_width=True):
                            if delete_garden_block(selected_block):
                                st.success(f"✅ Block '{selected_block}' deleted successfully!")
                                st.rerun()
                            else:
                                st.error("Error deleting block.")
                
                st.markdown("**⚙️ Editor Settings**")
                
                if layout_data:
                    section_options = []
                    if any(p <= 9 for p in [i['plot_number'] for i in layout_data]): section_options.append("Section 1")
                    if any(10 <= p <= 20 for p in [i['plot_number'] for i in layout_data]): section_options.append("Section 2")
                    if any(21 <= p <= 29 for p in [i['plot_number'] for i in layout_data]): section_options.append("Section 3")
                    if any(30 <= p <= 38 for p in [i['plot_number'] for i in layout_data]): section_options.append("Section 4")
                    if any(39 <= p <= 47 for p in [i['plot_number'] for i in layout_data]): section_options.append("Section 5")
                    if any(48 <= p <= 58 for p in [i['plot_number'] for i in layout_data]): section_options.append("Section 6")
                    if any(59 <= p <= 67 for p in [i['plot_number'] for i in layout_data]): section_options.append("Section 7")
                    if any(p >= 68 for p in [i['plot_number'] for i in layout_data]): section_options.append("Section 8")
                    
                    selected_section = st.selectbox("Select Section to Edit", section_options, index=0, key="edit_section_dropdown")
                else:
                    selected_section = "Section 1"
                    st.info("No layout data. Create plots manually below.")
                
                st.divider()
                
                # BULK AUTO-GENERATE
                with st.expander("⚡ Bulk Auto-Generate Layout", expanded=False):
                    st.caption("Automatically fill the grid with 76 plots in a straight 10-column layout.")
                    current_layout = load_garden_layout(selected_block)
                    if current_layout:
                        st.warning(f"⚠️ {selected_block} already has {len(current_layout)} plots defined. Bulk generating will OVERWRITE the current layout.")
                    
                    if st.button("Generate 76 Plots", type="primary", use_container_width=True):
                        clear_garden_layout(selected_block)
                        default_data = generate_default_layout(selected_block)
                        for item in default_data:
                            save_garden_layout(item['block_name'], item['plot_number'], item['grid_row'], item['grid_col'], item['plot_type'])
                        st.success(f"✅ Generated 76 plots for {selected_block}!")
                        st.rerun()

                st.divider()
                
                st.markdown("**🔢 Grid Canvas Size**")
                st.caption("Set your custom matrix size to match your physical floor plan (e.g., 5 Rows x 10 Cols).")
                
                editor_rows = st.number_input("Editor Rows", min_value=1, max_value=20, value=5, step=1, key="editor_rows")
                editor_cols = st.number_input("Editor Columns", min_value=1, max_value=20, value=10, step=1, key="editor_cols")

                st.divider()
                
                # 🔥 DROPDOWN: Shows ALL plots 1-76
                all_plot_options = {}
                for p_num in range(1, 77):
                    is_in_block = p_num in current_block_plot_nums
                    plot_data = plots_dict.get(p_num, {})
                    is_occ = plot_data.get('occupied', False)
                    
                    if is_in_block:
                        label = str(p_num)
                        if is_occ:
                            label += " (Occupied)"
                    else:
                        label = f"{p_num} (Unassigned)"
                    
                    all_plot_options[label] = p_num
                
                all_labels = list(all_plot_options.keys())
                
                # 🔥 SMART FALLBACK: If the saved label no longer exists, find the next best one
                if 'selected_plot_label' not in st.session_state:
                    st.session_state.selected_plot_label = all_labels[0] if all_labels else ""
                
                if st.session_state.selected_plot_label not in all_labels:
                    # Find the first unassigned plot
                    unassigned_labels = [l for l in all_labels if "(Unassigned)" in l]
                    if unassigned_labels:
                        st.session_state.selected_plot_label = unassigned_labels[0]
                    elif all_labels:
                        st.session_state.selected_plot_label = all_labels[-1]  # Fallback to the last plot
                
                st.caption(f"Total plots: {len(all_plot_options)}")
                
                selected_plot_label = st.selectbox(
                    "Select a plot (Occupied plots will auto-swap)",
                    all_labels,
                    index=all_labels.index(st.session_state.selected_plot_label),
                    key="new_plot_dropdown"
                )
                
                st.session_state.selected_plot_label = selected_plot_label
                selected_new_plot = all_plot_options[selected_plot_label]
                
                # 🔥 Size Selector now lives under the plot dropdown
                existing_layout_item = next((item for item in layout_data if item['plot_number'] == selected_new_plot), None)
                default_type = existing_layout_item['plot_type'] if existing_layout_item else 'B'
                
                st.markdown("**📏 Plot Size**")
                selected_size = st.radio(
                    "Select Size (Keeps original if unchanged)",
                    ["A", "B", "C", "D"],
                    index=["A", "B", "C", "D"].index(default_type),
                    horizontal=True,
                    key="global_size_selector"
                )

                st.divider()
                if st.button("🗑️ Clear All Plots", type="secondary", use_container_width=True):
                    if clear_garden_layout(selected_block):
                        st.success("Map cleared!")
                        st.rerun()

            with col_right:
                st.markdown(f"### 🎯 Interactive Grid ({editor_rows} x {editor_cols})")
                st.caption("👆 Tap an empty box to assign. Tap a colored box to remove.")
                
                # 🔥 CSS FIX: Ensure plot numbers stay on one line
                st.markdown("""
                <style>
                    div[data-testid="stButton"] button {
                        white-space: nowrap !important;
                        font-size: 16px !important;
                        padding: 0px !important;
                        min-height: 48px !important;
                    }
                </style>
                """, unsafe_allow_html=True)
                
                # 🔥 SPEED OPTIMIZATION: Use a container for faster partial updates
                grid_container = st.container()
                
                with grid_container:
                    section_data = []
                    if layout_data:
                        for item in layout_data:
                            p = item['plot_number']
                            if selected_section == "Section 1" and p <= 9: section_data.append(item)
                            elif selected_section == "Section 2" and 10 <= p <= 20: section_data.append(item)
                            elif selected_section == "Section 3" and 21 <= p <= 29: section_data.append(item)
                            elif selected_section == "Section 4" and 30 <= p <= 38: section_data.append(item)
                            elif selected_section == "Section 5" and 39 <= p <= 47: section_data.append(item)
                            elif selected_section == "Section 6" and 48 <= p <= 58: section_data.append(item)
                            elif selected_section == "Section 7" and 59 <= p <= 67: section_data.append(item)
                            elif selected_section == "Section 8" and p >= 68: section_data.append(item)

                    editor_grid = [[None for _ in range(editor_cols)] for _ in range(editor_rows)]
                    for item in section_data:
                        r = item['grid_row']
                        c = item['grid_col']
                        if r < editor_rows and c < editor_cols:
                            editor_grid[r][c] = item['plot_number']

                    for r in range(editor_rows):
                        cols_ui = st.columns(editor_cols)
                        for c in range(editor_cols):
                            with cols_ui[c]:
                                plot_num = editor_grid[r][c]
                                
                                if plot_num is None:
                                    # 🔥 Add action
                                    if st.button("+", key=f"add_{r}_{c}_{selected_block}", use_container_width=True):
                                        # Check if plot exists elsewhere
                                        existing_spot = next((item for item in layout_data if item['plot_number'] == selected_new_plot), None)
                                        if existing_spot:
                                            remove_garden_layout(selected_block, selected_new_plot)
                                        
                                        # Save using the global size selection
                                        if save_garden_layout(selected_block, selected_new_plot, r, c, selected_size):
                                            st.rerun()
                                else:
                                    layout_item = next((item for item in layout_data if item['plot_number'] == plot_num), None)
                                    plot_type = layout_item['plot_type'] if layout_item and 'plot_type' in layout_item else 'B'
                                    color = get_plot_type_color(plot_type)
                                    
                                    if st.button(
                                        label=f"{plot_num}", 
                                        key=f"remove_{plot_num}_{selected_block}", 
                                        use_container_width=True,
                                        type="primary"
                                    ):
                                        if remove_garden_layout(selected_block, plot_num):
                                            st.rerun()
                                    st.markdown(
                                        f'<style> div[data-testid="stButton"] button[key="remove_{plot_num}_{selected_block}"] {{ background-color: {color} !important; color: white !important; border: none; font-weight: bold; font-size: 16px; }}</style>',
                                        unsafe_allow_html=True
                                    )
    else:
        st.caption("🔒 Interactive Map Editor is restricted to System Admins.")

    # ── 5. STATISTICS ──────────────────────────────────────────
    st.markdown("---")
    st.markdown("## Statistics")
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Plots", total_plots_in_block if 'total_plots_in_block' in locals() else 0)
    c2.metric("💲 Paid", paid_count if 'paid_count' in locals() else 0)
    c3.metric("🤝 Unpaid (Pending)", unpaid_count if 'unpaid_count' in locals() else 0)
    c4.metric("🌱 Community Stewarded", community_count if 'community_count' in locals() else 0)

    st.markdown("### By Type")
    tc = st.columns(4)
    for i, (tk, ti) in enumerate(PLOT_TYPES.items()):
        with tc[i]:
            to = len([p for p in plots if p['plot_type'] == tk and p['occupied']])
            pc = (to / ti["total"]) * 100 if ti["total"] > 0 else 0
            box_count = ti.get("boxes", 0)
            st.markdown(
                f'<div style="background:{ti["colour"]};color:white;padding:10px;border-radius:8px;text-align:center;">'
                f'<div style="font-size:14px;font-weight:bold;">Type {tk}</div>'
                f'<div style="font-size:20px;margin:3px 0;">{to}/{ti["total"]}</div>'
                f'<div>{ti["area"]} m² ({box_count} boxes)</div>'
                f'<div>({pc:.1f}%)</div></div>',
                unsafe_allow_html=True
            )