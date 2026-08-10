import streamlit as st
from datetime import datetime
import pandas as pd
from config import supabase, PLOT_TYPES, TOTAL_PLOTS, TYPE_MAP, DB_CONNECTED
from utils import (mask_phone, get_plot, update_plot, get_user_plot,
                   get_occupied_count, load_plots, log_action, find_participant_by_id,
                   clean_phone_number, find_participant_by_phone)

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
            'block_name': block_name, 'plot_number': plot_num,
            'grid_row': row, 'grid_col': col, 'plot_type': plot_type
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
    return PLOT_TYPES.get(plot_type, PLOT_TYPES["B"])["colour"]

def generate_default_layout(block_name, total_plots=76):
    """Generates a default layout. Now supports dynamic plot counts."""
    rows = []
    for i in range(1, total_plots + 1):
        rows.append({'block_name': block_name, 'plot_number': i,
                     'grid_row': (i - 1) // 10, 'grid_col': (i - 1) % 10, 'plot_type': 'B'})
    return rows

def seed_block_plots(block_name, layout_items):
    """🔥 Create empty garden_plots rows for layout plots that don't exist yet."""
    if not DB_CONNECTED: return 0
    try:
        existing = supabase.table('garden_plots').select('plot_number').eq('block_name', block_name).execute().data or []
        have = {e['plot_number'] for e in existing}
        rows = [{'block_name': block_name, 'plot_number': it['plot_number'],
                 'plot_type': it.get('plot_type', 'B'), 'occupied': False, 'paid': False}
                for it in layout_items if it['plot_number'] not in have]
        if rows:
            supabase.table('garden_plots').insert(rows).execute()
        return len(rows)
    except Exception as e:
        print(f"Seed error: {e}")
        return 0

def rename_garden_block(old_name, new_name):
    """🔥 Renames BOTH layout and plots so they never desync."""
    if not DB_CONNECTED: return False
    try:
        supabase.table('garden_layout').update({'block_name': new_name}).eq('block_name', old_name).execute()
        supabase.table('garden_plots').update({'block_name': new_name}).eq('block_name', old_name).execute()
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

    # ── 2. Load Data (🔥 TRUE BLOCK ISOLATION) ─────────────────
    plots = load_plots()
    block_plots = [p for p in plots if (p.get('block_name') or '').strip() == selected_block]
    plots_dict = {p['plot_number']: p for p in block_plots}
    current_block_layout = load_garden_layout(selected_block)
    layout_data = current_block_layout

    if not current_block_layout:
        st.info(f"ℹ️ {selected_block} has no plots yet. Use the Admin Editor below to design the map.")
        st.subheader("0 / 0 occupied (0.0%)")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("💲 Paid", 0); c2.metric("🤝 Unpaid (Pending)", 0)
        c3.metric("🌱 Community Stewarded", 0); c4.metric("🟩 Available", 0)
        total_occupied_all_blocks = len([p for p in plots if p.get('occupied')])
        st.caption(f"📊 **System Wide:** {total_occupied_all_blocks} plots occupied across all blocks.")
        st.markdown("---")
        st.markdown("### Garden Grid Overview")
        st.info("No plots to display for this block.")
        st.divider()
    else:
        current_block_plot_nums = [item['plot_number'] for item in current_block_layout]
        total_plots_in_block = len(current_block_plot_nums)
        occupied = 0; paid_count = 0; unpaid_count = 0; community_count = 0
        for p in block_plots:
            if p['plot_number'] not in current_block_plot_nums:
                continue
            if p.get('occupied'):
                occupied += 1
                if p.get('paid'): paid_count += 1
                else: unpaid_count += 1
            else:
                community_count += 1
        pct = occupied / total_plots_in_block if total_plots_in_block > 0 else 0
        st.progress(pct)
        st.subheader(f"{occupied} / {total_plots_in_block} occupied ({pct:.1%})")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("💲 Paid", paid_count); c2.metric("🤝 Unpaid (Pending)", unpaid_count)
        c3.metric("🌱 Community Stewarded", community_count)
        c4.metric("🟩 Available", total_plots_in_block - occupied)
        total_occupied_all_blocks = len([p for p in plots if p.get('occupied')])
        st.caption(f"📊 **System Wide:** {total_occupied_all_blocks} plots occupied across all blocks.")
        st.markdown("---")
        st.markdown("### Legend")
        l1, l2, l3, l4 = st.columns(4)
        with l1: st.markdown("💲 **Paid** – Solid color")
        with l2: st.markdown("🤝 **Pending/Unpaid** – Solid color (Awaiting payment)")
        with l3: st.markdown("🌱 **Community Stewarded** – Dashed border")
        with l4: st.markdown("⬛ **Empty Plot** – Unplanted")
        st.markdown("---")
        
        # ── 3. Visual Grid Display (block-scoped) ─────────────
        st.markdown("### Garden Grid Overview")
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
                sections.setdefault(sec, []).append(item)
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
                                st.empty(); continue
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
                                    except: pass
                            elif occ and not is_paid:
                                border_style = "border: 2px solid #ffffff; box-shadow: 0 2px 5px rgba(255,255,255,0.2);"
                                opacity_style = "opacity: 1.0;"
                                icon_html = '<div style="position:absolute; top:4px; right:6px; font-size:12px;">🤝</div>'
                            elif not occ:
                                border_style = "border: 2px dashed #00ffff; box-shadow: 0 0 8px #00ffff;"
                                opacity_style = "opacity: 0.8;"
                                icon_html = '<div style="position:absolute; top:4px; right:6px; font-size:12px;">🌱</div>'
                            box_count = PLOT_TYPES.get(plot_type, PLOT_TYPES["B"]).get("boxes", 0)
                            st.markdown(
                                f'<div style="position:relative; background:{color}; {opacity_style} {border_style} border-radius:8px; width:100px; height:85px; margin:0 auto; display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; color:white; font-weight:bold; font-size:16px; box-sizing:border-box;">'
                                f'{icon_html}{plot_num}'
                                f'<div style="font-size:10px;color:#fff;margin-top:2px;">${price:.0f}/mo</div>'
                                f'<div style="font-size:8px;color:#ddd;margin-top:1px;">{box_count} boxes</div></div>',
                                unsafe_allow_html=True)
    st.divider()

    # ── 4. Admin Operation Panel ──────────────────────────────
    if st.session_state.get('user_role') == 'admin':
        st.subheader("🛠️ Admin Operation Panel")
        if 'admin_garden_tab' not in st.session_state:
            st.session_state.admin_garden_tab = "🗺️ Edit Garden Map"
        tab_assign, tab_list, tab_layout = st.tabs(["➕ Smart Assignment", "📋 Manage Existing", "🗺️ Edit Garden Map"])
        
        with tab_assign:
            st.markdown("#### Quick Assign or Swap a Plot")
            search_query = st.text_input("🔍 Search Resident (Type Name, Phone, or ID)", placeholder="e.g., 91234567 or AHMAD", key="admin_search")
            selected_participant = None
            current_plot_num = None
            if search_query:
                s = search_query.strip().lower()
                participants = st.session_state.get('participants', [])
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
                pid_l = str(selected_participant['id']).lower().strip()
                own_in_block = next((p for p in block_plots if p.get('occupied') and str(p.get('user_id', '')).lower().strip() == pid_l), None)
                own_elsewhere = next((p for p in plots if p.get('occupied') and (p.get('block_name') or '').strip() != selected_block and str(p.get('user_id', '')).lower().strip() == pid_l), None)
                if own_in_block:
                    current_plot_num = own_in_block['plot_number']
                    st.warning(f"⚠️ {selected_participant['name']} owns **Plot {current_plot_num} in {selected_block}**. Assigning below will SWAP it.")
                if own_elsewhere:
                    st.info(f"🏢 **Gentle reminder:** {selected_participant['name']} also owns Plot {own_elsewhere['plot_number']} in {own_elsewhere.get('block_name')}. Assigning here is an **ADDITIONAL** rental — that plot will NOT be released.")
                available_plots = [p for p in plots_dict.values() if not p.get('occupied')]
                if current_plot_num:
                    available_plots = [p for p in available_plots if p.get('plot_number') != current_plot_num]
                if not available_plots:
                    st.error("❌ No available plots to assign in this block.")
                else:
                    plot_options = {f"Plot {p['plot_number']} (Type {p.get('plot_type','B')})": p['plot_number'] for p in available_plots}
                    selected_plot_label = st.selectbox("Select Target Plot", list(plot_options.keys()), key="admin_plot_select")
                    selected_plot_num = plot_options[selected_plot_label]
                    renewal_date = st.date_input("📅 Renewal Due Date (Optional)", value=None, key="admin_assign_renewal")
                    button_label = "🔄 Swap to New Plot" if current_plot_num else "✅ Assign New Plot"
                    if st.button(button_label, type="primary", use_container_width=True):
                        try:
                            if current_plot_num and current_plot_num != selected_plot_num:
                                supabase.table('garden_plots').update({
                                    'occupied': False, 'user_id': None, 'renewal_due_date': None,
                                    'renewal_status': None,
                                    'change_log': f"Auto-released due to swap to {selected_plot_num}",
                                    'updated_at': datetime.now().isoformat()
                                }).eq('block_name', selected_block).eq('plot_number', current_plot_num).execute()
                            updates = {
                                'user_id': selected_participant['id'],
                                'change_log': f"Admin assigned to {selected_participant['id']}",
                                'block_name': selected_block,
                                'occupied': True,
                                'updated_at': datetime.now().isoformat()
                            }
                            if renewal_date:
                                updates['renewal_due_date'] = str(renewal_date)
                                updates['renewal_status'] = 'active'
                            supabase.table('garden_plots').update(updates).eq('block_name', selected_block).eq('plot_number', selected_plot_num).execute()
                            if 'Gardener' not in selected_participant.get('member_type', ''):
                                new_type = (selected_participant.get('member_type', 'Resident') + ', Gardener').strip(', ')
                                supabase.table('participants').update({'member_type': new_type}).eq('id', selected_participant['id']).execute()
                            log_action('admin', 'ASSIGN_PLOT', f"Plot {selected_plot_num} ({selected_block}) - {selected_participant['name']}", str(selected_plot_num))
                            st.success(f"✅ Assigned Plot {selected_plot_num} ({selected_block}) to {selected_participant['name']}!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error during assignment: {e}")
            else:
                st.info("🔍 Start typing above to search for a resident.")
                
        with tab_list:
            st.markdown("#### Manage All Plots")
            # 🔥 Dynamic max_value based on actual plots in block
            max_plot_search = max([76] + [p['plot_number'] for p in block_plots] + [i['plot_number'] for i in layout_data]) if (block_plots or layout_data) else 76
            plot_edit_num = st.number_input("🔍 Enter Plot Number to Edit", min_value=1, max_value=max_plot_search, value=1, step=1, key="plot_edit_search")
            found_plot = next((p for p in block_plots if p['plot_number'] == plot_edit_num), None)
            found_layout = next((l for l in layout_data if l['plot_number'] == plot_edit_num), None)
            if not found_layout:
                st.warning(f"⚠️ Plot {plot_edit_num} does not exist in the layout for {selected_block}.")
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
                    <h4 style="margin:0;">Plot {plot_edit_num} (Type {current_plot_type}) — {selected_block}</h4>
                    <div style="font-size:14px; color:#aaa;">Owner: {owner_name}</div>
                    <div style="font-size:14px; color:#aaa;">Status: {'✅ Occupied' if is_occupied else '🟩 Available (Community Stewarded)'}</div>
                </div>""", unsafe_allow_html=True)
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("**📐 Manage Plot Size**")
                    new_plot_type = st.selectbox("Select New Size", ["A", "B", "C", "D"],
                        index=["A", "B", "C", "D"].index(current_plot_type) if current_plot_type in ["A", "B", "C", "D"] else 1,
                        key=f"size_change_{plot_edit_num}")
                    if st.button(f"💾 Update Plot Size", key=f"save_size_{plot_edit_num}", use_container_width=True):
                        if new_plot_type != current_plot_type:
                            try:
                                supabase.table('garden_layout').update({'plot_type': new_plot_type}).eq('block_name', selected_block).eq('plot_number', plot_edit_num).execute()
                                supabase.table('garden_plots').update({'plot_type': new_plot_type}).eq('block_name', selected_block).eq('plot_number', plot_edit_num).execute()
                                log_action(st.session_state.user_role, "CHANGE_PLOT_SIZE", f"Plot {plot_edit_num} ({selected_block}) {current_plot_type}→{new_plot_type}", str(plot_edit_num))
                                st.success(f"✅ Plot {plot_edit_num} size updated!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error updating size: {e}")
                        else:
                            st.info("No change detected.")
                with c2:
                    if is_occupied:
                        st.markdown("**💰 Payment & Ownership**")
                        if st.button(f"Toggle Payment Status", key=f"pay_btn_{plot_edit_num}", use_container_width=True):
                            try:
                                new_status = not is_paid
                                supabase.table('garden_plots').update({'paid': new_status, 'updated_at': datetime.now().isoformat()}).eq('block_name', selected_block).eq('plot_number', plot_edit_num).execute()
                                log_action(st.session_state.user_role, "MARK_PAID" if new_status else "MARK_UNPAID", f"Plot {plot_edit_num} ({selected_block}) - {owner_name}", str(plot_edit_num))
                                st.success(f"Plot {plot_edit_num} payment status updated!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")
                    st.markdown("**📅 Renewal Date**")
                    current_renewal = found_plot.get('renewal_due_date') if found_plot else None
                    try: default_date = datetime.strptime(str(current_renewal)[:10], "%Y-%m-%d").date() if current_renewal else None
                    except: default_date = None
                    new_renewal = st.date_input("Renewal Date", value=default_date, key=f"renew_{plot_edit_num}")
                    if st.button("💾 Update Renewal", key=f"save_renew_{plot_edit_num}", use_container_width=True):
                        if found_plot:
                            supabase.table('garden_plots').update({'renewal_due_date': str(new_renewal), 'renewal_status': 'active', 'updated_at': datetime.now().isoformat()}).eq('block_name', selected_block).eq('plot_number', plot_edit_num).execute()
                            st.success("Renewal date updated!")
                            st.rerun()
                        else:
                            st.warning("Renewal dates are only applicable for occupied plots.")
                    if is_occupied:
                        st.divider()
                        if st.button("❌ Force Release Plot", type="secondary", key=f"release_{plot_edit_num}", use_container_width=True):
                            other_plots = [p for p in plots if p.get('user_id') == owner_id and not (p.get('block_name') == selected_block and p.get('plot_number') == plot_edit_num)]
                            if owner_data and not other_plots:
                                updated_types = [t.strip() for t in owner_data.get('member_type', '').split(',') if t.strip() != 'Gardener']
                                new_type = ', '.join(updated_types) if updated_types else 'Resident'
                                supabase.table('participants').update({'member_type': new_type}).eq('id', owner_id).execute()
                            supabase.table('garden_plots').update({'occupied': False, 'user_id': None, 'renewal_due_date': None, 'renewal_status': None, 'change_log': "Force released by admin", 'updated_at': datetime.now().isoformat()}).eq('block_name', selected_block).eq('plot_number', plot_edit_num).execute()
                            log_action('admin', 'RELEASE_PLOT', f"Plot {plot_edit_num} ({selected_block}) force released", str(plot_edit_num))
                            st.success(f"Plot {plot_edit_num} released!")
                            st.rerun()
                            
            with tab_layout:
                st.session_state.admin_garden_tab = "🗺️ Edit Garden Map"
                st.markdown("#### Design Your Garden Map")
                st.caption("💡 Create, rename, or delete blocks. Bulk generate layouts, or manually design with custom rows/cols.")
                layout_data = current_block_layout
                col_left, col_right = st.columns([1, 2])
                with col_left:
                    # CREATE NEW BLOCK
                    with st.expander("➕ Create New Block", expanded=False):
                        new_block_name = st.text_input("New Block Name", placeholder="e.g., Block 624, WCC RTG", key="new_block_input_garden")
                        new_block_plots = st.number_input("How many plots for new block?", min_value=1, max_value=200, value=76, step=1, key="new_block_plot_count")
                        if st.button("Create New Block", type="secondary", use_container_width=True):
                            if new_block_name.strip():
                                if load_garden_layout(new_block_name.strip()):
                                    st.error(f"Layout for {new_block_name.strip()} already exists.")
                                else:
                                    default_data = generate_default_layout(new_block_name.strip(), int(new_block_plots))
                                    for item in default_data:
                                        save_garden_layout(item['block_name'], item['plot_number'], item['grid_row'], item['grid_col'], item['plot_type'])
                                    seed_block_plots(new_block_name.strip(), default_data)
                                    st.success(f"✅ Created layout + plot rows for {new_block_name.strip()} ({new_block_plots} plots)!")
                                    st.info(f"👉 Select '{new_block_name.strip()}' from the dropdown at the top to edit it.")
                            else:
                                st.error("Please enter a name.")
                    # RENAME BLOCK
                    with st.expander("✏️ Rename Current Block", expanded=False):
                        st.caption(f"Rename '{selected_block}' to a new name.")
                        new_block_name_rename = st.text_input("New Name", placeholder="e.g., Woodlands CC RTG", key="rename_block_input")
                        if st.button("Rename Block", type="secondary", use_container_width=True):
                            if new_block_name_rename.strip() and new_block_name_rename.strip() != selected_block:
                                if load_garden_layout(new_block_name_rename.strip()):
                                    st.error(f"A block named '{new_block_name_rename.strip()}' already exists.")
                                else:
                                    if rename_garden_block(selected_block, new_block_name_rename.strip()):
                                        st.success(f"✅ Renamed '{selected_block}' → '{new_block_name_rename.strip()}' (layout + plots synced)!")
                                        st.rerun()
                                    else:
                                        st.error("Error renaming block.")
                            else:
                                st.error("Please enter a valid new name.")
                    # DELETE BLOCK
                    with st.expander("🗑️ Delete Current Block", expanded=False):
                        st.warning(f"⚠️ This deletes the '{selected_block}' LAYOUT only. garden_plots rows are kept (safe).")
                        confirm_delete = st.checkbox("I understand this action is permanent.", key="confirm_delete_block")
                        if confirm_delete:
                            if st.button(f"🚨 Permanently Delete '{selected_block}'", type="primary", use_container_width=True):
                                if delete_garden_block(selected_block):
                                    st.success(f"✅ Block '{selected_block}' deleted!")
                                    st.rerun()
                                else:
                                    st.error("Error deleting block.")

                    # 🔥 RESTORED: SECTION SELECTION
                    st.markdown("**🗂️ Section Selection**")
                    if layout_data:
                        _all_nums = [i['plot_number'] for i in layout_data]
                        section_options = []
                        if any(p <= 9 for p in _all_nums): section_options.append("Section 1")
                        if any(10 <= p <= 20 for p in _all_nums): section_options.append("Section 2")
                        if any(21 <= p <= 29 for p in _all_nums): section_options.append("Section 3")
                        if any(30 <= p <= 38 for p in _all_nums): section_options.append("Section 4")
                        if any(39 <= p <= 47 for p in _all_nums): section_options.append("Section 5")
                        if any(48 <= p <= 58 for p in _all_nums): section_options.append("Section 6")
                        if any(59 <= p <= 67 for p in _all_nums): section_options.append("Section 7")
                        if any(p >= 68 for p in _all_nums): section_options.append("Section 8")
                        section_options.append("🌐 All Sections")
                        selected_section = st.selectbox("Select Section to Edit", section_options, index=0, key="edit_section_dropdown")
                    else:
                        selected_section = "Section 1"
                        st.info("No layout data. Create plots manually below.")
                    st.divider()

                    # BULK AUTO-GENERATE
                    st.markdown("**⚡ Bulk Auto-Generate Layout**")
                    bulk_plot_count = st.number_input("How many plots to generate?", min_value=1, max_value=200, value=76, step=1, key="bulk_plot_count")
                    if st.button(f"Generate {bulk_plot_count} Plots", type="primary", use_container_width=True):
                        clear_garden_layout(selected_block)
                        default_data = generate_default_layout(selected_block, int(bulk_plot_count))
                        for item in default_data:
                            save_garden_layout(item['block_name'], item['plot_number'], item['grid_row'], item['grid_col'], item['plot_type'])
                        seed_block_plots(selected_block, default_data)
                        st.success(f"✅ Generated {bulk_plot_count} plots for {selected_block}!")
                        st.rerun()
                    st.divider()

                    st.markdown("**🔢 Grid Canvas Size**")
                    editor_rows = st.number_input("Editor Rows", min_value=1, max_value=20, value=5, step=1, key="editor_rows")
                    editor_cols = st.number_input("Editor Columns", min_value=1, max_value=20, value=10, step=1, key="editor_cols")
                    st.divider()

                    # PLOT DROPDOWN (dynamic max)
                    max_plot_num = max([76] + [i['plot_number'] for i in layout_data] + list(plots_dict.keys())) if (layout_data or plots_dict) else 76
                    all_plot_options = {}
                    for p_num in range(1, max_plot_num + 1):
                        is_in_block = p_num in [i['plot_number'] for i in layout_data]
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
                    if 'selected_plot_label' not in st.session_state:
                        st.session_state.selected_plot_label = all_labels[0] if all_labels else ""
                    if st.session_state.selected_plot_label not in all_labels:
                        unassigned_labels = [l for l in all_labels if "(Unassigned)" in l]
                        if unassigned_labels:
                            st.session_state.selected_plot_label = unassigned_labels[0]
                        elif all_labels:
                            st.session_state.selected_plot_label = all_labels[-1]
                    st.caption(f"Total plots: {len(all_plot_options)}")
                    selected_plot_label = st.selectbox(
                        "Select a plot (Occupied plots will auto-swap)",
                        all_labels,
                        index=all_labels.index(st.session_state.selected_plot_label),
                        key="new_plot_dropdown"
                    )
                    st.session_state.selected_plot_label = selected_plot_label
                    selected_new_plot = all_plot_options[selected_plot_label]
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
                    # 🔥 FIXED CSS: numbers stay on ONE line and fit nicely in the box
                    st.markdown("""
                    <style>
                        div[data-testid="stButton"] button {
                            white-space: nowrap !important;
                            font-size: 14px !important;
                            padding: 2px 0 !important;
                            min-height: 44px !important;
                            width: 100% !important;
                        }
                        div[data-testid="stButton"] button p,
                        div[data-testid="stButton"] button span {
                            white-space: nowrap !important;
                            overflow: hidden !important;
                            text-overflow: ellipsis !important;
                            margin: 0 !important;
                        }
                    </style>
                    """, unsafe_allow_html=True)
                    grid_container = st.container()
                    with grid_container:
                        section_data = []
                        if layout_data:
                            for item in layout_data:
                                p = item['plot_number']
                                if selected_section == "🌐 All Sections":
                                    section_data.append(item)
                                elif selected_section == "Section 1" and p <= 9: section_data.append(item)
                                elif selected_section == "Section 2" and 10 <= p <= 20: section_data.append(item)
                                elif selected_section == "Section 3" and 21 <= p <= 29: section_data.append(item)
                                elif selected_section == "Section 4" and 30 <= p <= 38: section_data.append(item)
                                elif selected_section == "Section 5" and 39 <= p <= 47: section_data.append(item)
                                elif selected_section == "Section 6" and 48 <= p <= 58: section_data.append(item)
                                elif selected_section == "Section 7" and 59 <= p <= 67: section_data.append(item)
                                elif selected_section == "Section 8" and p >= 68: section_data.append(item)
                        # 🔥 When editing one section, shift it to the top of the canvas
                        min_row = min((i['grid_row'] for i in section_data), default=0) if (section_data and selected_section != "🌐 All Sections") else 0
                        editor_grid = [[None for _ in range(editor_cols)] for _ in range(editor_rows)]
                        for item in section_data:
                            r = item['grid_row'] - min_row
                            c = item['grid_col']
                            if 0 <= r < editor_rows and c < editor_cols:
                                editor_grid[r][c] = item['plot_number']
                        for r in range(editor_rows):
                            cols_ui = st.columns(editor_cols)
                            for c in range(editor_cols):
                                with cols_ui[c]:
                                    plot_num = editor_grid[r][c]
                                    if plot_num is None:
                                        if st.button("+", key=f"add_{r}_{c}_{selected_block}", use_container_width=True):
                                            existing_spot = next((item for item in layout_data if item['plot_number'] == selected_new_plot), None)
                                            if existing_spot:
                                                remove_garden_layout(selected_block, selected_new_plot)
                                            if save_garden_layout(selected_block, selected_new_plot, r + min_row, c, selected_size):
                                                seed_block_plots(selected_block, [{'plot_number': selected_new_plot, 'plot_type': selected_size}])
                                                st.rerun()
                                    else:
                                        layout_item = next((item for item in layout_data if item['plot_number'] == plot_num), None)
                                        plot_type = layout_item['plot_type'] if layout_item and 'plot_type' in layout_item else 'B'
                                        color = get_plot_type_color(plot_type)
                                        if st.button(label=f"{plot_num}", key=f"remove_{plot_num}_{selected_block}", use_container_width=True, type="primary"):
                                            if remove_garden_layout(selected_block, plot_num):
                                                st.rerun()
                                        st.markdown(
                                            f'<style> div[data-testid="stButton"] button[key="remove_{plot_num}_{selected_block}"], div[data-testid="stButton"] button[key="remove_{plot_num}_{selected_block}"] p {{ background-color: {color} !important; color: white !important; border: none; font-weight: bold; font-size: 14px; white-space: nowrap !important; }}</style>',
                                            unsafe_allow_html=True
                                        )
    else:
        st.caption("🔒 Interactive Map Editor is restricted to System Admins.")
        
    # ── 5. STATISTICS (per selected block) ─────────────────────
    st.markdown("---")
    st.markdown("## Statistics")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Plots", total_plots_in_block if 'total_plots_in_block' in locals() else 0)
    c2.metric("💲 Paid", paid_count if 'paid_count' in locals() else 0)
    c3.metric("🤝 Unpaid (Pending)", unpaid_count if 'unpaid_count' in locals() else 0)
    c4.metric("🌱 Community Stewarded", community_count if 'community_count' in locals() else 0)
    st.markdown(f"### By Type ({selected_block})")
    tc = st.columns(4)
    for i, (tk, ti) in enumerate(PLOT_TYPES.items()):
        with tc[i]:
            to = len([p for p in block_plots if p.get('plot_type') == tk and p.get('occupied')])
            block_total = len([x for x in layout_data if x.get('plot_type') == tk]) if layout_data else ti["total"]
            pc = (to / block_total) * 100 if block_total > 0 else 0
            st.markdown(f'<div style="background:{ti["colour"]};color:white;padding:10px;border-radius:8px;text-align:center;"><div style="font-size:14px;font-weight:bold;">Type {tk}</div><div style="font-size:20px;margin:3px 0;">{to}/{block_total}</div><div>{ti["area"]} m²</div><div>({pc:.1f}%)</div></div>', unsafe_allow_html=True)