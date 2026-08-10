import streamlit as st
from datetime import datetime
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
    fig, ax = plt.subplots(1, 1, figsize=(18, 22))
    fig.patch.set_facecolor('#f8f9fa')
    ax.set_facecolor('#f8f9fa')

    ax.text(0.5, 0.98, 'Woodlands Zone 6 - Roof Top Garden Layout', 
            transform=ax.transAxes, fontsize=26, fontweight='bold',
            ha='center', va='top', color='#1a1a2e')
    ax.text(0.5, 0.965, 'All 76 Garden Plots - Type, Size & Availability', 
            transform=ax.transAxes, fontsize=14, ha='center', va='top', color='#666')

    plots_dict = {p['plot_number']: p for p in plots_data}

    sections = [
        ('Section A', list(range(1, 11))),
        ('Section B', list(range(11, 21))),
        ('Section C', list(range(21, 31))),
        ('Section D', list(range(31, 41))),
        ('Section E', list(range(41, 51))),
        ('Section F', list(range(51, 61))),
        ('Section G', list(range(61, 71))),
        ('Section H', list(range(71, 77))),
    ]

    y_pos = 0.94
    for section_name, plot_nums in sections:
        ax.text(0.02, y_pos, section_name, transform=ax.transAxes, 
                fontsize=11, fontweight='bold', color='#333')
        y_pos -= 0.018

        x_start = 0.02
        box_w = 0.085
        box_h = 0.022
        gap = 0.008

        for i, pn in enumerate(plot_nums):
            ptype = TYPE_MAP.get(pn, 'B')
            color = PLOT_TYPES[ptype]["colour"]
            plot = plots_dict.get(pn)
            occ = plot.get('occupied', False) if plot else False

            alpha = 0.4 if occ else 0.95
            edge = '#333' if occ else 'white'
            lw = 2 if occ else 1.5

            row = i // 10
            col = i % 10
            x = x_start + col * (box_w + gap)
            y = y_pos - row * (box_h + gap * 0.5)

            rect = FancyBboxPatch((x, y), box_w, box_h,
                                  boxstyle="round,pad=0.003",
                                  facecolor=color, edgecolor=edge, linewidth=lw,
                                  transform=ax.transAxes, alpha=alpha)
            ax.add_patch(rect)

            text_color = 'white' if not occ else '#fff'
            weight = 'bold' if not occ else 'normal'
            ax.text(x + box_w/2, y + box_h/2, str(pn), 
                   transform=ax.transAxes, fontsize=7, fontweight=weight,
                   ha='center', va='center', color=text_color)

        y_pos -= 0.055 if len(plot_nums) <= 10 else 0.075

    legend_elements = []
    for tk, ti in PLOT_TYPES.items():
        legend_elements.append(mpatches.Patch(facecolor=ti['colour'], edgecolor='white', 
                                              label=f'Type {tk} ({ti["area"]} m2) - {ti["total"]} plots'))
    legend_elements.append(mpatches.Patch(facecolor='gray', edgecolor='#333', alpha=0.4,
                                          label='Darker = Occupied'))

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

    cols = st.columns(4)
    for i, (tk, ti) in enumerate(PLOT_TYPES.items()):
        with cols[i]:
            st.markdown(f'<div style="background:{ti["colour"]};color:white;padding:8px;border-radius:6px;text-align:center;font-weight:bold;font-size:12px;">Type {tk}<br/>{ti["area"]} m²</div>', unsafe_allow_html=True)
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
    st.caption("Bright = Available | Faded/X = Taken")

    plots_dict = {p['plot_number']: p for p in plots}

    for plot_name, layout in PLOT_LAYOUTS.items():
        st.markdown(f"#### {plot_name}")
        for row in layout:
            cols = st.columns(10)
            for ci, pn in enumerate(row):
                if pn is None:
                    cols[ci].empty(); continue
                pd = plots_dict.get(pn, {'occupied': False, 'user_id': None, 'user_name': None, 'plot_type': TYPE_MAP.get(pn, 'B')})
                occ = pd.get('occupied', False)
                owner = pd.get('user_id', '')
                oname = pd.get('user_name', '')
                ptype = pd.get('plot_type', TYPE_MAP.get(pn, 'B'))
                is_my = user_id and owner and str(owner).strip().lower() == str(user_id).strip().lower()
                color = PLOT_TYPES[ptype]["colour"]
                sel = (st.session_state.get('selected_plot') == pn)

                with cols[ci]:
                    if st.button(str(pn), key=f"gplot_{pn}", use_container_width=True, type="primary" if sel else "secondary", disabled=occ):
                        st.session_state.selected_plot = pn
                        st.rerun()

                    x_mark = '<div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);font-size:20px;color:white;font-weight:bold;">✗</div>' if occ else ''
                    op = 0.8 if is_my else (0.5 if occ else 1.0)
                    bd = "gold" if is_my else ("#00FFFF" if sel else color)
                    bw = "3px" if (is_my or sel) else "2px"

                    st.markdown(f'<div style="background:{color};color:white;border:{bw} solid {bd};border-radius:6px;padding:8px 0;margin:2px 0;text-align:center;font-weight:bold;font-size:14px;opacity:{op};position:relative;">{pn}{x_mark}</div>', unsafe_allow_html=True)

                    if occ:
                        did = str(owner)[:10]
                        dname = str(oname)[:12] if oname else ""
                        if is_my:
                            label = f"👤 YOU<br/><small>{did}: {dname}</small>" if dname else f"👤 YOU<br/><small>{did}</small>"
                            lc, bg, bdr = "#00FF00", "rgba(0,100,0,0.3)", "1px solid #00FF00"
                        else:
                            label = f"👤 {did}<br/><small>{dname}</small>" if dname else f"👤 {did}"
                            lc, bg, bdr = "#FFFFFF", "rgba(100,100,100,0.2)", "none"
                        st.markdown(f'<div style="text-align:center;font-size:9px;color:{lc};margin-top:-3px;min-height:24px;line-height:1.2;background:{bg};padding:2px;border:{bdr};border-radius:3px;overflow:hidden;">{label}</div>', unsafe_allow_html=True)
                    else:
                        st.markdown('<div style="text-align:center;font-size:9px;color:#888;margin-top:-3px;">available</div>', unsafe_allow_html=True)

    if st.session_state.get('selected_plot'):
        pn = st.session_state.selected_plot
        pd = get_plot(pn)
        if not pd or pd.get('occupied'):
            st.error(f"Plot {pn} not available"); st.session_state.selected_plot = None; st.rerun()
        else:
            ptype = TYPE_MAP[pn]
            area = PLOT_TYPES[ptype]["area"]
            color = PLOT_TYPES[ptype]["colour"]
            st.markdown(f'<div style="background:{color};color:white;padding:15px;border-radius:8px;text-align:center;margin:10px 0;"><div style="font-size:20px;font-weight:bold;">Plot {pn}</div><div>Type {ptype} ({area} m²)</div><div style="font-size:12px;margin-top:5px;">Available</div></div>', unsafe_allow_html=True)

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

    # Export garden plot layout image
    st.divider()
    st.subheader("Export Garden Plot Layout")
    if st.button("Generate Plot Layout Image", type="primary", use_container_width=True):
        with st.spinner("Generating layout image..."):
            fig = create_garden_plot_image(plots)
            img_path = '/tmp/garden_layout.png'
            fig.savefig(img_path, dpi=200, bbox_inches='tight', 
                       facecolor='#f8f9fa', edgecolor='none')
            plt.close(fig)

            with open(img_path, 'rb') as img_file:
                st.download_button(
                    label="Download Garden Layout (PNG)",
                    data=img_file,
                    file_name=f"garden_layout_{datetime.now().strftime('%Y%m%d')}.png",
                    mime="image/png"
                )
            st.image(img_path, caption="Garden Plot Layout - All 76 Plots", use_container_width=True)

    st.markdown("### By Type")
    tc = st.columns(4)
    for i, (tk, ti) in enumerate(PLOT_TYPES.items()):
        with tc[i]:
            to = len([p for p in plots if p['plot_type'] == tk and p['occupied']])
            pc = (to / ti["total"]) * 100 if ti["total"] > 0 else 0
            st.markdown(f'<div style="background:{ti["colour"]};color:white;padding:10px;border-radius:8px;text-align:center;"><div style="font-size:14px;font-weight:bold;">Type {tk}</div><div style="font-size:20px;margin:3px 0;">{to}/{ti["total"]}</div><div>{ti["area"]} m²</div><div>({pc:.1f}%)</div></div>', unsafe_allow_html=True)

    st.markdown("---")
    with st.expander("Admin Panel"):
        if st.session_state.get('is_admin'):
            st.success("Admin mode")
            at1, at2, at3 = st.tabs(["Requests", "Direct", "Logout"])

            with at1:
                reqs = get_pending_requests()
                if reqs:
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
                                if st.button(f"Reject", key=f"rej_{req['id']}"):
                                    update_request_status(req['id'], 'rejected')
                                    st.rerun()
                else: st.info("No pending requests")

            with at2:
                st.markdown("### Direct Assignment")
                c1, c2, c3 = st.columns(3)
                with c1: ap = st.number_input("Plot #", 1, TOTAL_PLOTS, 1, key="admin_ap")
                with c2: au = st.text_input("User ID", key="admin_au")
                with c3: an = st.text_input("User Name", key="admin_an")
                if st.button("Assign", type="primary"):
                    if au:
                        if update_plot(ap, {'occupied': True, 'user_id': au, 'user_name': an, 'change_log': "Direct admin assign"}):
                            st.success(f"Plot {ap} assigned!"); st.rerun()

                st.markdown("---")
                st.markdown("### Force Release")
                rp = st.number_input("Plot to release", 1, TOTAL_PLOTS, 1, key="admin_rp")
                if st.button("Force Release", type="secondary"):
                    if update_plot(rp, {'occupied': False, 'user_id': None, 'user_name': None, 'contact': None, 'change_log': "Force released by admin"}):
                        st.success(f"Plot {rp} released!"); st.rerun()

            with at3:
                if st.button("Logout", type="primary", use_container_width=True):
                    st.session_state.is_admin = False; st.rerun()
        else:
            ap = st.text_input("Admin Password:", type="password", key="garden_admin_pass")
            if st.button("Login", type="primary"):
                from config import ADMIN_PASSWORD
                if ap == ADMIN_PASSWORD:
                    st.session_state.is_admin = True; st.success("Admin!"); st.rerun()
                else: st.error("Wrong password")
