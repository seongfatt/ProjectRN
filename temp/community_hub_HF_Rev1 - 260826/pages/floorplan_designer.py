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

def get_color_from_box_count(box_count):
    if box_count == 12: return "#2ca02c"  # Type A (Green)
    if box_count == 10: return "#ff7f0e"  # Type B (Orange)
    if box_count == 8:  return "#1f77b4"  # Type C (Blue)
    return "#6f42c1"                      # Custom Size (Purple)

def show_floorplan_designer():
    st.header("🎨 Box-Map Designer (Master Map Edition)")
    st.caption("Switch between Single Section editing and a customizable Master Map view!")

    if not DB_CONNECTED:
        st.error("Database not connected")
        return

    # 🔥 Toggle between views
    view_mode = st.radio("View Mode", ["🔍 Single Section View", "🗺️ Master Map View"], horizontal=True, key="view_mode")

    if view_mode == "🗺️ Master Map View":
        show_master_map_view()
        return  # Stop here to avoid running the Single Section code

    # ==========================================
    # ✅ EXISTING SINGLE SECTION VIEW (DO NOT TOUCH)
    # ==========================================

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

    qp1, qp2, qp3, qp4 = st.columns(4)
    with qp1:
        # This dropdown now actually works!
        selected_brush = st.selectbox("Current Brush (Plot ID)", list(range(1, max_plot_id + 1)), index=next_id - 1, key="brush_id")
    with qp2:
        plot_type_label = st.selectbox("Select Plot Type", list(PLOT_TYPES_CONFIG.keys()) + ["Custom Size"], key="qp_type")
        if plot_type_label == "Custom Size":
            cw = st.number_input("Custom Width", min_value=1, max_value=20, value=4, key="qp_cw")
            ch = st.number_input("Custom Height", min_value=1, max_value=20, value=3, key="qp_ch")
            plot_type_label = "Custom Size"
    with qp3:
        use_auto = st.checkbox("Auto Next ID", value=True, key="use_auto")
    with qp4:
        if use_auto:
            brush_id = next_id
            st.success(f"⚡ Auto-Generating ID: **{brush_id}**")
        else:
            # 🔥 FIX: Use the dropdown selection as the actual brush!
            brush_id = selected_brush
            st.info(f"Manual Brush Selected: **{brush_id}**")

    # 🔥 FIX: Define eraser_mode OUTSIDE the block so it is always accessible!
    eraser_mode = "Paint"  # Default value
    
    # Add the radio button
    with st.expander("🧹 Erase Mode"):
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
    def render_grid(current_brush, current_label, current_mode):
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
                        if current_mode == "Erase":
                            st.session_state.grid[cell_id] = 0
                            st.session_state.plot_types.pop(current_brush, None) 
                        else:
                            st.session_state.grid[cell_id] = current_brush
                            # 🔥 Store the type so it gets the right color!
                            st.session_state.plot_types[current_brush] = current_label
                        # 🔥 FIX: Rerun the WHOLE page so "Assign & Save" instantly updates!
                        st.rerun()

    render_grid(brush_id, plot_type_label, eraser_mode)
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

        # ── 📊 LIVE VISUAL PREVIEW & DATA SUMMARY ──
    st.divider()
    st.subheader(f"👁️ Live Visual Preview ({sec_name})")

    # Build the Preview Grid
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
                # Use the box count for color
                box_count = sum(1 for v in st.session_state.grid.values() if v == val)
                color = get_color_from_box_count(box_count)
                html += f'<div style="width: 25px; height: 25px; background: {color}; border: 1px solid white; color: white; font-size: 8px; display: flex; align-items: center; justify-content: center;">{val}</div>'
            else:
                html += '<div style="width: 25px; height: 25px; background: #2a2a2a; border: 1px dashed #555;"></div>'
        html += '</div>'
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)

    # ── 📊 1. SECTION DATA SUMMARY (Metrics) ──
    all_vals = list(st.session_state.grid.values())
    # 🔥 FIX: Use SET to guarantee NO repeats!
    unique_ids = sorted(list(set([v for v in all_vals if v > 0])))

    if unique_ids:
        total_boxes = sum(len([v for v in all_vals if v == pid]) for pid in unique_ids)
        total_area = total_boxes * 0.25  # 1 box = 0.25 m²
        
        st.markdown("#### 📊 Section Data Summary")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("📍 Total Plots", len(unique_ids))
        m2.metric("📦 Total Boxes (50x50cm)", total_boxes)
        m3.metric("📐 Total Area", f"{total_area:.2f} m²")
        m4.metric("📏 Average Plot Size", f"{total_area / len(unique_ids):.2f} m²")

        # ── 🎨 2. PLOT TYPE LEGEND ──
        st.markdown("#### 🎨 Plot Type Legend")
        st.markdown("""
        <div style="display: flex; flex-wrap: wrap; gap: 20px; margin-bottom: 10px; padding: 10px; background: #1e1e1e; border-radius: 8px;">
            <div style="display: flex; align-items: center; gap: 5px;"> <div style="width: 15px; height: 15px; background: #2ca02c; border-radius: 2px;"></div> <span>Type A (12 boxes) = 3.0 m²</span> </div>
            <div style="display: flex; align-items: center; gap: 5px;"> <div style="width: 15px; height: 15px; background: #ff7f0e; border-radius: 2px;"></div> <span>Type B (10 boxes) = 2.5 m²</span> </div>
            <div style="display: flex; align-items: center; gap: 5px;"> <div style="width: 15px; height: 15px; background: #1f77b4; border-radius: 2px;"></div> <span>Type C (8 boxes) = 2.0 m²</span> </div>
            <div style="display: flex; align-items: center; gap: 5px;"> <div style="width: 15px; height: 15px; background: #6f42c1; border-radius: 2px;"></div> <span>Custom (Any size)</span> </div>
        </div>
        """, unsafe_allow_html=True)

        # ── 📋 3. PLOT BREAKDOWN TABLE (NO REPEATS, AUTO-LABELS!) ──
        st.markdown("#### 📋 Plot Breakdown")
        st.caption("One row per unique Plot ID. Auto-classified by size.")

        # 🔥 HELPER: Auto-identify type based on box count
        def get_type_auto(box_count):
            if box_count == 12: return "Type A (12 boxes)"
            if box_count == 10: return "Type B (10 boxes)"
            if box_count == 8: return "Type C (8 boxes)"
            return "Custom Size"

        table_html = "<table style='width: 100%; border-collapse: collapse; color: white; font-size: 14px;'>"
        table_html += "<tr style='background: #333; text-align: left;'>"
        table_html += "<th style='padding: 8px; border: 1px solid #555;'>Plot ID</th>"
        table_html += "<th style='padding: 8px; border: 1px solid #555;'>Type</th>"
        table_html += "<th style='padding: 8px; border: 1px solid #555;'>Box Count</th>"
        table_html += "<th style='padding: 8px; border: 1px solid #555;'>Area (m²)</th>"
        table_html += "<th style='padding: 8px; border: 1px solid #555;'>Color</th>"
        table_html += "</tr>"

        for pid in unique_ids:
            box_count = len([v for v in all_vals if v == pid])
            area = box_count * 0.25
            
            # 🔥 FIX: Auto-classify the type based on size
            type_label = get_type_auto(box_count)
            
            # 🔥 FIX: Get color based on box count (so colors match the legend perfectly)
            color = get_color_from_box_count(box_count)
            
            # Add a row for this unique Plot ID
            table_html += "<tr style='text-align: center;'>"
            table_html += f"<td style='padding: 8px; border: 1px solid #555;'>{pid}</td>"
            table_html += f"<td style='padding: 8px; border: 1px solid #555;'>{type_label}</td>"
            table_html += f"<td style='padding: 8px; border: 1px solid #555;'>{box_count}</td>"
            table_html += f"<td style='padding: 8px; border: 1px solid #555;'>{area:.2f}</td>"
            table_html += f"<td style='padding: 8px; border: 1px solid #555;'><div style='width: 20px; height: 20px; background: {color}; border-radius: 2px; margin: 0 auto;'></div></td>"
            table_html += "</tr>"
            
        table_html += "</table>"
        
        st.html(table_html)
    else:
        st.info("Paint a plot to see the section data summary and breakdown.")


# ==========================================
# 🗺️ NEW MASTER MAP VIEW (Read-Only)
# ==========================================
def show_master_map_view():
    st.subheader("🗺️ Master Map View (Customizable Grid)")
    st.caption("Set the Row and Col for each section. The map will auto-arrange and display all sections in one unified view!")

    # Load all sections and their dimensions
    try:
        sections_data = supabase.table('section_settings').select('*').execute().data
        if not sections_data:
            st.info("No sections found. Create sections in 'Single Section View' first.")
            return
    except Exception as e:
        st.error(f"Error loading sections: {e}")
        return

    # --- Grid Configuration Panel ---
    st.markdown("### 📐 Grid Configuration")
    st.caption("Edit the Row and Col below. The map will update instantly.")

    # Load existing map_row/map_col (default to 0 if not set)
    config_data = []
    for sec in sections_data:
        row = sec.get('map_row', 0)
        col = sec.get('map_col', 0)
        config_data.append({
            'name': sec['section_name'],
            'rows': int(sec['rows']),
            'cols': int(sec['cols']),
            'map_row': int(row) if row else 0,
            'map_col': int(col) if col else 0
        })

    # Create a grid of number inputs
    for i, sec in enumerate(config_data):
        c1, c2, c3 = st.columns([3, 1, 1])
        with c1:
            st.write(f"**{sec['name']}** (Size: {sec['rows']} x {sec['cols']})")
        with c2:
            new_row = st.number_input("Row", min_value=0, max_value=10, value=sec['map_row'], key=f"map_row_{sec['name']}")
        with c3:
            new_col = st.number_input("Col", min_value=0, max_value=10, value=sec['map_col'], key=f"map_col_{sec['name']}")
        
        # Save changes if changed
        if new_row != sec['map_row'] or new_col != sec['map_col']:
            supabase.table('section_settings').update({'map_row': int(new_row), 'map_col': int(new_col)}).eq('section_name', sec['name']).execute()
            st.rerun()

    st.divider()

    # --- Build and Display Master Map ---
    st.markdown("### 🗺️ Combined Map Preview")

    # Find max rows/cols to build the canvas grid
    max_row = max((sec['map_row'] for sec in config_data), default=0)
    max_col = max((sec['map_col'] for sec in config_data), default=0)

    # Create a 2D list to hold sections
    master_grid = [[None for _ in range(max_col + 1)] for _ in range(max_row + 1)]
    for sec in config_data:
        master_grid[sec['map_row']][sec['map_col']] = sec

    # HTML canvas
    html = '<div style="overflow-x: auto; border: 2px solid #333; padding: 5px; border-radius: 8px; background: #1e1e1e; display: inline-block;">'

    # Top axis (Col numbers)
    html += '<div style="display: flex;"><div style="width: 30px;"></div>'
    for c in range(max_col + 1):
        html += f'<div style="width: 100px; font-size: 12px; color: #aaa; text-align: center; border-bottom: 1px solid #555; padding-bottom: 5px;">Col {c}</div>'
    html += '</div>'

    # Grid rows
    for r in range(max_row + 1):
        html += '<div style="display: flex; margin-bottom: 10px;">'
        # Row label
        html += f'<div style="width: 30px; font-size: 12px; color: #aaa; display: flex; align-items: center; justify-content: center; border-right: 1px solid #555; padding-right: 5px;">Row {r}</div>'
        
        for c in range(max_col + 1):
            sec = master_grid[r][c]
            if sec:
                # Load plots for this section
                plots_data = supabase.table('box_map_plots').select('*').eq('section_name', sec['name']).execute().data
                
                # Create a mini-grid for the section
                section_html = '<div style="border: 1px solid #444; margin: 2px; background: #1a1a1a;">'
                section_html += f'<div style="background: #667eea; color: white; font-weight: bold; text-align: center; padding: 4px; font-size: 14px;">{sec["name"]}</div>'
                
                # Create local grid dictionary
                local_grid = {f"{r}_{c}": 0 for r in range(sec['rows']) for c in range(sec['cols'])}
                for plot in plots_data:
                    cells = plot.get('cells')
                    if isinstance(cells, str): cells = json.loads(cells)
                    if cells:
                        for rr, cc in cells:
                            if rr < sec['rows'] and cc < sec['cols']:
                                local_grid[f"{rr}_{cc}"] = plot['plot_id']
                
                # Render section boxes
                for rr in range(sec['rows']):
                    section_html += '<div style="display: flex;">'
                    for cc in range(sec['cols']):
                        val = local_grid.get(f"{rr}_{cc}", 0)
                        if val > 0:
                            box_count = sum(1 for v in local_grid.values() if v == val)
                            color = get_color_from_box_count(box_count)
                            section_html += f'<div style="width: 15px; height: 15px; background: {color}; border: 1px solid #fff;"></div>'
                        else:
                            section_html += f'<div style="width: 15px; height: 15px; background: #2a2a2a; border: 1px dashed #555;"></div>'
                    section_html += '</div>'
                section_html += '</div>'
                
                html += f'<div style="width: fit-content;">{section_html}</div>'
            else:
                # Empty cell (for gaps / walkways)
                html += '<div style="width: 50px; height: 50px; border: 1px dashed #333; margin: 2px;"></div>'
        html += '</div>'
    
    html += '</div>'
    
    st.markdown(html, unsafe_allow_html=True)