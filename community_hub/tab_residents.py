import streamlit as st
import pandas as pd
from config import supabase, DB_CONNECTED, load_activities, TYPE_MAP, PLOT_TYPES
from utils import mask_phone, get_attendance_count, get_user_plot, load_plots

def show_residents():
    st.header("Resident Network & Entitlements")

    if not DB_CONNECTED:
        st.error("Database not connected"); return

    participants = st.session_state.participants
    plots = st.session_state.plots
    acts = load_activities()

    total = len(participants)
    active = len([p for p in participants if p.get('active', True)])
    newbies = len([p for p in participants if p.get('is_new')])
    regular = active - newbies

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Residents", total)
    c2.metric("Active", active)
    c3.metric("New", newbies)
    c4.metric("Regular", regular)
    st.divider()

    st.subheader("Resident Directory")

    search = st.text_input("Search resident", placeholder="Name or last 4 digits...")
    filter_status = st.selectbox("Filter", ["All", "Active Only", "New Only", "Regular Only", "Has Garden Plot", "No Garden Plot"])

    plot_dict = {p.get('user_id', '').lower().strip(): p for p in plots if p.get('occupied')}

    display_data = []
    for p in participants:
        if not p.get('active', True): continue

        if search:
            s = search.lower()
            if s not in p['name'].lower() and s not in p.get('contact', '')[-4:]:
                continue

        if filter_status == "New Only" and not p.get('is_new'): continue
        if filter_status == "Regular Only" and p.get('is_new'): continue

        pid = p['id']
        has_plot = pid.lower().strip() in plot_dict

        if filter_status == "Has Garden Plot" and not has_plot: continue
        if filter_status == "No Garden Plot" and has_plot: continue

        attendance_info = []
        for act in acts:
            try:
                count = supabase.table('attendance').select('*', count='exact').eq('participant_id', pid).eq('source', act['name']).execute().count
                if count > 0:
                    attendance_info.append(f"{act['name']}: {count}x")
            except:
                pass

        plot_info = ""
        if has_plot:
            plot_data = plot_dict[pid.lower().strip()]
            plot_info = f"Plot {plot_data['plot_number']} (Type {plot_data['plot_type']})"

        display_data.append({
            "ID": pid,
            "Name": p['name'],
            "Contact": p.get('contact', 'N/A'),
            "Status": "New" if p.get('is_new') else "Regular",
            "Indemnity": "Yes" if p.get('indemnity') else "No",
            "Garden Plot": plot_info if plot_info else "",
            "Activities": ", ".join(attendance_info) if attendance_info else "",
            "Total Attendance": get_attendance_count(pid)
        })

    if not display_data:
        st.info("No residents found matching criteria")
        return

    df = pd.DataFrame(display_data)
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button("Export Resident Directory (CSV)", csv, f"residents_{pd.Timestamp.now().strftime('%Y%m%d')}.csv", "text/csv")

    # ═══════════════════════════════════════════
    #  GARDEN PLOT ENTITLEMENTS — Visual Display
    # ═══════════════════════════════════════════
    st.divider()
    st.subheader("Garden Plot Entitlements")
    st.caption("Occupied = Red | Available = Green")

    all_plots = load_plots()
    plots_dict = {p['plot_number']: p for p in all_plots}

    # Summary metrics
    plot_owners = [p for p in plots if p.get('occupied')]
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Plots", 76)
    c2.metric("Occupied", len(plot_owners))
    c3.metric("Available", 76 - len(plot_owners))

    # Visual grid display
    st.markdown("#### Plot Status Grid")
    st.caption("Red = Occupied | Green = Available | Click plot for details")

    # Display in rows of 10
    for row_start in range(1, 77, 10):
        cols = st.columns(10)
        for i, pn in enumerate(range(row_start, min(row_start + 10, 77))):
            plot = plots_dict.get(pn)
            ptype = TYPE_MAP.get(pn, 'B')
            color = PLOT_TYPES[ptype]["colour"]
            is_occ = plot and plot.get('occupied', False)

            with cols[i]:
                # Border color: red for occupied, green for available
                border_color = "#ff4444" if is_occ else "#44ff44"
                border_width = "3px" if is_occ else "2px"
                opacity = "0.7" if is_occ else "1.0"

                st.markdown(
                    f'<div style="background:{color};color:white;border:{border_width} solid {border_color};'
                    f'border-radius:6px;padding:6px 0;margin:2px 0;text-align:center;font-weight:bold;font-size:12px;'
                    f'opacity:{opacity};">{pn}</div>',
                    unsafe_allow_html=True
                )
                if is_occ:
                    owner = str(plot.get('user_id', ''))[:8]
                    st.caption(f"{owner}...")
                else:
                    st.caption("Free")

    # Detailed table with payment status (admin view)
    if st.session_state.get('is_authenticated') and st.session_state.get('user_role') == 'admin':
        st.markdown("#### Payment Management")
        st.info("Admin can mark plots as paid/unpaid")

        for plot in plot_owners:
            cols = st.columns([2, 2, 1, 1])
            cols[0].write(f"Plot {plot['plot_number']}")
            cols[1].write(plot.get('user_name', 'N/A'))
            is_paid = plot.get('paid', False)
            cols[2].write("Yes" if is_paid else "No")

            btn_label = "Mark Unpaid" if is_paid else "Mark Paid"
            if cols[3].button(btn_label, key=f"pay_{plot['plot_number']}"):
                try:
                    supabase.table('garden_plots').update({'paid': not is_paid}).eq('plot_number', plot['plot_number']).execute()
                    st.success(f"Plot {plot['plot_number']} updated!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    # ═══════════════════════════════════════════
    #  EXPORT GARDEN PLOT ENTITLEMENTS (CSV)
    #  Uses text labels instead of emojis to prevent encoding issues
    # ═══════════════════════════════════════════
    st.divider()
    st.subheader("Export Garden Plot Entitlements")
    st.caption("CSV uses text labels: [OCCUPIED] / [AVAILABLE] to avoid encoding issues")

    plot_export_data = []
    for pn in range(1, 77):
        ptype = TYPE_MAP.get(pn, 'B')
        area = PLOT_TYPES[ptype]["area"]
        plot = plots_dict.get(pn)
        if plot and plot.get('occupied'):
            resident = next((p for p in participants if p['id'].lower().strip() == str(plot.get('user_id', '')).lower().strip()), None)
            plot_export_data.append({
                "Plot Number": pn,
                "Plot Type": ptype,
                "Area (sqm)": area,
                "Status": "[OCCUPIED]",  # Text label, not emoji
                "Owner ID": plot.get('user_id', ''),
                "Owner Name": plot.get('user_name', resident['name'] if resident else ''),
                "Contact": plot.get('contact', resident.get('contact', '') if resident else ''),
                "Paid": "Yes" if plot.get('paid') else "No"
            })
        else:
            plot_export_data.append({
                "Plot Number": pn,
                "Plot Type": ptype,
                "Area (sqm)": area,
                "Status": "[AVAILABLE]",  # Text label, not emoji
                "Owner ID": "",
                "Owner Name": "",
                "Contact": "",
                "Paid": ""
            })

    plot_df = pd.DataFrame(plot_export_data)
    st.dataframe(plot_df, use_container_width=True, hide_index=True)

    plot_csv = plot_df.to_csv(index=False).encode('utf-8')
    st.download_button("Export Garden Plot Entitlements (CSV)", plot_csv, f"garden_plots_{pd.Timestamp.now().strftime('%Y%m%d')}.csv", "text/csv")

    st.divider()
    st.subheader("Activity Participation Summary")

    for act in acts:
        try:
            r = supabase.table('attendance').select('participant_id').eq('source', act['name']).execute()
            unique_participants = len(set(x['participant_id'] for x in r.data)) if r.data else 0
            total_records = len(r.data) if r.data else 0

            c1, c2, c3 = st.columns(3)
            c1.metric(f"{act['name']}", f"{unique_participants} unique")
            c2.metric("Total Records", total_records)
            c3.metric("Participation Rate", f"{(unique_participants / active * 100):.1f}%" if active > 0 else "0%")
        except:
            pass
