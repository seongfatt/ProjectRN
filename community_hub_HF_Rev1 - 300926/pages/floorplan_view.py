import streamlit as st
from config import supabase, DB_CONNECTED

# ==========================================
# REAL FLOOR PLAN VIEW (Pre-Mapped Generator)
# ==========================================
def show_floorplan():
    st.header("🗺️ Real Rooftop Floor Plan")
    st.caption("Interactive Pre-Mapped Generator: Design, Resize, and View your actual garden layout.")

    if not DB_CONNECTED:
        st.error("Database not connected")
        return

    # ── LEFT SIDE PANEL: Live Design Controls ──
    with st.sidebar:
        st.subheader("🛠️ Design Controls")
        st.caption("Adjust dimensions to see the floor plan update instantly.")

        # Walkway control
        walkway_cm = st.slider("Walkway Gap (cm)", 50, 200, 100, step=50)
        st.divider()

        # Initialize sections in session state
        if 'floor_sections' not in st.session_state:
            # 🔥 FIX: Width (w) is the LONGER side, Height (h) is the SHORTER side
            st.session_state.floor_sections = [
                {'name': 'Section 1', 'w': 22, 'h': 17, 'color': '#2ca02c', 'occupied': True},  # 11m x 8.5m
                {'name': 'Section 2', 'w': 30, 'h': 17, 'color': '#ff7f0e', 'occupied': True},  # 15m x 8.5m
                {'name': 'Section 3', 'w': 22, 'h': 17, 'color': '#2ca02c', 'occupied': True},  # 11m x 8.5m
                {'name': 'Section 4', 'w': 32, 'h': 11, 'color': '#1f77b4', 'occupied': True},  # 16m x 5.5m
            ]

        st.markdown("**✏️ Edit Your Sections**")
        # Loop through existing sections to allow edits
        for idx, sec in enumerate(st.session_state.floor_sections):
            with st.expander(f"📐 {sec['name']}", expanded=False):
                # 🔥 NEW: Toggle Occupied / Empty
                occupied = st.toggle("Occupied", value=sec['occupied'], key=f"sec_occ_{idx}")
                st.session_state.floor_sections[idx]['occupied'] = occupied
                
                name = st.text_input("Section Name", sec['name'], key=f"sec_name_{idx}")
                w = st.slider("Width (Units)", 5, 40, sec['w'], key=f"sec_w_{idx}")
                h = st.slider("Height (Units)", 5, 40, sec['h'], key=f"sec_h_{idx}")
                
                # Update state in real-time
                st.session_state.floor_sections[idx]['name'] = name
                st.session_state.floor_sections[idx]['w'] = w
                st.session_state.floor_sections[idx]['h'] = h

        st.divider()
        st.markdown("**➕ Add Your Own Section**")
        # Add a new section based on user input
        with st.form("add_new_section"):
            new_name = st.text_input("Section Name", "Section 5")
            new_w = st.number_input("Width (Units)", min_value=1, max_value=100, value=22)
            new_h = st.number_input("Height (Units)", min_value=1, max_value=100, value=17)
            new_color = st.selectbox("Color", ["#2ca02c", "#ff7f0e", "#1f77b4", "#d62728"])
            submitted = st.form_submit_button("➕ Add Section to Map")
            if submitted:
                st.session_state.floor_sections.append({
                    'name': new_name, 
                    'w': int(new_w), 
                    'h': int(new_h), 
                    'color': new_color,
                    'occupied': True
                })
                st.rerun()

    # ── CALCULATE AREAS ──
    total_units = 0
    total_area = 0.0
    for sec in st.session_state.floor_sections:
        sec_units = sec['w'] * sec['h']
        sec_area = sec_units * 0.25
        total_units += sec_units
        total_area += sec_area

    # ── DISPLAY LIVE STATISTICS ──
    st.markdown("### 📊 Live Area Summary")
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Area", f"{total_area:.2f} m²")
    c2.metric("Total 50x50 Units", f"{total_units}")
    c3.metric("Walkway Gap", f"{walkway_cm} cm")

    st.divider()

    # ── VISUAL FLOOR PLAN (CSS/HTML) ──
    st.markdown("### 🧱 Actual Floor Plan Layout")
    st.caption("👆 Solid colors = Occupied. Dotted grid = Empty / Available space.")

    # Scale: 1 unit = 15 pixels
    scale = 15
    walkway_px = int(walkway_cm / 50 * scale)

    # Build the plots - 🔥 CRITICAL FIX: Single line strings with NO leading spaces!
    def build_plot(w, h, label, color, occupied):
        width_px = int(w * scale)
        height_px = int(h * scale)
        
        # 🔥 NEW: Apply Dotted Grid Logic if not occupied
        if occupied:
            background_style = f"background: {color};"
            border_style = "border: 2px solid white;"
            opacity_style = "opacity: 1.0;"
        else:
            # Dotted Grid Pattern for Empty/Unoccupied Plots
            background_style = "background-image: linear-gradient(to right, #555 1px, transparent 1px), linear-gradient(to bottom, #555 1px, transparent 1px); background-size: 15px 15px; background-color: #1a1a2e;"
            border_style = "border: 2px dashed #888;"
            opacity_style = "opacity: 0.9;"
        
        return (
            f'<div style="width:{width_px}px; height:{height_px}px; {background_style} '
            f'{border_style} border-radius: 8px; '
            f'display:flex; flex-direction:column; align-items:center; justify-content:center; '
            f'color:white; font-weight:bold; font-size:16px; box-shadow: 0 4px 10px rgba(0,0,0,0.3); {opacity_style}">'
            f'<div>{label}</div>'
            f'<div style="font-size:10px; font-weight:normal;">{w*0.5}m × {h*0.5}m</div>'
            f'<div style="font-size:10px; font-weight:normal;">({w*h*0.25:.2f} m²)</div>'
            f'</div>'
        )

    # Build the floor plan using Flexbox - Now dynamically loops through ALL sections!
    floor_plan_html = (
        '<div style="background-color: #1a1a2e; padding: 20px; border-radius: 12px; border: 1px solid #333; display: inline-block; width: 100%;">'
        
        # THE MAIN ROW (all sections with walkway gaps)
        '<div style="display: flex; gap: ' + str(walkway_px) + 'px; margin-bottom: ' + str(walkway_px) + 'px; align-items: flex-start;">'
    )

    # Loop through all sections
    for i, sec in enumerate(st.session_state.floor_sections):
        floor_plan_html += build_plot(sec['w'], sec['h'], sec['name'], sec['color'], sec['occupied'])
        # Add walkway between plots (not after the last one)
        if i < len(st.session_state.floor_sections) - 1:
            floor_plan_html += ('<div style="display:flex; flex-direction:column; justify-content:center; font-size:10px; color:#aaa;">WALKWAY<br>(' + str(walkway_cm) + 'cm)</div>')

    floor_plan_html += '</div>'

    # CONCRETE WALKWAY STRIP AT THE BOTTOM
    floor_plan_html += ('<div style="width: 100%; height: ' + str(walkway_px) + 'px; background: repeating-linear-gradient(45deg, #555, #555 10px, #444 10px, #444 20px); border-radius: 4px; margin-bottom: ' + str(walkway_px) + 'px; display:flex; align-items:center; justify-content:center; font-size:10px; color:#ddd;">CONCRETE WALKWAY</div>')

    # EMPTY ROOF SPACE (Dotted/Shaded)
    floor_plan_html += ('<div style="padding: 20px; border: 2px dashed #555; border-radius: 8px; background: repeating-linear-gradient(45deg, #222, #222 10px, #2a2a2a 10px, #2a2a2a 20px); text-align: center; color: #888; font-size: 12px;">'
        '▒▒ Dotted Shaded Zone: Empty Roof / Concrete Space ▒▒'
        '</div>')

    floor_plan_html += '</div>'
    
    # Render the HTML
    st.markdown(floor_plan_html, unsafe_allow_html=True)

    st.divider()
    st.caption(f"💡 Total Calculated Area: **{total_area:.2f} m²** | Total Units: **{total_units}** | Walkway: **{walkway_cm} cm**")