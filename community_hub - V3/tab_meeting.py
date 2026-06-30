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
    #  SECTION 4 — COLORFUL HTML REPORT
    # ═══════════════════════════════════════════
    st.subheader("📄 Monthly Meeting Report")

    if st.button("📊 Generate Colorful Report", type="primary", use_container_width=True):
        html_report = generate_html_report(start_date, end_date, occupied, available, occupancy_rate, type_df, all_att, total_records, unique_p, s1_total, s2_total, act_summary, parts, parts_df, new_c, reg_c, unsigned)
        st.success("Report generated!")
        st.components.v1.html(html_report, height=600, scrolling=True)

        st.download_button(
            "📥 Download HTML Report",
            html_report,
            f"monthly_meeting_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.html",
            "text/html"
        )

        if all_att:
            csv = att_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                "📊 Download Raw Data (CSV)",
                csv,
                f"activity_data_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.csv",
                "text/csv"
            )

def generate_html_report(start_date, end_date, occupied, available, occupancy_rate, type_df, all_att, total_records, unique_p, s1_total, s2_total, act_summary, parts, parts_df, new_c, reg_c, unsigned):
    from config import TOTAL_PLOTS, PLOT_TYPES

    # Build HTML using string concatenation to avoid f-string issues with CSS braces
    parts_list = []
    parts_list.append("<!DOCTYPE html><html><head><meta charset=\"UTF-8\"><style>")
    parts_list.append("body{font-family:'Segoe UI',Arial,sans-serif;margin:0;padding:20px;background:#f5f7fa;}")
    parts_list.append(".container{max-width:900px;margin:0 auto;background:white;border-radius:12px;box-shadow:0 4px 20px rgba(0,0,0,0.1);overflow:hidden;}")
    parts_list.append(".header{background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:white;padding:30px;text-align:center;}")
    parts_list.append(".header h1{margin:0;font-size:28px;}.header p{margin:8px 0 0;opacity:0.9;font-size:14px;}")
    parts_list.append(".section{padding:25px 30px;border-bottom:1px solid #eee;}")
    parts_list.append(".section-title{color:#333;font-size:20px;font-weight:bold;margin-bottom:15px;}")
    parts_list.append(".stats-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:15px;margin:15px 0;}")
    parts_list.append(".stat-card{background:#f8f9fa;border-radius:10px;padding:15px;text-align:center;border-left:4px solid #667eea;}")
    parts_list.append(".stat-value{font-size:24px;font-weight:bold;color:#667eea;}.stat-label{font-size:12px;color:#666;margin-top:4px;}")
    parts_list.append(".progress-bar{background:#e9ecef;border-radius:10px;height:20px;overflow:hidden;margin:10px 0;}")
    parts_list.append(".progress-fill{background:linear-gradient(90deg,#667eea,#764ba2);height:100%;border-radius:10px;}")
    parts_list.append(".activity-card{background:#f8f9fa;border-radius:8px;padding:15px;margin:10px 0;border-left:4px solid #28a745;}")
    parts_list.append(".type-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;}")
    parts_list.append(".type-item{padding:10px;border-radius:6px;color:white;font-weight:bold;text-align:center;}")
    parts_list.append(".footer{background:#f8f9fa;padding:15px;text-align:center;font-size:12px;color:#666;}")
    parts_list.append("</style></head><body>")

    parts_list.append('<div class="container">')
    parts_list.append('<div class="header"><h1>Woodlands Zone 6 Community Hub</h1>')
    parts_list.append('<p>Monthly Meeting Report | ' + start_date.strftime('%d %b %Y') + ' - ' + end_date.strftime('%d %b %Y') + '</p>')
    parts_list.append('<p style="font-size:12px;margin-top:10px;">Generated: ' + datetime.now().strftime('%d %b %Y, %I:%M %p') + '</p></div>')

    parts_list.append('<div class="section"><div class="section-title">Roof Top Garden</div>')
    parts_list.append('<div class="stats-grid">')
    parts_list.append('<div class="stat-card"><div class="stat-value">' + str(TOTAL_PLOTS) + '</div><div class="stat-label">Total Plots</div></div>')
    parts_list.append('<div class="stat-card"><div class="stat-value">' + str(occupied) + '</div><div class="stat-label">Occupied</div></div>')
    parts_list.append('<div class="stat-card"><div class="stat-value">' + str(available) + '</div><div class="stat-label">Available</div></div>')
    parts_list.append('<div class="stat-card"><div class="stat-value">' + f"{occupancy_rate:.1%}" + '</div><div class="stat-label">Occupancy Rate</div></div>')
    parts_list.append('</div>')
    parts_list.append('<div class="progress-bar"><div class="progress-fill" style="width:' + str(occupancy_rate*100) + '%"></div></div>')
    parts_list.append('<p style="text-align:center;color:#666;font-size:12px;">Garden Utilization: ' + f"{occupancy_rate:.1%}" + '</p>')

    parts_list.append('<div class="section-title" style="margin-top:20px;">Plot Types Breakdown</div>')
    parts_list.append('<div class="type-grid">')

    for _, row in type_df.reset_index().iterrows():
        ptype = row['Plot Type'].split(' ')[1].split('(')[0]
        color = PLOT_TYPES.get(ptype, {}).get('colour', '#667eea')
        parts_list.append('<div class="type-item" style="background:' + color + ';">' + row['Plot Type'] + '<br><small>' + str(row['Occupied']) + '/' + str(row['Occupied'] + row['Available']) + ' (' + f"{row['Rate']:.0f}" + '%)</small></div>')

    parts_list.append('</div></div>')

    parts_list.append('<div class="section"><div class="section-title">Activity Participation</div>')

    if all_att:
        parts_list.append('<div class="stats-grid">')
        parts_list.append('<div class="stat-card"><div class="stat-value">' + str(total_records) + '</div><div class="stat-label">Total Records</div></div>')
        parts_list.append('<div class="stat-card"><div class="stat-value">' + str(int(unique_p)) + '</div><div class="stat-label">Unique Residents</div></div>')
        parts_list.append('<div class="stat-card"><div class="stat-value">' + str(s1_total) + '</div><div class="stat-label">Session 1</div></div>')
        parts_list.append('<div class="stat-card"><div class="stat-value">' + str(s2_total) + '</div><div class="stat-label">Session 2</div></div>')
        parts_list.append('</div>')

        if act_summary:
            parts_list.append('<div class="section-title" style="margin-top:20px;">By Activity</div>')
            for row in act_summary:
                parts_list.append('<div class="activity-card"><strong>' + row['Activity'] + '</strong><br><small>' + str(row['Records']) + ' records | ' + str(row['Unique Residents']) + ' unique residents | S1: ' + str(row['Session 1']) + ' | S2: ' + str(row['Session 2']) + '</small></div>')
    else:
        parts_list.append('<p style="color:#666;">No attendance records for this period.</p>')

    parts_list.append('</div>')

    parts_list.append('<div class="section"><div class="section-title">Resident Snapshot</div>')

    try:
        if parts:
            parts_list.append('<div class="stats-grid">')
            parts_list.append('<div class="stat-card"><div class="stat-value">' + str(len(parts_df)) + '</div><div class="stat-label">Total Registered</div></div>')
            parts_list.append('<div class="stat-card"><div class="stat-value">' + str(new_c) + '</div><div class="stat-label">New</div></div>')
            parts_list.append('<div class="stat-card"><div class="stat-value">' + str(reg_c) + '</div><div class="stat-label">Regular</div></div>')
            parts_list.append('<div class="stat-card"><div class="stat-value">' + str(unsigned) + '</div><div class="stat-label">Unsigned Indemnity</div></div>')
            parts_list.append('</div>')
    except:
        parts_list.append('<p style="color:#666;">Resident data unavailable.</p>')

    parts_list.append('</div>')

    parts_list.append('<div class="footer">Woodlands Zone 6 Community Hub | Monthly Meeting Report | Generated ' + datetime.now().strftime('%d %b %Y') + '</div>')
    parts_list.append('</div></body></html>')

    return ''.join(parts_list)
