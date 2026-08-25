import streamlit as st
import pandas as pd
import json
from config import supabase, DB_CONNECTED
from utils import find_participant_by_phone, clean_phone_number

# Define Plot Types & Colors
PLOT_TYPES_CONFIG = {
    "A (12 boxes / 3.0 m²)": {"w": 4, "h": 3, "boxes": 12, "color": "#2ca02c"}, # Green
    "B (10 boxes / 2.5 m²)": {"w": 5, "h": 2, "boxes": 10, "color": "#ff7f0e"}, # Orange
    "C (8 boxes / 2.0 m²)": {"w": 4, "h": 2, "boxes": 8, "color": "#1f77b4"}, # Blue
}
# 🔥 AUTO-LOCATE COLOR BASED ON BOX COUNT
def get_color_from_box_count(box_count):
    if box_count == 12: return "#2ca02c"  # Type A (Green)
    if box_count == 10: return "#ff7f0e"  # Type B (Orange)
    if box_count == 8:  return "#1f77b4"  # Type C (Blue)
    return "#6f42c1"                      # Custom Size (Purple)

def show_floorplan_designer():
    st.header("🎨 Box-Map Designer (Dynamic Colors)")
    st.caption("Maps now follow the exact Type colors! Fixed squares for single and double digits.")

    if not DB_CONNECTED:
        st.error("Database not connected")
        return

    # 🔥 Add Plot Types Store
    if 'plot_types' not in st.session_state:
        st.session_state.plot_types = {}

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
                    supabase.table('section_settings').upsert({'section_name': new_name.strip(), 'rows': int(new_rows), 'cols': int(new_cols)}, on_conflict='section_name').execute()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error saving: {e}")
            elif new_name.strip() in saved_sections:
                st.error("Section name already exists.")
            else:
                st.error("Please enter a section name.")

    # --- Manage Section (Rename, Resize, Duplicate, Delete) ---
    if sec_name:
        with st.expander("🛠️ Manage Current Section", expanded=False):
            rows, cols = saved_sections[sec_name]
            
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
                                supabase.table('section_settings').update({'section_name': new_rename.strip()}).eq('section_name', sec_name).execute()
                                supabase.table('box_map_plots').update({'section_name': new_rename.strip()}).eq('section_name', sec_name).execute()
                                st.session_state.current_sec = None
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error renaming: {e}")
            st.divider()

            st.markdown("**📐 Resize Section**")
            st.caption("⚠️ Existing plots may be cut off.")
            resize_col1, resize_col2, resize_col3 = st.columns([1,1,1])
            with resize_col1:
                new_rows = st.number_input("New Rows", min_value=1, max_value=100, value=rows, key="resize_rows")
            with resize_col2:
                new_cols = st.number_input("New Cols", min_value=1, max_value=100, value=cols, key="resize_cols")
            with resize_col3:
                st.write("")
                if st.button("Resize", use_container_width=True):
                    supabase.table('section_settings').update({'rows': int(new_rows), 'cols': int(new_cols)}).eq('section_name', sec_name).execute()
                    st.session_state.current_sec = None
                    st.rerun()
            st.divider()

            st.markdown("**📋 Duplicate Section**")
            dup_col1, dup_col2 = st.columns([3, 1])
            with dup_col1:
                dup_name = st.text_input("New Section Name", value=f"Copy of {sec_name}", key="dup_input")
            with dup_col2:
                st.write("")
                if st.button("Duplicate", use_container_width=True):
                    if dup_name.strip() and dup_name.strip() not in saved_sections:
                        try:
                            supabase.table('section_settings').insert({'section_name': dup_name.strip(), 'rows': rows, 'cols': cols}).execute()
                            plots_data = supabase.table('box_map_plots').select('*').eq('section_name', sec_name).execute().data
                            for plot in plots_data:
                                new_plot = {k: v for k, v in plot.items() if k != 'id'}
                                new_plot['section_name'] = dup_name.strip()
                                supabase.table('box_map_plots').insert(new_plot).execute()
                            st.session_state.current_sec = None
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error duplicating: {e}")
            st.divider()

            st.markdown("**🗑️ Delete Section**")
            confirm_delete = st.checkbox("I understand this permanently deletes the section.", key="delete_confirm")
            if confirm_delete:
                if st.button("Delete Section", type="primary", use_container_width=True):
                    supabase.table('box_map_plots').delete().eq('section_name', sec_name).execute()
                    supabase.table('section_settings').delete().eq('section_name', sec_name).execute()
                    st.session_state.current_sec = None
                    st.rerun()

    # --- If a section is selected, load its data ---
    if sec_name:
        rows, cols = saved_sections[sec_name]
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.caption("Section Size")
        with c2: st.metric("Rows", rows)
        with c3: st.metric("Cols", cols)
        with c4: st.caption("")
    else:
        st.info("Create a new section above to begin.")
        return

    # --- Initialize Grid ---
    if 'current_sec' not in st.session_state or st.session_state.current_sec != sec_name:
        st.session_state.grid = {f"{r}_{c}": 0 for r in range(rows) for c in range(cols)}
        st.session_state.current_sec = sec_name
        st.session_state.loaded_grid_sec = None
        st.session_state.plot_types = {} # Reset plot types for new section

    # --- Load Grid Data ---
    if st.session_state.get('loaded_grid_sec') != sec_name:
        try:
            st.session_state.grid = {f"{r}_{c}": 0 for r in range(rows) for c in range(cols)}
            data = supabase.table('box_map_plots').select('*').eq('section_name', sec_name).execute().data
            for row in data:
                st.session_state.plot_types[row['plot_id']] = row.get('plot_type', "C (8 boxes / 2.0 m²)")
                cells = row.get('cells')
                if isinstance(cells, str): cells = json.loads(cells)
                if cells:
                    for r, c in cells:
                        if r < rows and c < cols:
                            st.session_state.grid[f"{r}_{c}"] = row['plot_id']
            st.session_state.loaded_grid_sec = sec_name
        except:
            pass

    st.divider()

    # ── THE "ONE MAP" EDITOR ──
    st.subheader("🗺️ One Map Editor (Click to Paint)")

    # Brush Selector
    max_plot_id = rows * cols
    existing_vals = [v for v in st.session_state.grid.values() if v > 0]
    existing_ids = set(existing_vals)
    next_id = 1
    while next_id in existing_ids:
        next_id += 1

    # 🔥 FIX: Define these BEFORE using them!
    plot_type_label = "C (8 boxes / 2.0 m²)"  # Default to Blue

    b1, b2, b3, b4 = st.columns(4)
    with b1:
        brush_id = st.selectbox("Current Brush (Plot ID)", list(range(1, max_plot_id + 1)), index=next_id - 1, key="brush_id")
    with b2:
        st.write("")
        use_auto = st.checkbox("Auto Next ID", value=True, key="use_auto")
    with b3:
        st.write("")
        # 🔥 FIX: Add the Plot Type Selector here!
        type_label = st.selectbox("Plot Type", list(PLOT_TYPES_CONFIG.keys()), key="brush_type")
        plot_type_label = type_label  # Update the variable

        if not use_auto:
            brush_id = st.number_input("Manual Plot ID", min_value=1, max_value=max_plot_id, value=next_id)
        st.info(f"Next Auto ID: **{next_id}**")
    with b4:
        eraser_mode = st.radio("Mode", ["Paint", "Erase"], horizontal=True, key="mode")

    # 🔥 ULTIMATE FIXED SIZE & BLUE CSS (Scoped perfectly)
    st.markdown("""
    <style>
        .map-grid-container {
            width: fit-content;
            margin: 0 auto;
            padding: 5px;
            border: 1px solid #333;
            border-radius: 8px;
            background: #1e1e1e;
            overflow-x: auto;
        }
        .map-grid-container div[data-testid="stColumn"] {
            gap: 0px !important;
            padding: 0px !important;
            margin: 0px !important;
            width: 32px !important;
            min-width: 32px !important;
            max-width: 32px !important;
            flex: none !important;
        }
        .map-grid-container div.stButton > button {
            width: 32px !important;
            min-width: 32px !important;
            max-width: 32px !important;
            height: 32px !important;
            min-height: 32px !important;
            max-height: 32px !important;
            padding: 0 !important;
            margin: 0 !important;
            border-radius: 0px !important; 
            font-size: 12px !important;
            line-height: 1 !important;
            font-weight: bold !important;
        }
        /* Empty Cells */
        .map-grid-container button[kind="secondary"] {
            background-color: #2a2a2a !important;
            border: 1px dashed #555 !important;
            color: #888 !important;
        }
    </style>
    """, unsafe_allow_html=True)

    # WRAP THE GRID IN THE CONTAINER
    st.markdown('<div class="map-grid-container">', unsafe_allow_html=True)

    # 🔥 PRE-GENERATE CSS FOR THE EXISTING PAINTED CELLS
    css_rules = ""
    for cell_id, plot_id in st.session_state.grid.items():
        if plot_id > 0:
            # Get the color from the stored type (default to Blue if no type found)
            type_label = st.session_state.plot_types.get(plot_id, "C (8 boxes / 2.0 m²)")
            color = PLOT_TYPES_CONFIG.get(type_label, {}).get("color", "#1f77b4")
            css_rules += f"""
                .map-grid-container div[data-testid="stButton"] button[key="map_btn_{cell_id}"] {{
                    background-color: {color} !important;
                    border: 1px solid {color} !important;
                    color: white !important;
                    box-shadow: none !important;
                }}
            """
    if css_rules:
        st.markdown(f"<style>{css_rules}</style>", unsafe_allow_html=True)

    # --- THE GRID FRAGMENT ---
    @st.fragment
    def render_grid(current_brush, current_label):
        header_cols = st.columns([1] + [1] * cols)
        with header_cols[0]:
            st.markdown("<div style='height:32px;'></div>", unsafe_allow_html=True)
        for c in range(cols):
            with header_cols[c + 1]:
                st.markdown(f"<div style='font-size:10px; color:#aaa; text-align:center; line-height:32px;'>{c}</div>", unsafe_allow_html=True)

        for r in range(rows):
            row_cols = st.columns([1] + [1] * cols)
            with row_cols[0]:
                st.markdown(f"<div style='font-size:10px; color:#aaa; text-align:center; line-height:32px;'>{r}</div>", unsafe_allow_html=True)

            for c in range(cols):
                cell_id = f"{r}_{c}"
                value = st.session_state.grid.get(cell_id, 0)
                
                with row_cols[c + 1]:
                    clicked = st.button(
                        str(value) if value > 0 else " ",
                        key=f"map_btn_{cell_id}",
                        type="secondary" if value == 0 else "primary"
                    )
                    
                    if clicked:
                        if eraser_mode == "Erase":
                            st.session_state.grid[cell_id] = 0
                            st.session_state.plot_types.pop(current_brush, None) 
                        else:
                            st.session_state.grid[cell_id] = current_brush
                            # 🔥 Store the label used for painting (auto-color will handle the rest)
                            st.session_state.plot_types[current_brush] = current_label
                        st.rerun(scope="fragment")

    render_grid(brush_id, plot_type_label)
    st.markdown('</div>', unsafe_allow_html=True)

    st.divider()

        # ── Assign & Save ──
    st.subheader("📋 Assign Owner & Save")
    unique_ids = sorted([v for v in st.session_state.grid.values() if v > 0])

    if not unique_ids:
        st.info("Paint a plot first.")
    else:
        a1, a2, a3, a4 = st.columns(4)
        with a1:
            selected_id = st.selectbox("Select Plot ID to Save", unique_ids, key="save_select_id")
            rows_list, cols_list = [], []
            for r in range(rows):
                for c in range(cols):
                    if st.session_state.grid.get(f"{r}_{c}") == selected_id:
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
                        "plot_type": st.session_state.plot_types.get(selected_id, "C (8 boxes / 2.0 m²)"),  # 🔥 Save the type
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
                for k, v in st.session_state.grid.items():
                    if v == selected_id:
                        st.session_state.grid[k] = 0
                try:
                    supabase.table('box_map_plots').delete().eq('section_name', sec_name).eq('plot_id', selected_id).execute()
                except:
                    pass
                st.success(f"Plot {selected_id} erased from map!")
                st.rerun()

    # ── LIVE VISUAL PREVIEW (Auto-Color by Box Count) ──
    st.divider()
    st.subheader(f"👁️ Live Visual Preview ({sec_name})")
    st.caption("Colors follow Type: A=Green, B=Orange, C=Blue, Custom=Purple")

    # Helper function to auto-determine color based on how many boxes are in a plot
    def get_color_from_box_count(box_count):
        if box_count == 12: return "#2ca02c"  # Type A (Green)
        if box_count == 10: return "#ff7f0e"  # Type B (Orange)
        if box_count == 8:  return "#1f77b4"  # Type C (Blue)
        return "#6f42c1"                      # Custom Size (Purple)

    html = '<div style="overflow-x: auto; border: 2px solid #333; padding: 5px; border-radius: 8px; background: #1e1e1e; display: inline-block;">'
    html += '<div style="display: flex;"><div style="width: 30px;"></div>'
    for c in range(cols):
        html += f'<div style="width: 25px; font-size: 10px; color: #aaa; text-align: center;">{c}</div>'
    html += '</div>'

    for r in range(rows):
        html += '<div style="display: flex;">'
        html += f'<div style="width: 30px; font-size: 10px; color: #aaa; display: flex; align-items: center; justify-content: center;">{r}</div>'
        for c in range(cols):
            val = st.session_state.grid.get(f"{r}_{c}", 0)
            if val > 0:
                # 🔥 AUTO-COUNT: Count total boxes for this Plot ID
                box_count = sum(1 for v in st.session_state.grid.values() if v == val)
                
                # 🔥 AUTO-COLOR: Get color based on box count
                color = get_color_from_box_count(box_count)
                
                html += f'<div style="width: 25px; height: 25px; background: {color}; border: 1px solid white; color: white; font-size: 8px; display: flex; align-items: center; justify-content: center;">{val}</div>'
            else:
                html += '<div style="width: 25px; height: 25px; background: #2a2a2a; border: 1px dashed #555;"></div>'
        html += '</div>'
    html += '</div>'

    st.markdown(html, unsafe_allow_html=True)