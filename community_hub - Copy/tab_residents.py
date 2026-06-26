import streamlit as st
import pandas as pd
from config import supabase, DB_CONNECTED, load_activities, PLOT_TYPES, TYPE_MAP, TOTAL_PLOTS
from utils import mask_phone, get_attendance_count

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
            "Contact": mask_phone(p.get('contact', 'N/A')),
            "Status": "New" if p.get('is_new') else "Regular",
            "Indemnity": "Yes" if p.get('indemnity') else "No",
            "Garden Plot": plot_info if plot_info else "—",
            "Activities": ", ".join(attendance_info) if attendance_info else "—",
            "Total Attendance": get_attendance_count(pid)
        })

    if not display_data:
        st.info("No residents found matching criteria")
        return

    df = pd.DataFrame(display_data)
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button("Export Resident List (CSV)", csv, f"residents_{pd.Timestamp.now().strftime('%Y%m%d')}.csv", "text/csv")

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

    st.divider()
    st.subheader("Garden Plot Entitlements")

    # Build complete list of all 76 plots
    occupied_plots = {p['plot_number']: p for p in plots if p.get('occupied')}
    occupied_count = len(occupied_plots)
    available_count = TOTAL_PLOTS - occupied_count

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Plots", TOTAL_PLOTS)
    c2.metric("Occupied", occupied_count)
    c3.metric("Available", available_count)

    # Show ALL plots in a single table
    all_plot_data = []
    for pn in range(1, TOTAL_PLOTS + 1):
        ptype = TYPE_MAP.get(pn, 'B')
        area = PLOT_TYPES[ptype]["area"]

        if pn in occupied_plots:
            plot = occupied_plots[pn]
            resident = next((p for p in participants if p['id'].lower().strip() == str(plot.get('user_id', '')).lower().strip()), None)
            all_plot_data.append({
                "Plot #": pn,
                "Type": f"Type {ptype} ({area} m²)",
                "Status": "🔴 Occupied",
                "Owner ID": plot.get('user_id', 'N/A'),
                "Owner Name": plot.get('user_name', resident['name'] if resident else 'N/A'),
                "Contact": mask_phone(plot.get('contact', resident.get('contact', 'N/A') if resident else 'N/A')),
                "Paid": "Yes" if plot.get('paid', False) else "No"
            })
        else:
            all_plot_data.append({
                "Plot #": pn,
                "Type": f"Type {ptype} ({area} m²)",
                "Status": "🟢 Available",
                "Owner ID": "—",
                "Owner Name": "—",
                "Contact": "—",
                "Paid": "—"
            })

    all_df = pd.DataFrame(all_plot_data)

    # Filter toggle for admin convenience
    show_filter = st.selectbox("Filter Plots", ["All Plots", "Occupied Only", "Available Only"], key="plot_filter")
    if show_filter == "Occupied Only":
        display_df = all_df[all_df["Status"] == "🔴 Occupied"]
    elif show_filter == "Available Only":
        display_df = all_df[all_df["Status"] == "🟢 Available"]
    else:
        display_df = all_df

    st.dataframe(display_df, use_container_width=True, hide_index=True)

    # Admin: Mark Paid buttons
    if st.session_state.get('is_authenticated') and st.session_state.get('user_role') == 'admin':
        st.markdown("### Payment Management")
        st.info("Admin can mark occupied plots as paid/unpaid")

        occupied_only = all_df[all_df["Status"] == "🔴 Occupied"]
        if occupied_only.empty:
            st.info("No occupied plots to manage")
        else:
            for _, row in occupied_only.iterrows():
                pn = row["Plot #"]
                plot = occupied_plots.get(pn, {})
                is_paid = plot.get('paid', False)

                cols = st.columns([1, 2, 2, 1, 1])
                cols[0].write(f"**Plot {pn}**")
                cols[1].write(row["Owner Name"])
                cols[2].write(row["Owner ID"])
                cols[3].write("✅ Paid" if is_paid else "❌ Unpaid")

                btn_label = "Mark Unpaid" if is_paid else "Mark Paid"
                if cols[4].button(btn_label, key=f"pay_{pn}"):
                    try:
                        supabase.table('garden_plots').update({'paid': not is_paid}).eq('plot_number', pn).execute()
                        st.success(f"Plot {pn} updated!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
