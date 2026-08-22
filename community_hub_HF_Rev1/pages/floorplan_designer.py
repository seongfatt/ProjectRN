import streamlit as st
from config import supabase, DB_CONNECTED
from utils import find_participant_by_phone, clean_phone_number

def show_floorplan_designer():
    st.header("🎨 Box-Map Designer")
    st.caption("Draw plots on a 50x50cm grid, assign residents, and save to Supabase.")

    if not DB_CONNECTED:
        st.error("Database not connected")
        return

    # --- Initialize Session State ---
    if 'canvas' not in st.session_state:
        st.session_state.canvas = {}
    if 'canvas_loaded' not in st.session_state:
        st.session_state.canvas_loaded = False
    if 'canvas_meta' not in st.session_state:
        st.session_state.canvas_meta = {"name": "Section 1", "rows": 22, "cols": 17}
    if 'next_plot_id' not in st.session_state:
        st.session_state.next_plot_id = 1

    # --- Load Saved Data from Supabase (Only once) ---
    if not st.session_state.canvas_loaded:
        try:
            data = supabase.table('box_map_plots').select('*').execute().data
            for row in data:
                if row['section_name'] == st.session_state.canvas_meta["name"]:
                    pid = row['plot_id']
                    for r in range(row['start_row'], row['start_row'] + row['height']):
                        for c in range(row['start_col'], row['start_col'] + row['width']):
                            st.session_state.canvas[f"{r}_{c}"] = pid
                    if pid >= st.session_state.next_plot_id:
                        st.session_state.next_plot_id = pid + 1
            st.session_state.canvas_loaded = True
        except Exception as e:
            st.warning(f"Could not load saved plots: {e}")
            st.session_state.canvas_loaded = True

    # --- Sidebar: Controls ---
    with st.sidebar:
        st.subheader("🛠️ Canvas Settings")
        sec_name = st.text_input("Section Name", value=st.session_state.canvas_meta["name"])
        rows = int(st.number_input("Rows (Height Units)", min_value=1, max_value=50, value=st.session_state.canvas_meta["rows"]))
        cols = int(st.number_input("Cols (Width Units)", min_value=1, max_value=50, value=st.session_state.canvas_meta["cols"]))

        # 🔥 FIX: Only reset if user clicks this button, NOT automatically!
        if st.button("🗑️ Start New Section (Clear Canvas)", use_container_width=True):
            st.session_state.canvas_meta = {"name": sec_name, "rows": rows, "cols": cols}
            st.session_state.canvas = {}
            st.session_state.next_plot_id = 1
            st.session_state.canvas_loaded = False
            st.rerun()

        st.divider()
        st.subheader("🖌️ Painting Tools")
        brush_size = st.selectbox("Select Brush", ["12 boxes (3x4)", "10 boxes (2x5)", "8 boxes (2x4)", "Custom", "Eraser"], index=0)
        
        brush_w, brush_h = 0, 0
        if brush_size == "12 boxes (3x4)": brush_w, brush_h = 4, 3
        elif brush_size == "10 boxes (2x5)": brush_w, brush_h = 5, 2
        elif brush_size == "8 boxes (2x4)": brush_w, brush_h = 4, 2
        elif brush_size == "Custom":
            brush_w = int(st.number_input("Custom Width", min_value=1, max_value=20, value=4))
            brush_h = int(st.number_input("Custom Height", min_value=1, max_value=20, value=3))
        else:
            brush_w, brush_h = 1, 1

        start_r = int(st.number_input("Start Row", min_value=0, max_value=rows-1, value=0))
        start_c = int(st.number_input("Start Col", min_value=0, max_value=cols-1, value=0))
        
        # 🔥 FIX: Removed st.rerun() inside the button to prevent state wipe!
        if st.button("🖌️ Paint Plot", type="primary", use_container_width=True):
            painted = False
            for r in range(brush_h):
                for c in range(brush_w):
                    rr, cc = start_r + r, start_c + c
                    if 0 <= rr < rows and 0 <= cc < cols:
                        if brush_size == "Eraser":
                            st.session_state.canvas[f"{rr}_{cc}"] = None
                        else:
                            st.session_state.canvas[f"{rr}_{cc}"] = st.session_state.next_plot_id
                        painted = True
            
            if painted:
                if brush_size != "Eraser":
                    # Show which plot ID was just painted
                    st.success(f"✅ Plot {st.session_state.next_plot_id} painted successfully!")
                    st.session_state.next_plot_id += 1
                else:
                    st.success("✅ Eraser used successfully!")
            else:
                st.warning("⚠️ Coordinates are out of bounds. Please check your Start Row/Col.")

        st.divider()
        
        # ... (Rest of the assignment and saving logic remains exactly as before) ...
        st.subheader("📋 Plot Assignment & Saving")
        current_ids = sorted(list(set(v for v in st.session_state.canvas.values() if v)))
        
        if not current_ids:
            st.caption("Paint a plot first to assign it.")
        else:
            selected_id = st.selectbox("Select Plot ID", current_ids, key="assign_plot_id")
            coords = [(int(k.split('_')[0]), int(k.split('_')[1])) for k, v in st.session_state.canvas.items() if v == selected_id]
            
            if coords:
                min_r = min(c[0] for c in coords)
                min_c = min(c[1] for c in coords)
                max_r = max(c[0] for c in coords)
                max_c = max(c[1] for c in coords)
                width = max_c - min_c + 1
                height = max_r - min_r + 1
                box_count = len(coords)
                
                st.caption(f"**Plot {selected_id}:** {width} x {height} units ({box_count} boxes)")
                
                phone_input = st.text_input("Owner Phone Number", placeholder="e.g., 91234567", key=f"owner_phone_{selected_id}")
                owner_name = ""
                if phone_input and len(clean_phone_number(phone_input)) >= 8:
                    res = find_participant_by_phone(clean_phone_number(phone_input))
                    if res:
                        owner_name = res['name']
                        st.success(f"Found: **{owner_name}**")
                
                owner_name = st.text_input("Or Type Owner Name", value=owner_name, key=f"owner_name_{selected_id}")
                status = st.radio("Status", ["Paid", "Unpaid", "Empty"], horizontal=True, key=f"status_{selected_id}")
                
                if st.button("💾 Save Plot to Database", use_container_width=True, key=f"save_plot_{selected_id}"):
                    try:
                        supabase.table('box_map_plots').delete().eq('section_name', sec_name).eq('plot_id', selected_id).execute()
                        supabase.table('box_map_plots').insert({
                            "section_name": sec_name,
                            "plot_id": selected_id,
                            "start_row": min_r,
                            "start_col": min_c,
                            "width": width,
                            "height": height,
                            "box_count": box_count,
                            "owner_id": "PENDING" if not phone_input else clean_phone_number(phone_input),
                            "owner_name": owner_name,
                            "status": status
                        }).execute()
                        st.success(f"✅ Plot {selected_id} saved successfully!")
                        st.session_state.canvas_loaded = False
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error saving: {e}")

    # --- Render Grid ---
    st.markdown(f"### {sec_name} ({rows} rows x {cols} cols)")
    st.caption("Dotted lines = empty boxes. Colored blocks = Plots. Use sidebar to assign residents.")

    html = '<div style="overflow-x: auto; border: 2px solid #333; padding: 5px; border-radius: 8px; background: #1e1e1e; display: inline-block;">'
    
    for r in range(rows):
        html += '<div style="display: flex;">'
        for c in range(cols):
            plot_id = st.session_state.canvas.get(f"{r}_{c}", None)
            if plot_id:
                html += f'<div style="width: 25px; height: 25px; background: #888; border: 1px solid white; color: white; font-size: 8px; display: flex; align-items: center; justify-content: center;">{plot_id}</div>'
            else:
                html += f'<div style="width: 25px; height: 25px; background: #2a2a2a; border: 1px dashed #555;"></div>'
        html += '</div>'
    html += '</div>'

    st.markdown(html, unsafe_allow_html=True)

    total_painted = len([v for v in st.session_state.canvas.values() if v])
    total_boxes = rows * cols
    c1, c2 = st.columns(2)
    c1.metric("Total Boxes Painted", total_painted)
    c2.metric("Total Empty Boxes", total_boxes - total_painted)