import streamlit as st
import pandas as pd
from config import supabase, DB_CONNECTED, load_activities, TYPE_MAP, PLOT_TYPES
from utils import mask_phone, get_user_plot, load_plots
from collections import defaultdict

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

    # 🚀 SPEED FIX: Pre-calculate all attendance stats in ONE query (Fixes N+1 problem)
    activity_counts = defaultdict(lambda: defaultdict(int))
    total_counts = defaultdict(int)

    try:
        # Fetch only the columns we need to make it ultra-fast and save bandwidth
        all_att = supabase.table('attendance').select('participant_id, source').execute().data
        for rec in all_att:
            pid_att = rec['participant_id']
            source_att = rec['source']
            activity_counts[pid_att][source_att] += 1
            total_counts[pid_att] += 1
    except Exception:
        pass

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

        # 🚀 SPEED FIX: Use pre-calculated dictionary instead of querying DB
        attendance_info = []
        for act in acts:
            count = activity_counts[pid][act['name']]
            if count > 0:
                attendance_info.append(f"{act['name']}: {count}x")

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
            "Total Attendance": total_counts.get(pid, 0),  # 🚀 SPEED FIX: Instant lookup instead of DB query!
            # 🔥 PHASE 3: Add Streak Column
            "Streak": f"🔥 {p.get('streak_weeks', 0)} weeks" if p.get('streak_weeks', 0) >= 3 else f"{p.get('streak_weeks', 0)} weeks"
        })

    if not display_data:
        st.info("No residents found matching criteria")
        return

    df = pd.DataFrame(display_data)
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button("Export Resident Directory (CSV)", csv, f"residents_{pd.Timestamp.now().strftime('%Y%m%d')}.csv", "text/csv")

    # GARDEN PLOT ENTITLEMENTS — Visual Display with Type Colors
    st.divider()
    st.subheader("Garden Plot Entitlements")

    all_plots = load_plots()
    plots_dict = {p['plot_number']: p for p in all_plots}

    # Summary metrics
    plot_owners = [p for p in plots if p.get('occupied')]
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Plots", 76)
    c2.metric("Occupied", len(plot_owners))
    c3.metric("Available", 76 - len(plot_owners))

    # By Type summary cards (same style as tab_garden.py)
    st.markdown("#### By Type")
    tc = st.columns(4)
    for i, (tk, ti) in enumerate(PLOT_TYPES.items()):
        with tc[i]:
            to = len([p for p in plots if p['plot_type'] == tk and p.get('occupied')])
            pc = (to / ti["total"]) * 100 if ti["total"] > 0 else 0
            st.markdown(
                f'<div style="background:{ti["colour"]};color:white;padding:10px;border-radius:8px;text-align:center;">'
                f'<div style="font-size:14px;font-weight:bold;">Type {tk}</div>'
                f'<div style="font-size:20px;margin:3px 0;">{to}/{ti["total"]}</div>'
                f'<div>{ti["area"]} m\u00B2</div>'
                f'<div>({pc:.1f}%)</div></div>',
                unsafe_allow_html=True
            )
    
    # Visual grid display — PRIVACY: no names or contacts shown
    st.markdown("#### Plot Status Grid")
    st.caption("Occupied = Dimmed + Red X | Available = Bright | Green border = Available, Red border = Occupied")

    # Display in rows of 10 with actual type colors
    for row_start in range(1, 77, 10):
        cols = st.columns(10)
        for i, pn in enumerate(range(row_start, min(row_start + 10, 77))):
            plot = plots_dict.get(pn)
            ptype = TYPE_MAP.get(pn, 'B')
            color = PLOT_TYPES[ptype]["colour"]
            is_occ = plot and plot.get('occupied', False)

            with cols[i]:
                if is_occ:
                    # Occupied - dimmed color, red border, X mark, NO name/contact
                    st.markdown(
                        f'<div style="background:{color};opacity:0.4;border:2px solid #ff4444;border-radius:6px;padding:6px 0;margin:2px 0;text-align:center;font-weight:bold;font-size:12px;color:#ccc;">'
                        f'{pn}</div>'
                        f'<div style="text-align:center;font-size:12px;color:#ff4444;margin-top:-2px;font-weight:bold;">X</div>',
                        unsafe_allow_html=True
                    )
                else:
                    # Available - bright color, green border, display only (NO button, NO dropdown)
                    st.markdown(
                        f'<div style="background:{color};border:2px solid #44ff44;border-radius:6px;padding:6px 0;margin:2px 0;text-align:center;font-weight:bold;font-size:12px;color:white;">'
                        f'{pn}</div>'
                        f'<div style="text-align:center;font-size:9px;color:#44ff44;margin-top:-2px;">Type {ptype}</div>',
                        unsafe_allow_html=True
                    )

    # EXPORT GARDEN PLOT ENTITLEMENTS (CSV)
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
                "Status": "[OCCUPIED]",
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
                "Status": "[AVAILABLE]",
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

    # 🚀 SPEED FIX: Re-use the pre-calculated dictionaries instead of querying DB again!
    for act in acts:
        act_name = act['name']
        # Count unique participants for this activity from our pre-calculated dict
        unique_participants = sum(1 for pid, counts in activity_counts.items() if counts[act_name] > 0)
        total_records = sum(counts[act_name] for counts in activity_counts.values())

        c1, c2, c3 = st.columns(3)
        c1.metric(f"{act_name}", f"{unique_participants} unique")
        c2.metric("Total Records", total_records)
        c3.metric("Participation Rate", f"{(unique_participants / active * 100):.1f}%" if active > 0 else "0%")