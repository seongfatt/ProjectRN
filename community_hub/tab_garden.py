import streamlit as st
from datetime import datetime
import tempfile
import os
from config import supabase, PLOT_TYPES, TOTAL_PLOTS, TYPE_MAP, DB_CONNECTED
from utils import mask_phone, get_plot, update_plot, get_user_plot, create_request, get_pending_requests, update_request_status, get_occupied_count, load_plots
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch

PLOT_LAYOUTS = {
    "Plot 1": [[2,3,7,8,None,None,None,None,None,None],[None,None,6,None,None,None,None,None,None,None],[1,4,5,9,None,None,None,None,None,None],[None,None,None,None,None,None,None,None,None,None]],
    "Plot 2": [[11,12,16,17,20,None,None,None,None,None],[None,None,15,None,None,None,None,None,None,None],[10,13,14,18,19,None,None,None,None,None],[None,None,None,None,None,None,None,None,None,None]],
    "Plot 3": [[21,24,25,29,None,None,None,None,None,None],[None,None,26,None,None,None,None,None,None,None],[22,23,27,28,None,None,None,None,None,None],[None,None,None,None,None,None,None,None,None,None]],
    "Plot 4": [[None,32,None,None,35,38,None,None,None,None],[30,None,33,34,None,None,None,None,None,None],[None,31,None,None,36,37,None,None,None]],
    "Plot 5": [[40,41,45,46,None,None,None,None,None,None],[None,None,44,None,None,None,None,None,None,None],[39,42,43,47,None,None,None,None,None,None],[None,None,None,None,None,None,None,None,None,None]],
    "Plot 6": [[49,50,54,55,58,None,None,None,None,None],[None,None,53,None,None,None,None,None,None,None],[48,51,52,56,57,None,None,None,None,None],[None,None,None,None,None,None,None,None,None,None]],
    "Plot 7": [[59,63,64,67,None,None,None,None,None,None],[None,62,None,None,None,None,None,None,None,None],[60,61,65,66,None,None,None,None,None,None],[None,None,None,None,None,None,None,None,None,None]],
    "Plot 8": [[None,70,None,None,73,76,None,None,None,None],[68,None,71,72,None,None,None,None,None,None],[None,69,None,None,74,75,None,None,None,None]],
}

def create_garden_plot_image(plots_data):
    """Generate garden layout image matching PLOT_LAYOUTS structure with correct occupied/available indicators."""
    fig, ax = plt.subplots(1, 1, figsize=(20, 26))
    fig.patch.set_facecolor('#f8f9fa')
    ax.set_facecolor('#f8f9fa')

    ax.text(0.5, 0.99, 'Woodlands Zone 6 - Roof Top Garden Layout',
            transform=ax.transAxes, fontsize=28, fontweight='bold',
            ha='center', va='top', color='#1a1a2e')
    ax.text(0.5, 0.985, 'All 76 Garden Plots - Type, Size & Availability',
            transform=ax.transAxes, fontsize=14, ha='center', va='top', color='#666')

    plots_dict = {p['plot_number']: p for p in plots_data}

    # Use PLOT_LAYOUTS to render sections exactly as defined
    y_pos = 0.96
    section_names = list(PLOT_LAYOUTS.keys())

    for section_name in section_names:
        layout = PLOT_LAYOUTS[section_name]
        ax.text(0.02, y_pos, section_name, transform=ax.transAxes,
                fontsize=13, fontweight='bold', color='#333')
        y_pos -= 0.012

        # Calculate grid dimensions
        rows = len(layout)
        max_cols = max(len(row) for row in layout) if layout else 10

        box_w = 0.072
        box_h = 0.016
        gap_x = 0.005
        gap_y = 0.003
        x_start = 0.02

        for row_idx, row in enumerate(layout):
            for col_idx, pn in enumerate(row):
                if pn is None:
                    continue

                ptype = TYPE_MAP.get(pn, 'B')
                color = PLOT_TYPES[ptype]["colour"]
                plot = plots_dict.get(pn)
                occ = plot.get('occupied', False) if plot else False

                # Occupied = darker/muted, Available = bright
                alpha = 0.35 if occ else 0.95
                edge = '#333333' if occ else '#ffffff'
                lw = 2.5 if occ else 1.0
                text_color = '#ffffff' if not occ else '#eeeeee'
                weight = 'bold' if not occ else 'normal'

                x = x_start + col_idx * (box_w + gap_x)
                y = y_pos - row_idx * (box_h + gap_y)

                rect = FancyBboxPatch((x, y), box_w, box_h,
                                      boxstyle="round,pad=0.003",
                                      facecolor=color, edgecolor=edge, linewidth=lw,
                                      transform=ax.transAxes, alpha=alpha)
                ax.add_patch(rect)

                # Plot number
                ax.text(x + box_w/2, y + box_h/2, str(pn),
                       transform=ax.transAxes, fontsize=7, fontweight=weight,
                       ha='center', va='center', color=text_color)

                # Occupied indicator (small X) - no name/contact for privacy
                if occ:
                    ax.text(x + box_w - 0.004, y + box_h - 0.002, 'X',
                           transform=ax.transAxes, fontsize=6, color='#ff4444',
                           ha='right', va='top', fontweight='bold')

        # Advance y_pos based on rows in this section
        y_pos -= (rows * (box_h + gap_y)) + 0.022

    # Legend
    legend_elements = []
    for tk, ti in PLOT_TYPES.items():
        legend_elements.append(mpatches.Patch(facecolor=ti['colour'], edgecolor='white',
                                              label=f'Type {tk} ({ti["area"]} m\u00B2) - {ti["total"]} plots'))
    legend_elements.append(mpatches.Patch(facecolor='#999999', edgecolor='#333', alpha=0.35,
                                          label='Darker = Occupied'))
    legend_elements.append(mpatches.Patch(facecolor='#ffffff', edgecolor='#333', alpha=0.95,
                                          label='Bright = Available'))

    ax.legend(handles=legend_elements, loc='lower center', bbox_to_anchor=(0.5, -0.01),
              ncol=3, fontsize=10, frameon=True, fancybox=True, shadow=True)

    occupied = sum(1 for p in plots_data if p.get('occupied'))
    available = 76 - occupied
    ax.text(0.98, 0.01, f'Total: 76 | Occupied: {occupied} | Available: {available}',
            transform=ax.transAxes, fontsize=11, ha='right', va='bottom',
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.9, edgecolor='#ccc'))

    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis('off')
    plt.tight_layout()
    return fig


def show_garden():
    st.header("Roof Top Garden")

    if not DB_CONNECTED:
        st.error("Database not connected"); return

    plots = load_plots()
    occupied = get_occupied_count()
    pct = occupied / TOTAL_PLOTS

    st.progress(pct)
    st.subheader(f"{occupied} / {TOTAL_PLOTS} occupied ({pct:.1%})")

    # Type legend at top
    cols = st.columns(4)
    for i, (tk, ti) in enumerate(PLOT_TYPES.items()):
        with cols[i]:
            st.markdown(f'<div style="background:{ti["colour"]};color:white;padding:8px;border-radius:6px;text-align:center;font-weight:bold;font-size:12px;">Type {tk}<br/>{ti["area"]} m\u00B2</div>', unsafe_allow_html=True)
    st.markdown("---")

    st.markdown("## Your Account")
    user_id = st.text_input("Your User ID", value=st.session_state.get('user_id', ''), placeholder="Enter nickname/ID", key="garden_user_id")
    if user_id:
        st.session_state.user_id = user_id.strip()
        user_plot = get_user_plot(user_id)
        if user_plot:
            st.success(f"You have Plot {user_plot['plot_number']} (Type {user_plot['plot_type']})")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Release My Plot", type="secondary", use_container_width=True):
                    if update_plot(user_plot['plot_number'], {'occupied': False, 'user_id': None, 'user_name': None, 'contact': None, 'change_log': f"Released by {user_id}"}):
                        st.success("Released!"); st.rerun()
            with c2:
                if st.button("Refresh", use_container_width=True):
                    st.rerun()

    st.markdown("### All 76 Garden Plots")
    st.caption("Bright = Available | Faded/Dark with X = Occupied")

    plots_dict = {p['plot_number']: p for p in plots}

    # Render each section using PLOT_LAYOUTS exactly with COLORS
    for plot_name, layout in PLOT_LAYOUTS.items():
        st.markdown(f"#### {plot_name}")
        for row in layout:
            # Count actual plots in this row to determine columns
            actual_plots = [pn for pn in row if pn is not None]
            if not actual_plots:
                continue

            # Use 10 columns max, but only render for actual plot positions
            cols = st.columns(10)
            for ci, pn in enumerate(row):
                if pn is None:
                    cols[ci].empty()
                    continue

                pd = plots_dict.get(pn, {'occupied': False, 'user_id': None, 'user_name': None, 'plot_type': TYPE_MAP.get(pn, 'B')})
                occ = pd.get('occupied', False)
                owner = pd.get('user_id', '')
                ptype = pd.get('plot_type', TYPE_MAP.get(pn, 'B'))
                is_my = user_id and owner and str(owner).strip().lower() == str(user_id).strip().lower()
                color = PLOT_TYPES[ptype]["colour"]
                sel = (st.session_state.get('selected_plot') == pn)

                with cols[ci]:
                    # Calculate opacity: occupied = dimmed, available = bright
                    opacity = 0.4 if occ else 1.0

                    # Border: gold for selected, white for normal
                    border_color = "#FFD700" if sel else "#ffffff"
                    border_width = "3px" if sel else "1px"

                    # Determine if button should be disabled
                    btn_disabled = occ and not is_my

                    # Use HTML div with actual color instead of Streamlit button for color display
                    # But keep button functionality for available plots
                    if occ:
                        # Occupied plot - show as colored div with X, not clickable (except own)
                        if is_my:
                            # My plot - clickable to release
                            if st.button(str(pn), key=f"gplot_{pn}", use_container_width=True, type="secondary"):
                                st.session_state.selected_plot = pn
                                st.rerun()
                            st.markdown(
                                f'<div style="background:{color};opacity:0.6;border:2px solid #00FF00;border-radius:6px;padding:6px 0;margin:2px 0;text-align:center;font-weight:bold;font-size:14px;color:white;">{pn}</div>'
                                '<div style="text-align:center;font-size:10px;color:#00FF00;margin-top:-2px;font-weight:bold;">YOU</div>',
                                unsafe_allow_html=True
                            )
                        else:
                            # 🔥 PHASE 3: Check Renewal Status for visual warning
                            renewal_date_str = pd.get('renewal_due_date')
                            is_due_soon = False
                            warning_icon = "X"
                            border_style = "1px solid #666"
                            
                            if renewal_date_str:
                                try:
                                    # Parse the date safely
                                    renewal_date = datetime.strptime(renewal_date_str[:10], "%Y-%m-%d").date()
                                    days_left = (renewal_date - datetime.now().date()).days
                                    
                                    # If due within 30 days, show warning
                                    if 0 <= days_left <= 30:
                                        is_due_soon = True
                                        border_style = "3px solid #ff4444"  # Thicker red border
                                        warning_icon = "⚠️"               # Warning emoji
                                except:
                                    pass
                            
                            # Other occupied - not clickable, just display
                            st.markdown(
                                f'<div style="background:{color};opacity:0.4;border:{border_style};border-radius:6px;padding:8px 0;margin:2px 0;text-align:center;font-weight:bold;font-size:14px;color:#ccc;">{pn}</div>'
                                f'<div style="text-align:center;font-size:14px;color:#ff4444;margin-top:-2px;font-weight:bold;">{warning_icon}</div>',
                                unsafe_allow_html=True
                            )
                    else:
                        # Available plot - clickable with full color
                        if st.button(str(pn), key=f"gplot_{pn}", use_container_width=True, type="secondary"):
                            st.session_state.selected_plot = pn
                            st.rerun()
                        st.markdown(
                            f'<div style="background:{color};border:{border_width} solid {border_color};border-radius:6px;padding:8px 0;margin:2px 0;text-align:center;font-weight:bold;font-size:14px;color:white;">{pn}</div>'
                            '<div style="text-align:center;font-size:10px;color:#888;margin-top:-2px;">available</div>',
                            unsafe_allow_html=True
                        )

    if st.session_state.get('selected_plot'):
        pn = st.session_state.selected_plot
        pd = get_plot(pn)
        if not pd or pd.get('occupied'):
            st.error(f"Plot {pn} not available"); st.session_state.selected_plot = None; st.rerun()
        else:
            ptype = TYPE_MAP[pn]
            area = PLOT_TYPES[ptype]["area"]
            color = PLOT_TYPES[ptype]["colour"]
            st.markdown(f'<div style="background:{color};color:white;padding:15px;border-radius:8px;text-align:center;margin:10px 0;"><div style="font-size:20px;font-weight:bold;">Plot {pn}</div><div>Type {ptype} ({area} m\u00B2)</div><div style="font-size:12px;margin-top:5px;">Available</div></div>', unsafe_allow_html=True)

            with st.form("plot_req", clear_on_submit=True):
                req_id = user_id or st.text_input("Your User ID:", key="req_uid")
                req_name = st.text_input("Full Name:", key="req_name")
                req_contact = st.text_input("Contact:", key="req_contact")
                req_notes = st.text_area("Notes:", key="req_notes")

                if st.form_submit_button("Submit Request", type="primary", use_container_width=True):
                    if req_id:
                        existing = get_user_plot(req_id)
                        if existing:
                            st.error(f"You already have Plot {existing['plot_number']}!")
                        else:
                            result = create_request(pn, req_id, req_name, req_contact, req_notes)
                            if result:
                                st.success(f"Request for Plot {pn} submitted!")
                                st.session_state.selected_plot = None
                                st.rerun()

    st.markdown("---")
    st.markdown("## Statistics")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total", TOTAL_PLOTS); c2.metric("Available", TOTAL_PLOTS - occupied)
    c3.metric("Occupied", occupied); c4.metric("Rate", f"{pct:.1%}")

    st.markdown("### By Type")
    tc = st.columns(4)
    for i, (tk, ti) in enumerate(PLOT_TYPES.items()):
        with tc[i]:
            to = len([p for p in plots if p['plot_type'] == tk and p['occupied']])
            pc = (to / ti["total"]) * 100 if ti["total"] > 0 else 0
            st.markdown(f'<div style="background:{ti["colour"]};color:white;padding:10px;border-radius:8px;text-align:center;"><div style="font-size:14px;font-weight:bold;">Type {tk}</div><div style="font-size:20px;margin:3px 0;">{to}/{ti["total"]}</div><div>{ti["area"]} m\u00B2</div><div>({pc:.1f}%)</div></div>', unsafe_allow_html=True)

    # ADMIN PANEL - No password needed (already logged in as admin)
    # Admin sees full details in the Requests/Direct tabs only
    st.divider()
    st.subheader("Admin Panel")
    st.caption("Manage garden plot requests and direct assignments")

    at1, at2 = st.tabs(["Requests", "Direct Assignment"])

    with at1:
        reqs = get_pending_requests()
        if reqs:
            st.write(f"**{len(reqs)} pending request(s)**")
            for req in reqs:
                with st.expander(f"#{req['id']}: Plot {req['plot_number']} - {req['user_id']}"):
                    c1, c2 = st.columns(2)
                    with c1:
                        st.write(f"**ID:** {req['user_id']}")
                        st.write(f"**Name:** {req.get('user_name', 'N/A')}")
                        st.write(f"**Contact:** {req.get('contact', 'N/A')}")
                        st.write(f"**Plot:** {req['plot_number']}")
                        st.write(f"**Notes:** {req.get('notes', 'N/A')}")
                    with c2:
                        plot_data = get_plot(req['plot_number'])
                        if plot_data and not plot_data.get('occupied'):
                            if st.button(f"Approve", key=f"app_{req['id']}", type="primary"):
                                if update_plot(req['plot_number'], {'occupied': True, 'user_id': req['user_id'], 'user_name': req.get('user_name', ''), 'contact': req.get('contact', ''), 'change_log': f"Approved #{req['id']}"}):
                                    update_request_status(req['id'], 'approved')
                                    st.success("Approved!"); st.rerun()
                        else:
                            st.warning("Plot unavailable")
                        if st.button(f"Reject", key=f"rej_{req['id']}", type="secondary"):
                            update_request_status(req['id'], 'rejected')
                            st.rerun()
        else:
            st.info("No pending requests")

        with at2:
            st.markdown("### Direct Assignment")
            c1, c2, c3 = st.columns(3)
            with c1: ap = st.number_input("Plot #", 1, TOTAL_PLOTS, 1, key="admin_ap")
            with c2: au = st.text_input("User ID", key="admin_au")
            with c3: an = st.text_input("User Name", key="admin_an")
            
            # 🔥 PHASE 3: Add Renewal Date input
            st.markdown("**📅 Plot Renewal Tracking**")
            renewal_date = st.date_input("Renewal Due Date (Optional)", value=None, key="admin_renewal", help="Set a date to trigger a ⚠️ warning 30 days before expiry")
            
            if st.button("Assign", type="primary", use_container_width=True):
                if au:
                    updates = {
                        'occupied': True, 
                        'user_id': au, 
                        'user_name': an, 
                        'change_log': "Direct admin assign"
                    }
                    
                    # 🔥 PHASE 3: Save renewal date if provided
                    if renewal_date:
                        updates['renewal_due_date'] = str(renewal_date)
                        updates['renewal_status'] = 'active'
                        
                    if update_plot(ap, updates):
                        st.success(f"Plot {ap} assigned!"); st.rerun()

            st.markdown("---")
            st.markdown("### Force Release")
            rp = st.number_input("Plot to release", 1, TOTAL_PLOTS, 1, key="admin_rp")
            if st.button("Force Release", type="secondary", use_container_width=True):
                # 🔥 PHASE 3: Clear renewal date when releasing
                if update_plot(rp, {
                    'occupied': False, 
                    'user_id': None, 
                    'user_name': None, 
                    'contact': None,
                    'renewal_due_date': None,
                    'renewal_status': None,
                    'change_log': "Force released by admin"
                }):
                    st.success(f"Plot {rp} released!"); st.rerun()
