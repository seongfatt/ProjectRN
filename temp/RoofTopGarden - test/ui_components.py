# ui_components.py - Updated for Supabase data structure
import streamlit as st
import pandas as pd
from config import PLOT_TYPES, TYPE_MAP, PLOT_LAYOUTS
from data_manager import mask_phone

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

def render_plot_grid(plots, selected_plot=None, user_id=None):
    """Render the garden plots grouped by Plot 1–8 with custom layout"""
    st.markdown("### 📍 All 76 Garden Plots")
    st.caption("✅ **Bright colors** = Available | ❌ **Faded/X** = Already taken | Owner shown below")

    # Convert list to dict for faster lookup
    plots_dict = {p['plot_number']: p for p in plots}
    
    COLS_PER_ROW = 10

    for plot_name, layout in PLOT_LAYOUTS.items():
        st.markdown(f"#### {plot_name}")
        
        for row in layout:
            cols = st.columns(COLS_PER_ROW)
            for col_idx, plot_num in enumerate(row):
                if plot_num is None:
                    cols[col_idx].empty()
                    continue
                
                # Get plot data from dict
                plot_data = plots_dict.get(plot_num, {
                    'occupied': False,
                    'user_id': None,
                    'user_name': None,
                    'plot_type': TYPE_MAP.get(plot_num, 'B')
                })
                
                occupied = plot_data.get('occupied', False)
                owner_id = plot_data.get('user_id') or ''
                owner_name = plot_data.get('user_name') or ''
                plot_type = plot_data.get('plot_type', TYPE_MAP.get(plot_num, 'B'))
                
                # Check if this is current user's plot
                is_my_plot = False
                if user_id and owner_id:
                    is_my_plot = str(owner_id).strip().lower() == str(user_id).strip().lower()

                color = PLOT_TYPES[plot_type]["colour"]
                is_selected = (selected_plot == plot_num)
                
                # Border style
                if is_my_plot:
                    border_color = "gold"
                    border_width = "3px"
                elif is_selected:
                    border_color = "#00FFFF"
                    border_width = "3px"
                else:
                    border_color = color
                    border_width = "2px"

                with cols[col_idx]:
                    # Button
                    if st.button(
                        str(plot_num),
                        key=f"plot_{plot_num}",
                        use_container_width=True,
                        type="primary" if is_selected else "secondary",
                        disabled=occupied
                    ):
                        st.session_state.selected_plot = plot_num
                        st.rerun()

                    # Visual styling
                    x_mark = '<div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); font-size: 24px; color: white; font-weight: bold;">✗</div>' if occupied else ''
                    
                    if occupied:
                        opacity = 0.8 if is_my_plot else 0.5
                    else:
                        opacity = 1.0

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
                    ">
                        {plot_num}
                        {x_mark}
                    </div>
                    """, unsafe_allow_html=True)

                    # Owner label - NOW SHOWS BOTH ID AND NAME
                    if occupied:
                        # Format: "ID: Name" or just "ID" if no name
                        display_id = str(owner_id)[:10]  # Limit ID length
                        display_name = str(owner_name)[:12] if owner_name else ""  # Limit name length
                        
                        if is_my_plot:
                            # MY plot styling
                            if display_name:
                                label_text = f"👤 YOU<br/><small>{display_id}: {display_name}</small>"
                            else:
                                label_text = f"👤 YOU<br/><small>{display_id}</small>"
                            label_color = "#00FF00"
                            bg = "rgba(0, 100, 0, 0.3)"
                            border = "1px solid #00FF00"
                        else:
                            # Other people's plot styling
                            if display_name:
                                label_text = f"👤 {display_id}<br/><small>{display_name}</small>"
                            else:
                                label_text = f"👤 {display_id}"
                            label_color = "#FFFFFF"
                            bg = "rgba(100, 100, 100, 0.2)"
                            border = "none"
                        
                        st.markdown(
                            f'<div style="text-align:center;font-size:10px;color:{label_color};margin-top:-4px;min-height:28px;line-height:1.2;background:{bg};padding:2px 3px;border:{border};border-radius:4px;overflow:hidden;">{label_text}</div>',
                            unsafe_allow_html=True
                        )
                    else:
                        st.markdown(
                            '<div style="text-align:center;font-size:11px;color:#888888;margin-top:-4px;height:16px;">available</div>',
                            unsafe_allow_html=True
                        )

# pdpa_compliance_ui.py - New file for PDPA-compliant occupant list rendering

def render_occupant_list(plots, is_admin=False):
    """Render PDPA-compliant occupant list with admin toggle for full phone numbers"""
    import pandas as pd
    from data_manager import mask_phone  # ✅ Only import mask_phone
    
    st.markdown("## 📋 Occupied Plots List")
    
    # Filter occupied plots (passed as parameter)
    occupied_plots = [p for p in plots if p.get('occupied', False)]
    
    if not occupied_plots:
        st.info("No plots are currently occupied.")
        return
    
    # Admin toggle for full phone visibility
    show_full_phone = False
    if is_admin:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.caption("🔒 PDPA Compliant View (Last 4 digits shown)")
        with col2:
            show_full_phone = st.toggle("Show Full Phone", value=False, help="Admin-only toggle (resets on refresh)")
    
    # Prepare display data
    display_data = []
    for plot in occupied_plots:
        phone = plot.get('contact', 'N/A')
        if show_full_phone and is_admin:
            masked_phone = phone if phone else "N/A"
        else:
            masked_phone = mask_phone(phone)
        
        display_data.append({
            "Plot #": plot['plot_number'],
            "Owner Name": plot.get('user_name', 'N/A'),
            "Phone": masked_phone,
            "Plot Type": plot['plot_type']
        })
    
    # Create DataFrame for display
    display_df = pd.DataFrame(display_data)
    
    # Display table
    st.dataframe(display_df, use_container_width=True, hide_index=True)
    
    # Download button (admin only)
    if is_admin:
        csv = display_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Full List (CSV)",
            data=csv,
            file_name="woodlands_zone6_occupants.csv",
            mime="text/csv",
            use_container_width=True
        )