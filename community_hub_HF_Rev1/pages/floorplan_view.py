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

        # Plot Dimensions (50x50cm units)
        st.markdown("**Plot Dimensions (in units of 50x50cm)**")
        p1_w = st.slider("Plot 1 Width (Units)", 5, 30, 17)
        p1_h = st.slider("Plot 1 Height (Units)", 5, 40, 22)

        p2_w = st.slider("Plot 2 Width (Units)", 5, 30, 17)
        p2_h = st.slider("Plot 2 Height (Units)", 5, 40, 30)

        p3_w = st.slider("Plot 3 Width (Units)", 5, 30, 17)
        p3_h = st.slider("Plot 3 Height (Units)", 5, 40, 22)

        p4_w = st.slider("Plot 4 Width (Units)", 5, 30, 11)
        p4_h = st.slider("Plot 4 Height (Units)", 5, 40, 32)

    # ── CALCULATE AREAS ──
    # A 50x50 unit is 0.25 m²
    area1 = p1_w * p1_h * 0.25
    area2 = p2_w * p2_h * 0.25
    area3 = p3_w * p3_h * 0.25
    area4 = p4_w * p4_h * 0.25
    
    total_units = (p1_w * p1_h) + (p2_w * p2_h) + (p3_w * p3_h) + (p4_w * p4_h)
    total_area = area1 + area2 + area3 + area4

    # ── DISPLAY LIVE STATISTICS ──
    st.markdown("### 📊 Live Area Summary")
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Area", f"{total_area:.2f} m²")
    c2.metric("Total 50x50 Units", f"{total_units}")
    c3.metric("Walkway Gap", f"{walkway_cm} cm")

    st.divider()

    # ── VISUAL FLOOR PLAN (CSS/HTML) ──
    st.markdown("### 🧱 Actual Floor Plan Layout")
    st.caption("👆 Dotted shading indicates empty concrete/unused roof space. Walkways are shown as gaps.")

    # Scale: 1 unit = 15 pixels
    scale = 15
    walkway_px = int(walkway_cm / 50 * scale)  # Convert cm to unit to px

    # Build the plots - 🔥 CRITICAL FIX: Single line strings with NO leading spaces!
    def build_plot(w, h, label, color):
        width_px = int(w * scale)
        height_px = int(h * scale)
        # Using string concatenation to avoid any newlines or spaces at the start
        return (
            f'<div style="width:{width_px}px; height:{height_px}px; background:{color}; '
            f'border: 2px solid white; border-radius: 8px; '
            f'display:flex; flex-direction:column; align-items:center; justify-content:center; '
            f'color:white; font-weight:bold; font-size:16px; box-shadow: 0 4px 10px rgba(0,0,0,0.3);">'
            f'<div>Plot {label}</div>'
            f'<div style="font-size:10px; font-weight:normal;">{w*0.5}m × {h*0.5}m</div>'
            f'<div style="font-size:10px; font-weight:normal;">({w*h*0.25:.2f} m²)</div>'
            f'</div>'
        )

    # Build the floor plan using Flexbox - 🔥 CRITICAL FIX: Starts immediately with <div>!
    floor_plan_html = (
        '<div style="background-color: #1a1a2e; padding: 20px; border-radius: 12px; border: 1px solid #333; display: inline-block;">'
        '<div style="display: flex; gap: ' + str(walkway_px) + 'px; margin-bottom: ' + str(walkway_px) + 'px; align-items: flex-start;">' +
        build_plot(p1_w, p1_h, "1", "#2ca02c") +
        '<div style="display:flex; flex-direction:column; justify-content:center; font-size:10px; color:#aaa;">WALKWAY<br>(' + str(walkway_cm) + 'cm)</div>' +
        build_plot(p2_w, p2_h, "2", "#ff7f0e") +
        '</div>' +
        '<div style="width: 100%; height: ' + str(walkway_px) + 'px; background: repeating-linear-gradient(45deg, #555, #555 10px, #444 10px, #444 20px); border-radius: 4px; margin-bottom: ' + str(walkway_px) + 'px; display:flex; align-items:center; justify-content:center; font-size:10px; color:#ddd;">CONCRETE WALKWAY</div>' +
        '<div style="display: flex; gap: ' + str(walkway_px) + 'px; align-items: flex-start;">' +
        build_plot(p3_w, p3_h, "3", "#2ca02c") +
        '<div style="display:flex; flex-direction:column; justify-content:center; font-size:10px; color:#aaa;">WALKWAY<br>(' + str(walkway_cm) + 'cm)</div>' +
        build_plot(p4_w, p4_h, "4", "#1f77b4") +
        '</div>' +
        '<div style="margin-top: ' + str(walkway_px) + 'px; padding: 20px; border: 2px dashed #555; border-radius: 8px; background: repeating-linear-gradient(45deg, #222, #222 10px, #2a2a2a 10px, #2a2a2a 20px); text-align: center; color: #888; font-size: 12px;">' +
        '▒▒ Dotted Shaded Zone: Empty Roof / Concrete Space ▒▒' +
        '</div>' +
        '</div>'
    )
    
    # Render the HTML
    st.markdown(floor_plan_html, unsafe_allow_html=True)

    st.divider()
    st.caption(f"💡 Total Calculated Area: **{total_area:.2f} m²** | Total Units: **{total_units}** | Walkway: **{walkway_cm} cm**")