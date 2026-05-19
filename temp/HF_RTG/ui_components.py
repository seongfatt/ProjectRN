# ui_components.py
import streamlit as st
import pandas as pd
from datetime import datetime
from config import PLOT_TYPES, TYPE_MAP, PHYSICAL_ORDER, PLOT_LAYOUTS, TOTAL_PLOTS
from data_manager import load_data, save_data

def render_legend():
    st.markdown("### 🎨 Plot Type Legend")
    cols = st.columns(4)
    for i, (type_key, type_info) in enumerate(PLOT_TYPES.items()):
        with cols[i]:
            st.markdown(
                f'<div style="background-color: {type_info["colour"]}; color: white; padding: 10px; border-radius: 8px; text-align: center; font-weight: bold; margin: 5px 0;">'
                f'<div style="font-size: 16px;">Type {type_key}</div>'
                f'<div style="font-size: 12px;">{type_info["area"]} m²</div>'
                f'</div>',
                unsafe_allow_html=True
            )

def render_plot_grid(df, selected_plot=None, user_id=None):
    """Render the garden plots grouped by Plot 1–8 with custom layout"""
    st.markdown("### 📍 All 76 Garden Plots")
    st.caption("✅ **Bright colors** = Available | ❌ **Faded/X** = Already taken | Owner shown below")

    COLS_PER_ROW = 10

    for plot_name, layout in PLOT_LAYOUTS.items():
        st.markdown(f"#### {plot_name}")
        
        # Render each row in this plot
        for row_idx, row in enumerate(layout):
            cols = st.columns(COLS_PER_ROW)
            for col_idx, plot_num in enumerate(row):
                if plot_num is None:
                    cols[col_idx].empty()
                    continue
                
                plot_data = df[df["Plot"] == plot_num].iloc[0]
                
                # Determine occupancy safely
                occupied_val = plot_data["Occupy"]
                occupied = False if pd.isna(occupied_val) else bool(occupied_val)
                owner = str(plot_data["User_ID"]) if pd.notna(plot_data["User_ID"]) else ""

                # Check if this is the current user's plot (case-insensitive)
                is_my_plot = False
                if user_id and pd.notna(plot_data["User_ID"]):
                    if str(plot_data["User_ID"]).strip().lower() == str(user_id).strip().lower():
                        is_my_plot = True

                # Get color and area
                plot_type = TYPE_MAP[plot_num]
                color = PLOT_TYPES[plot_type]["colour"]
                area = PLOT_TYPES[plot_type]["area"]

                # Check if selected
                is_selected = (selected_plot == plot_num)

                # Determine border style
                if is_my_plot:
                    border_color = "gold"
                    border_width = "3px"
                elif is_selected:
                    border_color = "#00FFFF"
                    border_width = "3px"
                else:
                    border_color = color
                    border_width = "2px"

                # Define disabled state
                disabled = occupied

                with cols[col_idx]:
                    # Interactive button
                    if st.button(
                        str(plot_num),
                        key=f"plot_{plot_num}",
                        use_container_width=True,
                        type="primary" if is_selected else "secondary",
                        disabled=disabled
                    ):
                        st.session_state.selected_plot = plot_num
                        st.rerun()

                    # Visual styling - DIFFERENT OPACITY FOR MY PLOT
                    x_mark = '<div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); font-size: 24px; color: white; font-weight: bold;">✗</div>' if occupied else ''
                    
                    # Apply different opacity based on ownership
                    if occupied:
                        if is_my_plot:
                            opacity = 0.8  # Slightly faded for my own plot
                        else:
                            opacity = 0.5  # More faded for others' plots
                    else:
                        opacity = 1.0  # Bright for available plots

                    st.markdown(f"""
                    <div style="
                        background-color: {color};
                        color: white;
                        border: {border_width} solid {border_color};
                        border-radius: 8px;
                        padding: 12px 0;
                        margin: 2px 0;
                        text-align: center;
                        font-weight: bold;
                        font-size: 16px;
                        opacity: {opacity};
                        position: relative;
                        pointer-events: none;
                        transition: opacity 0.3s ease;
                    ">
                        {plot_num}
                        {x_mark}
                    </div>
                    """, unsafe_allow_html=True)

                    # Label below button - DIFFERENT STYLING FOR MY PLOT
                    if occupied:
                        if is_my_plot:
                            # MY plot: BRIGHT and CLEAR
                            label_text = f"👤 {owner} (YOU)"
                            label_color = "#00FF00"  # Bright green
                            label_size = "12px"
                            font_weight = "bold"
                            background_color = "rgba(0, 100, 0, 0.3)"
                            border = "1px solid #00FF00"
                            padding = "2px 4px"
                            margin_top = "-4px"
                            opacity_label = "1.0"
                            text_shadow = "0 0 3px #00FF00"
                        else:
                            # Other people's plot: faded
                            label_text = f"👤 {owner}"
                            label_color = "#FFFFFFF"  # Light gray
                            label_size = "11px"
                            font_weight = "normal"
                            background_color = "rgba(100, 100, 100, 0.2)"
                            border = "none"
                            padding = "1px 3px"
                            margin_top = "-4px"
                            opacity_label = "1.0"
                            text_shadow = "none"
                        
                        st.markdown(
                            f'<div style="text-align:center;font-size:{label_size};color:{label_color};margin-top:{margin_top};height:18px;font-weight:{font_weight};opacity:{opacity_label};background:{background_color};padding:{padding};border:{border};border-radius:4px;text-shadow:{text_shadow};">{label_text}</div>',
                            unsafe_allow_html=True
                        )
                    else:
                        # Show "available" in gray, smaller font
                        label_text = "available"
                        label_color = "#888888"
                        label_size = "11px"
                        font_weight = "normal"
                        margin_top = "-4px"
                        opacity_label = "0.8"
                        
                        st.markdown(
                            f'<div style="text-align:center;font-size:{label_size};color:{label_color};margin-top:{margin_top};height:16px;font-weight:{font_weight};opacity:{opacity_label};">{label_text}</div>',
                            unsafe_allow_html=True
                        )

def render_admin_panel():
    if not st.session_state.get("is_admin", False):
        return

    st.markdown("---")
    st.markdown("## 👮 Admin Control Panel")
    
    if st.button("🚪 Logout Admin", type="secondary"):
        del st.session_state.is_admin
        st.rerun()

    df = load_data()
    
    st.subheader("📋 All Plot Assignments")
    display_df = df[df["Occupy"] == True][["Plot", "Type", "User_ID", "Change"]].copy()
    display_df = display_df.rename(columns={
        "Plot": "Plot #", "Type": "Type", "User_ID": "Owner", "Change": "Action Log"
    })
    st.dataframe(display_df, use_container_width=True, hide_index=True)
    
    st.subheader("🛠️ Release Any Plot")
    col1, col2 = st.columns(2)
    with col1:
        release_plot = st.number_input("Plot number to release", min_value=1, max_value=TOTAL_PLOTS, value=1, key="admin_release_plot")
    with col2:
        owner_info = df[df["Plot"] == release_plot]
        current_owner = owner_info["User_ID"].iloc[0] if not owner_info.empty and pd.notna(owner_info["User_ID"].iloc[0]) else "None"
        st.write(f"Current owner: **{current_owner}**")
    
    if st.button("🗑️ Force Release Plot", type="secondary"):
        if df.loc[df["Plot"] == release_plot, "Occupy"].iloc[0]:
            df.loc[df["Plot"] == release_plot, ["Occupy", "User_ID", "Change"]] = [
                False, pd.NA, f"Released by ADMIN - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            ]
            save_data(df)
            st.success(f"✅ Plot {release_plot} has been forcibly released!")
            st.rerun()
        else:
            st.info(f"ℹ️ Plot {release_plot} is already available.")
    
    st.markdown("---")
    if st.button("🚨 RESET ALL PLOTS (irreversible)", type="primary"):
        confirm = st.checkbox("I understand this will clear all assignments")
        if confirm:
            df["Occupy"] = False
            df["User_ID"] = pd.NA
            df["Change"] = f"FULL RESET by ADMIN - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            save_data(df)
            st.success("💥 All plots reset!")
            st.balloons()
            st.rerun()