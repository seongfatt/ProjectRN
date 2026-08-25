import streamlit as st
import pandas as pd
import json
from config import supabase, DB_CONNECTED
from utils import find_participant_by_phone, clean_phone_number

# Define Plot Types
PLOT_TYPES_CONFIG = {
    "A (12 boxes / 3.0 m²)": {"w": 4, "h": 3, "boxes": 12},
    "B (10 boxes / 2.5 m²)": {"w": 5, "h": 2, "boxes": 10},
    "C (8 boxes / 2.0 m²)": {"w": 4, "h": 2, "boxes": 8},
}

def show_floorplan_designer():
    st.header("🎨 Box-Map Designer (Full Management)")
    st.caption("Sections: Add, Edit, Rename, Duplicate, Delete.")

    if not DB_CONNECTED:
        st.error("Database not connected")
        return

    # --- Get all saved sections from DB ---
    try:
        sections_data = supabase.table('section_settings').select('*').execute().data
        saved_sections = {s['section_name']: (int(s['rows']), int(s['cols'])) for s in sections_data}
    except Exception as e:
        st.error(f"Missing table: {e}. Please run the SQL command to create it.")
        saved_sections = {}

    # --- Section Selector ---
    if saved_sections:
        sec_name = st.selectbox("Select Section", list(saved_sections.keys()), key="sec_selector")
    else:
        sec_name = None

    # --- Create New Section ---
    with st.expander("➕ Create New Section", expanded=not saved_sections):
        c1, c2, c3 = st.columns(3)
        with c1:
            new_name = st.text_input("Section Name")
        with c2:
            new_rows = st.number_input("Rows", min_value=1, max_value=100, value=22)
        with c3:
            new_cols = st.number_input("Cols", min_value=1, max_value=100, value=17)
        
        if st.button("✅ Create Section", type="primary"):
            if new_name.strip() and new_name.strip() not in saved_sections:
                try:
                    supabase.table('section_settings').upsert({
                        'section_name': new_name.strip(), 'rows': int(new_rows), 'cols': int(new_cols)
                    }, on_conflict='section_name').execute()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error saving: {e}")
            elif new_name.strip() in saved_sections:
                st.error("Section name already exists.")
            else:
                st.error("Please enter a section name.")

    # --- 🛠️ Manage Existing Section (Edit, Rename, Duplicate, Delete) ---
    if sec_name:
        with st.expander("🛠️ Manage Current Section", expanded=False):
            rows, cols = saved_sections[sec_name]
            
            # 1. Rename Section
            st.markdown("**✏️ Rename Section**")
            rename_col1, rename_col2 = st.columns([3, 1])
            with rename_col1:
                new_rename = st.text_input("New Section Name", value=sec_name, key="rename_input")
            with rename_col2:
                st.write("")
                if st.button("Rename", use_container_width=True):
                    if new_rename.strip() and new_rename.strip() != sec_name:
                        if new_rename.strip() in saved_sections:
                            st.error("Section name already exists.")
                        else:
                            try:
                                # Update section_settings
                                supabase.table('section_settings').update({'section_name': new_rename.strip()}).eq('section_name', sec_name).execute()
                                # Update all related plots
                                supabase.table('box_map_plots').update({'section_name': new_rename.strip()}).eq('section_name', sec_name).execute()
                                st.success(f"Section renamed to '{new_rename.strip()}'")
                                st.session_state.current_sec = None  # Force reload
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error renaming: {e}")
                    else:
                        st.error("Please enter a valid new name.")

            st.divider()

            # 2. Resize Section (Warning: may affect plots)
            st.markdown("**📐 Resize Section**")
            st.caption("⚠️ Resizing will cut off or pad existing plot cells. Proceed with caution.")
            resize_col1, resize_col2, resize_col3 = st.columns([1,1,1])
            with resize_col1:
                new_rows = st.number_input("New Rows", min_value=1, max_value=100, value=rows, key="resize_rows")
            with resize_col2:
                new_cols = st.number_input("New Cols", min_value=1, max_value=100, value=cols, key="resize_cols")
            with resize_col3:
                st.write("")
                if st.button("Resize", use_container_width=True):
                    if new_rows > 0 and new_cols > 0:
                        # Update section_settings
                        supabase.table('section_settings').update({'rows': int(new_rows), 'cols': int(new_cols)}).eq('section_name', sec_name).execute()
                        st.success("Section size updated. Plot cells outside the new bounds will be ignored.")
                        st.session_state.current_sec = None  # Force reload
                        st.rerun()
                    else:
                        st.error("Rows and Cols must be positive.")

            st.divider()

            # 3. Duplicate Section
            st.markdown("**📋 Duplicate Section**")
            dup_col1, dup_col2 = st.columns([3, 1])
            with dup_col1:
                dup_name = st.text_input("New Section Name (Copy)", value=f"Copy of {sec_name}", key="dup_input")
            with dup_col2:
                st.write("")
                if st.button("Duplicate", use_container_width=True):
                    if dup_name.strip() and dup_name.strip() not in saved_sections:
                        try:
                            # Copy section_settings
                            supabase.table('section_settings').insert({
                                'section_name': dup_name.strip(), 'rows': rows, 'cols': cols
                            }).execute()
                            # Copy all box_map_plots
                            plots_data = supabase.table('box_map_plots').select('*').eq('section_name', sec_name).execute().data
                            for plot in plots_data:
                                new_plot = {k: v for k, v in plot.items() if k != 'id'}  # Remove auto id
                                new_plot['section_name'] = dup_name.strip()
                                supabase.table('box_map_plots').insert(new_plot).execute()
                            st.success(f"Section duplicated as '{dup_name.strip()}'")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error duplicating: {e}")
                    else:
                        st.error("Section name already exists or is empty.")

            st.divider()

            # 4. Delete Section
            st.markdown("**🗑️ Delete Section**")
            confirm_delete = st.checkbox("I understand this permanently deletes the section and its plots.", key="delete_confirm")
            if confirm_delete:
                if st.button("Delete Section", type="primary", use_container_width=True):
                    try:
                        # Delete box_map_plots first
                        supabase.table('box_map_plots').delete().eq('section_name', sec_name).execute()
                        # Then delete section_settings
                        supabase.table('section_settings').delete().eq('section_name', sec_name).execute()
                        st.success(f"Section '{sec_name}' deleted.")
                        st.session_state.current_sec = None
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error deleting: {e}")

    # --- If a section is selected, load its data ---
    if sec_name:
        rows, cols = saved_sections[sec_name]
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.caption("Section Size (Locked)")
        with c2: st.metric("Rows", rows)
        with c3: st.metric("Cols", cols)
        with c4: st.caption("")
    else:
        st.info("Create a new section above to begin.")
        return

    # --- Initialize Grid & Force Reset on Section Change ---
    if 'current_sec' not in st.session_state or st.session_state.current_sec != sec_name:
        st.session_state.grid_df = pd.DataFrame(0, index=range(rows), columns=[f"Col {i}" for i in range(cols)])
        st.session_state.current_sec = sec_name
        st.session_state.loaded_grid_sec = None  # Force reload for the new section

    # --- Load Grid Data ---
    if st.session_state.get('loaded_grid_sec') != sec_name:
        try:
            st.session_state.grid_df = pd.DataFrame(0, index=range(rows), columns=[f"Col {i}" for i in range(cols)])
            data = supabase.table('box_map_plots').select('*').eq('section_name', sec_name).execute().data
            for row in data:
                cells = row.get('cells')
                if isinstance(cells, str): cells = json.loads(cells)
                if cells:
                    for r, c in cells:
                        if r < rows and c < cols:
                            st.session_state.grid_df.iloc[r, c] = row['plot_id']
                else:
                    for r in range(row['start_row'], row['start_row'] + row['height']):
                        for c in range(row['start_col'], row['start_col'] + row['width']):
                            if r < rows and c < cols:
                                st.session_state.grid_df.iloc[r, c] = row['plot_id']
            st.session_state.loaded_grid_sec = sec_name
        except:
            pass

    st.divider()

        # ── Quick Paint (Auto-Generate Plot ID or Manual Override) ──
    st.subheader("⚡ Quick Paint (Plot ID)")

    # Define max plot ID here for the input field
    max_plot_id = rows * cols
    
    existing_ids = set(st.session_state.grid_df.values.flatten().tolist())
    existing_ids.discard(0)
    next_id = 1
    while next_id in existing_ids:
        next_id += 1

    qp1, qp2, qp3, qp4 = st.columns(4)
    with qp1:
        start_row = st.number_input("Start Row", min_value=0, max_value=rows-1, value=0, key="qp_start_row")
    with qp2:
        start_col = st.number_input("Start Col", min_value=0, max_value=cols-1, value=0, key="qp_start_col")
    with qp3:
        plot_type_label = st.selectbox("Select Plot Type", list(PLOT_TYPES_CONFIG.keys()) + ["Custom Size"], key="qp_type")
        if plot_type_label == "Custom Size":
            cw = st.number_input("Custom Width", min_value=1, max_value=20, value=4, key="qp_cw")
            ch = st.number_input("Custom Height", min_value=1, max_value=20, value=3, key="qp_ch")
            plot_type = {"w": int(cw), "h": int(ch)}
        else:
            plot_type = PLOT_TYPES_CONFIG[plot_type_label]
            
    with qp4:
        # 🔥 NEW: Let user choose to Auto-Generate or Manual Input
        use_auto = st.checkbox("Auto-ID", value=True, key=f"auto_id_{sec_name}")
        
        if use_auto:
            manual_id = next_id
            st.success(f"🔥 Next Plot ID: **{next_id}**")
        else:
            manual_id = st.number_input("Manual Plot ID", min_value=1, max_value=max_plot_id, value=next_id, key=f"manual_id_{sec_name}")
            st.info(f"Using manual ID: **{manual_id}**")

    if st.button(f"🖌️ Paint Plot (ID {manual_id})", type="primary", width='stretch'):
        end_row = int(start_row) + plot_type['h'] - 1
        end_col = int(start_col) + plot_type['w'] - 1
        if end_row < rows and end_col < cols:
            for r in range(int(start_row), end_row + 1):
                for c in range(int(start_col), end_col + 1):
                    st.session_state.grid_df.iloc[r, c] = manual_id
            
            # The "Magic Fix" to allow the grid to update
            if f"map_editor_{sec_name}" in st.session_state:
                del st.session_state[f"map_editor_{sec_name}"]
            
            st.rerun()
        else:
            st.error(f"❌ Block needs {plot_type['h']} rows and {plot_type['w']} cols. It doesn't fit here.")

    # ── Grid (Dropdowns) ──
    st.subheader("🗺️ Step 1: Fine-Tune Grid (Dropdowns)")
    max_plot_id = rows * cols
    options_list = list(range(0, max_plot_id + 1))

    edited_df = st.data_editor(
        st.session_state.grid_df,
        use_container_width=True,
        key=f"map_editor_{sec_name}",
        height=500,
        hide_index=False, 
        column_config={col: st.column_config.SelectboxColumn(label=col, options=options_list, required=True) for col in st.session_state.grid_df.columns}
    )

    edited_df = edited_df.fillna(0)
    st.session_state.grid_df = edited_df

    st.divider()

    # ── Assign & Save ──
    st.subheader("📋 Step 2: Assign Owner & Save")
    unique_ids = sorted([int(v) for v in edited_df.values.flatten() if v > 0])

    if not unique_ids:
        st.info("Paint a plot first.")
    else:
        a1, a2, a3, a4 = st.columns(4)
        with a1:
            selected_id = st.selectbox("Select Plot ID to Save", unique_ids, key="save_select_id")
            rows_list, cols_list = [], []
            for r in range(rows):
                for c in range(cols):
                    if int(edited_df.iloc[r, c]) == selected_id:
                        rows_list.append(r)
                        cols_list.append(c)

            if rows_list:
                start_r = min(rows_list)
                start_c = min(cols_list)
                end_r = max(rows_list)
                end_c = max(cols_list)
                width = end_c - start_c + 1
                height = end_r - start_r + 1
                box_count = len(rows_list)
                cells = [[r, c] for r, c in zip(rows_list, cols_list)]
                st.caption(f"**Plot {selected_id}:** {width} x {height} units ({box_count} boxes)")

        with a2:
            phone_input = st.text_input("Owner Phone Number", placeholder="e.g., 91234567", key="save_phone")
            owner_name = ""
            if phone_input and len(clean_phone_number(phone_input)) >= 8:
                res = find_participant_by_phone(clean_phone_number(phone_input))
                if res:
                    owner_name = res['name']
                    st.success(f"Found: **{owner_name}**")
            owner_name = st.text_input("Or Type Owner Name", value=owner_name, key="save_owner_name")
            status = st.radio("Status", ["Paid", "Unpaid", "Empty"], horizontal=True, key="save_status")

        with a3:
            st.write("")
            if st.button("💾 Save Plot to Database", width='stretch'):
                try:
                    supabase.table('box_map_plots').delete().eq('section_name', sec_name).eq('plot_id', selected_id).execute()
                    supabase.table('box_map_plots').insert({
                        "section_name": sec_name,
                        "plot_id": selected_id,
                        "start_row": start_r,
                        "start_col": start_c,
                        "width": width,
                        "height": height,
                        "box_count": box_count,
                        "cells": json.dumps(cells),
                        "owner_id": "PENDING" if not phone_input else clean_phone_number(phone_input),
                        "owner_name": owner_name,
                        "status": status
                    }).execute()
                    st.success(f"✅ Plot {selected_id} saved successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error saving: {e}")

        with a4:
            st.write("")
            if st.button("🧹 Erase Selected Plot", width='stretch'):
                st.session_state.grid_df = edited_df.replace(selected_id, 0)
                try:
                    supabase.table('box_map_plots').delete().eq('section_name', sec_name).eq('plot_id', selected_id).execute()
                except:
                    pass
                st.success(f"Plot {selected_id} erased from map!")
                st.rerun()

    # ── Step 3: Visual Map Preview (Axis Labels Fixed) ──
    st.divider()
    st.subheader(f"🗺️ Step 3: Visual Map Preview ({sec_name})")
    html = '<div style="overflow-x: auto; border: 2px solid #333; padding: 5px; border-radius: 8px; background: #1e1e1e; display: inline-block;">'
    html += '<div style="display: flex;"><div style="width: 30px;"></div>'
    for c in range(cols):
        html += f'<div style="width: 25px; font-size: 10px; color: #aaa; text-align: center;">{c}</div>'
    html += '</div>'
    for r in range(rows):
        html += '<div style="display: flex;">'
        html += f'<div style="width: 30px; font-size: 10px; color: #aaa; display: flex; align-items: center; justify-content: center;">{r}</div>'
        for c in range(cols):
            val = edited_df.iloc[r, c]
            plot_id = int(val) if not pd.isna(val) else 0
            if plot_id > 0:
                html += f'<div style="width: 25px; height: 25px; background: #28a745; border: 1px solid white; color: white; font-size: 8px; display: flex; align-items: center; justify-content: center;">{plot_id}</div>'
            else:
                html += f'<div style="width: 25px; height: 25px; background: #2a2a2a; border: 1px dashed #555;"></div>'
        html += '</div>'
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)