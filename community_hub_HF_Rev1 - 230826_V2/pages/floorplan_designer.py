import streamlit as st
import pandas as pd
from config import supabase, DB_CONNECTED
from utils import find_participant_by_phone, clean_phone_number

# Define Plot Types with their exact Box dimensions (Width x Height in units of 50cm)
PLOT_TYPES_CONFIG = {
    "A (12 boxes / 3.0 m²)": {"w": 4, "h": 3, "boxes": 12},
    "B (10 boxes / 2.5 m²)": {"w": 5, "h": 2, "boxes": 10},
    "C (8 boxes / 2.0 m²)": {"w": 4, "h": 2, "boxes": 8},
}

def show_floorplan_designer():
    st.header("🎨 Box-Map Designer (Auto-Generate Plot IDs)")
    st.caption("Select a Type (A/B/C) and click Paint. The system automatically assigns the next Plot ID (1, 2, 3...).")

    if not DB_CONNECTED:
        st.error("Database not connected")
        return

    # --- Controls ---
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        sec_name = st.text_input("Section Name", value="Section 1")
    with c2:
        rows = int(st.number_input("Rows", min_value=1, max_value=100, value=22))
    with c3:
        cols = int(st.number_input("Cols", min_value=1, max_value=100, value=17))
    with c4:
        if st.button("🔄 Reset Canvas", width='stretch'):
            st.session_state.grid_df = pd.DataFrame(0, index=range(rows), columns=[f"Col {i}" for i in range(cols)])
            st.rerun()

    # 🔥 DYNAMIC MAX PLOT ID: Based on the total grid size!
    max_plot_id = rows * cols

    # Initialize DataFrame
    if 'grid_df' not in st.session_state or st.session_state.grid_df.shape != (rows, cols):
        st.session_state.grid_df = pd.DataFrame(0, index=range(rows), columns=[f"Col {i}" for i in range(cols)])

    # Load Existing Data from DB
    if 'loaded_sec' not in st.session_state or st.session_state.get('loaded_sec') != sec_name:
        try:
            st.session_state.grid_df = pd.DataFrame(0, index=range(rows), columns=[f"Col {i}" for i in range(cols)])
            data = supabase.table('box_map_plots').select('*').eq('section_name', sec_name).execute().data
            for row in data:
                for r in range(row['start_row'], row['start_row'] + row['height']):
                    for c in range(row['start_col'], row['start_col'] + row['width']):
                        if r < rows and c < cols:
                            st.session_state.grid_df.iloc[r, c] = row['plot_id']
            st.session_state.loaded_sec = sec_name
        except:
            pass

    st.divider()

    # --- 🔥 QUICK PAINT (Auto-Plot & Auto-ID) ---
    st.subheader("⚡ Quick Paint (Auto-Generate Plot ID)")

    # 🔥 Calculate the next available Plot ID automatically!
    existing_ids = set(st.session_state.grid_df.values.flatten().tolist())
    existing_ids.discard(0)
    if not existing_ids:
        next_id = 1
    else:
        next_id = max(existing_ids) + 1

    qp1, qp2, qp3, qp4 = st.columns(4)
    with qp1:
        start_row = st.number_input("Start Row", min_value=0, max_value=rows-1, value=0)
    with qp2:
        start_col = st.number_input("Start Col", min_value=0, max_value=cols-1, value=0)
    with qp3:
        # Select Plot Type (including Custom Size)
        plot_type_label = st.selectbox("Select Plot Type", list(PLOT_TYPES_CONFIG.keys()) + ["Custom Size"])
        
        if plot_type_label == "Custom Size":
            cw = st.number_input("Custom Width (Boxes)", min_value=1, max_value=20, value=4)
            ch = st.number_input("Custom Height (Boxes)", min_value=1, max_value=20, value=3)
            plot_type = {"w": int(cw), "h": int(ch), "boxes": int(cw * ch)}
            st.caption(f"Custom Size: {plot_type['w']} wide x {plot_type['h']} high ({plot_type['boxes']} boxes)")
        else:
            plot_type = PLOT_TYPES_CONFIG[plot_type_label]
            st.caption(f"Auto-detect: {plot_type['w']} wide x {plot_type['h']} high")
    with qp4:
        # 🔥 NOTE: We removed the manual Plot ID input!
        st.success(f"🔥 Next Plot ID: **{next_id}**")
        st.caption(f"Max allowed: {max_plot_id}")

    # Paint Button
    if st.button("🖌️ Paint Auto-Plot (ID " + str(next_id) + ")", type="primary", width='stretch'):
        end_row = int(start_row) + plot_type['h'] - 1
        end_col = int(start_col) + plot_type['w'] - 1
        
        if end_row < rows and end_col < cols:
            for r in range(int(start_row), end_row + 1):
                for c in range(int(start_col), end_col + 1):
                    st.session_state.grid_df.iloc[r, c] = next_id
            st.rerun()
        else:
            st.error(f"❌ Invalid coordinate! The block needs {plot_type['h']} rows and {plot_type['w']} cols. It doesn't fit here.")

    st.divider()

    # --- GRID (Dropdowns + Fixed Axis) ---
    st.subheader("🗺️ Step 1: Fine-Tune Grid (Dropdowns)")
    # 🔥 DYNAMIC OPTIONS: 0 to max_plot_id
    options_list = list(range(0, max_plot_id + 1))

    edited_df = st.data_editor(
        st.session_state.grid_df,
        use_container_width=True,
        key="map_editor",
        height=500,
        hide_index=False, 
        column_config={
            col: st.column_config.SelectboxColumn(
                label=col,
                help="Pick a Plot ID or 0 for Empty",
                width="small",
                options=options_list,
                required=True
            )
            for col in st.session_state.grid_df.columns
        }
    )

    edited_df = edited_df.fillna(0)
    st.session_state.grid_df = edited_df

    st.divider()

    # --- Assign & Save ---
    st.subheader("📋 Step 2: Assign Owner & Save")
    unique_ids = sorted([int(v) for v in edited_df.values.flatten() if v > 0])

    if not unique_ids:
        st.info("Paint a plot first.")
    else:
        a1, a2, a3, a4 = st.columns(4)
        with a1:
            selected_id = st.selectbox("Select Plot ID to Save", unique_ids)
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
                st.caption(f"**Plot {selected_id}:** {width} x {height} units ({box_count} boxes)")

        with a2:
            phone_input = st.text_input("Owner Phone Number", placeholder="e.g., 91234567")
            owner_name = ""
            if phone_input and len(clean_phone_number(phone_input)) >= 8:
                res = find_participant_by_phone(clean_phone_number(phone_input))
                if res:
                    owner_name = res['name']
                    st.success(f"Found: **{owner_name}**")
            owner_name = st.text_input("Or Type Owner Name", value=owner_name)
            status = st.radio("Status", ["Paid", "Unpaid", "Empty"], horizontal=True)

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

        # --- Step 3: The Beautiful Color Map ---
    st.divider()
    st.subheader(f"🗺️ Step 3: Visual Map Preview ({sec_name})")

    # 🔥 RESTORED: Build the HTML with Axis Labels (Fixed alignment)
    html = '<div style="overflow-x: auto; border: 2px solid #333; padding: 5px; border-radius: 8px; background: #1e1e1e; display: inline-block;">'

    # Header Row (Column Numbers)
    # 🔥 FIX: Removed "margin-left: 30px" - only use the 30px spacer to match the grid!
    html += '<div style="display: flex;">'
    html += '<div style="width: 30px;"></div>'  # Spacer for the row numbers
    for c in range(cols):
        html += f'<div style="width: 25px; font-size: 10px; color: #aaa; text-align: center;">{c}</div>'
    html += '</div>'

    # Grid Rows
    for r in range(rows):
        html += '<div style="display: flex;">'
        # Row Number on the left
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