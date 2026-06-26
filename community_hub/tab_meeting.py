import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from config import supabase, DB_CONNECTED, PLOT_TYPES, TOTAL_PLOTS, TYPE_MAP, load_activities
from utils import get_occupied_count, load_plots

def show_meeting(selected_date):
    st.header("📊 Monthly Meeting Dashboard")
    st.caption("Auto-compiled community statistics — ready for monthly meetings")

    if not DB_CONNECTED:
        st.error("Database not connected")
        return

    # ── Period Selector ──
    today = selected_date
    month_start = today.replace(day=1)
    next_m = month_start + timedelta(days=32)
    month_end = next_m.replace(day=1) - timedelta(days=1)

    c1, c2, c3 = st.columns([2, 2, 3])
    with c1:
        start_date = st.date_input("Period Start", value=month_start, key="mtg_start")
    with c2:
        end_date = st.date_input("Period End", value=month_end, key="mtg_end")
    with c3:
        st.write(""); st.write("")
        if st.button("🔄 Refresh Dashboard", use_container_width=True):
            st.rerun()

    st.info(f"Reporting Period: **{start_date.strftime('%d %b %Y')}** → **{end_date.strftime('%d %b %Y')}**")
    st.divider()

    # ═══════════════════════════════════════════
    #  SECTION 1 — ROOF TOP GARDEN
    # ═══════════════════════════════════════════
    st.subheader("🌱 Roof Top Garden Statistics")

    plots = load_plots()
    occupied = get_occupied_count()
    available = TOTAL_PLOTS - occupied
    occupancy_rate = occupied / TOTAL_PLOTS if TOTAL_PLOTS else 0

    # Big metric cards
    gc1, gc2, gc3, gc4, gc5 = st.columns(5)
    gc1.metric("Total Plots", TOTAL_PLOTS)
    gc2.metric("Occupied", occupied, delta=f"{occupancy_rate:.1%}", delta_color="normal")
    gc3.metric("Available", available)
    gc4.metric("Occupancy Rate", f"{occupancy_rate:.1%}")
    gc5.metric("Utilization", f"{occupied}/{TOTAL_PLOTS}")

    st.progress(occupancy_rate, text=f"Garden Utilization: {occupancy_rate:.1%}")

    # By Plot Type — stacked bar chart
    st.markdown("#### Occupancy Breakdown by Plot Type")
    type_rows = []
    for tk, ti in PLOT_TYPES.items():
        to = len([p for p in plots if p.get('plot_type') == tk and p.get('occupied')])
        type_rows.append({
            "Plot Type": f"Type {tk} ({ti['area']} m²)",
            "Occupied": to,
            "Available": ti["total"] - to,
            "Rate": round(to / ti["total"] * 100, 1) if ti["total"] else 0
        })
    type_df = pd.DataFrame(type_rows).set_index("Plot Type")
    st.bar_chart(type_df[["Occupied", "Available"]], use_container_width=True, color=["#d62728", "#2ca02c"])
    st.caption("Red = Occupied | Green = Available")

    # Type summary table
    st.dataframe(
        type_df.reset_index().rename(columns={"Rate": "Occupancy %"}),
        use_container_width=True, hide_index=True
    )

    # Garden requests trend
    st.markdown("#### Garden Activity (Requests & Changes)")
    try:
        reqs = supabase.table('plot_requests').select("*").gte('created_at', str(start_date)).lte('created_at', str(end_date)).execute().data
        if reqs:
            req_df = pd.DataFrame(reqs)
            req_df['date'] = pd.to_datetime(req_df['created_at']).dt.date
            daily = req_df.groupby('date').size().reset_index(name='Requests')
            daily = daily.set_index('date')
            st.area_chart(daily, use_container_width=True, color="#ff7f0e")
        else:
            st.info("No garden requests in this period")
    except Exception:
        st.info("Garden request data unavailable")

    st.divider()

    # ═══════════════════════════════════════════
    #  SECTION 2 — ACTIVITY PARTICIPATION
    # ═══════════════════════════════════════════
    st.subheader("🥁 Activity Participation")

    acts = load_activities()
    act_names = [a['name'] for a in acts]

    # Load attendance for period
    try:
        all_att = supabase.table('attendance').select("*").gte('date', str(start_date)).lte('date', str(end_date)).execute().data
    except Exception:
        all_att = []

    if all_att:
        att_df = pd.DataFrame(all_att)
        att_df['date'] = pd.to_datetime(att_df['date'])

        total_records = len(att_df)
        unique_p = att_df['participant_id'].nunique()
        s1_total = int(att_df['session_1'].sum())
        s2_total = int(att_df['session_2'].sum())
        both_sessions = int(((att_df['session_1'] == True) & (att_df['session_2'] == True)).sum())

        ac1, ac2, ac3, ac4, ac5 = st.columns(5)
        ac1.metric("Total Records", total_records)
        ac2.metric("Unique Residents", int(unique_p))
        ac3.metric("Session 1", s1_total)
        ac4.metric("Session 2", s2_total)
        ac5.metric("Both Sessions", both_sessions)

        # By Activity table + chart
        st.markdown("#### Participation by Activity")
        act_summary = []
        for act in acts:
            act_name = act['name']
            ad = att_df[att_df['source'] == act_name]
            if not ad.empty:
                act_summary.append({
                    "Activity": act_name,
                    "Records": len(ad),
                    "Unique Residents": int(ad['participant_id'].nunique()),
                    "Session 1": int(ad['session_1'].sum()),
                    "Session 2": int(ad['session_2'].sum()),
                    "Both": int(((ad['session_1'] == True) & (ad['session_2'] == True)).sum())
                })

        if act_summary:
            act_sum_df = pd.DataFrame(act_summary)
            st.dataframe(act_sum_df, use_container_width=True, hide_index=True)

            chart_df = act_sum_df.set_index("Activity")[["Session 1", "Session 2"]]
            st.bar_chart(chart_df, use_container_width=True)

        # Daily trend
        st.markdown("#### Daily Attendance Trend")
        daily = att_df.groupby(att_df['date'].dt.date).agg({
            'participant_id': 'nunique',
            'session_1': 'sum',
            'session_2': 'sum'
        }).reset_index()
        daily.columns = ['Date', 'Unique Residents', 'Session 1', 'Session 2']
        daily = daily.set_index('Date')
        st.line_chart(daily, use_container_width=True)

        # New vs Regular
        st.markdown("#### Resident Composition")
        try:
            parts = supabase.table('participants').select("*").execute().data
            if parts:
                parts_df = pd.DataFrame(parts)
                new_c = int(parts_df['is_new'].sum())
                reg_c = len(parts_df) - new_c
                unsigned = int((~parts_df['indemnity'].fillna(False)).sum())

                rc1, rc2, rc3 = st.columns(3)
                rc1.metric("🆕 New", new_c)
                rc2.metric("⭐ Regular", reg_c)
                rc3.metric("🔴 Unsigned Indemnity", unsigned)
        except Exception:
            pass
    else:
        st.info("No attendance records for the selected period")

    st.divider()

    # ═══════════════════════════════════════════
    #  SECTION 3 — FUTURE / ACTIVE ACTIVITIES
    # ═══════════════════════════════════════════
    st.subheader("📅 Active & Upcoming Activities")
    if acts:
        act_cols = st.columns(min(len(acts), 4))
        for i, act in enumerate(acts):
            with act_cols[i % 4]:
                status = "🟢 Active" if act.get('active') else "⚪ Inactive"
                # Build session labels safely — handle missing/empty session 2
                s1 = act.get('session_1_label', 'Session 1') or 'Session 1'
                s2 = act.get('session_2_label', '') or ''
                if s2.strip():
                    sessions_html = f"{s1}<br/>{s2}"
                else:
                    sessions_html = s1
                card_html = f'<div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 15px; border-radius: 10px; margin-bottom: 10px;"><div style="font-size: 18px; font-weight: bold;">{act["name"]}</div><div style="font-size: 12px; margin-top: 5px; opacity: 0.9;">{sessions_html}</div><div style="font-size: 11px; margin-top: 8px; background: rgba(255,255,255,0.2); padding: 4px 8px; border-radius: 4px; display: inline-block;">{status}</div></div>'
                st.markdown(card_html, unsafe_allow_html=True)
    else:
        st.info("No activities configured")

    st.divider()

    # ═══════════════════════════════════════════
    #  SECTION 4 — EXPORT
    # ═══════════════════════════════════════════
    st.subheader("📄 Export Meeting Pack")

    if st.button("📥 Generate Meeting Summary", type="primary", use_container_width=True):
        summary_lines = [
            "=" * 50,
            "  WOODLANDS ZONE 6 COMMUNITY HUB",
            "  Monthly Meeting Report",
            "=" * 50,
            "",
            f"Period: {start_date.strftime('%d %b %Y')} to {end_date.strftime('%d %b %Y')}",
            f"Generated: {datetime.now().strftime('%d %b %Y %H:%M')}",
            "",
            "─" * 50,
            "ROOF TOP GARDEN",
            "─" * 50,
            f"  Total Plots:     {TOTAL_PLOTS}",
            f"  Occupied:        {occupied} ({occupancy_rate:.1%})",
            f"  Available:       {available}",
            "",
            "By Type:",
        ]
        for _, row in type_df.reset_index().iterrows():
            summary_lines.append(f"  {row['Plot Type']}: {row['Occupied']}/{row['Occupied'] + row['Available']} ({row['Rate']:.0f}%)")

        summary_lines.extend([
            "",
            "─" * 50,
            "ACTIVITY PARTICIPATION",
            "─" * 50,
            f"  Total Records:      {len(all_att) if all_att else 0}",
            f"  Unique Residents:   {att_df['participant_id'].nunique() if all_att else 0}",
            f"  Session 1 Total:    {s1_total if all_att else 0}",
            f"  Session 2 Total:    {s2_total if all_att else 0}",
            "",
            "By Activity:",
        ])
        if act_summary:
            for row in act_summary:
                summary_lines.append(f"  {row['Activity']}: {row['Records']} records, {row['Unique Residents']} unique")

        summary_lines.extend([
            "",
            "─" * 50,
            "RESIDENT SNAPSHOT",
            "─" * 50,
        ])
        try:
            if parts:
                summary_lines.append(f"  Total Registered:   {len(parts_df)}")
                summary_lines.append(f"  New:                {new_c}")
                summary_lines.append(f"  Regular:            {reg_c}")
                summary_lines.append(f"  Unsigned Indemnity: {unsigned}")
        except Exception:
            pass

        summary_lines.extend(["", "=" * 50, "End of Report", "=" * 50])
        summary_text = "\n".join(summary_lines)

        st.download_button(
            "Download Meeting Summary (TXT)",
            summary_text,
            f"monthly_meeting_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.txt",
            "text/plain"
        )

        # Also offer CSV of activity data
        if all_att:
            csv = att_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                "Download Raw Activity Data (CSV)",
                csv,
                f"activity_data_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.csv",
                "text/csv"
            )
