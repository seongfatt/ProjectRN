import streamlit as st
import pandas as pd
from datetime import datetime
from config import supabase, DB_CONNECTED, load_activities, TYPE_MAP, PLOT_TYPES, APP_URL
from utils import mask_phone, get_user_plot, load_plots
from collections import defaultdict
import urllib.parse
import base64
import os
import streamlit.components.v1 as components


def _get_logo_base64(logo_path="logo.png"):
    """Convert local logo to base64 so it renders inside HTML components."""
    try:
        if os.path.exists(logo_path):
            with open(logo_path, "rb") as f:
                data = f.read()
            ext = os.path.splitext(logo_path)[1].lower().replace(".", "")
            if ext == "svg":
                ext = "svg+xml"
            return f"data:image/{ext};base64,{base64.b64encode(data).decode()}"
    except Exception:
        pass
    return (
        "data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+"
        "PHJlY3Qgd2lkdGg9IjYwIiBoZWlnaHQ9IjYwIiBmaWxsPSIjNjY3ZWVhIiByeD0iMTAiLz48dGV4dCB4PSI1MCUiIHk9"
        "IjUwJSIgZG9taW5hbnQtYmFzZWxpbmU9Im1pZGRsZSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZmlsbD0id2hpdGUiIGZvbnQt"
        "ZmFtaWx5PSJBcmlhbCIgZm9udC1zaXplPSIxNCIgZm9udC13ZWlnaHQ9ImJvbGQiPldaNjwvdGV4dD48L3N2Zz4="
    )


def show_residents():
    st.header("Resident Network & Entitlements")
    if not DB_CONNECTED:
        st.error("Database not connected")
        return

    participants = st.session_state.participants
    plots = st.session_state.plots
    acts = load_activities()

    total = len(participants)
    active = len([p for p in participants if p.get("active", True)])
    newbies = len([p for p in participants if p.get("is_new")])
    regular = active - newbies

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Residents", total)
    c2.metric("Active", active)
    c3.metric("New", newbies)
    c4.metric("Regular", regular)

    st.divider()
    st.subheader("Resident Directory")
    search = st.text_input("Search resident", placeholder="Name or last 4 digits...")
    filter_status = st.selectbox(
        "Filter",
        ["All", "Active Only", "New Only", "Regular Only", "Has Garden Plot", "No Garden Plot",
         "RN Members Only", "Volunteer Members Only", "Residents Only"],
    )

    # 🔥 MULTI-BLOCK: collect ALL occupied plots per resident
    plot_dict = {}
    for p in plots:
        if p.get("occupied"):
            uid = p.get("user_id")
            if uid:
                plot_dict.setdefault(str(uid).strip(), []).append(p)

    # Pre-calculate all attendance stats in ONE query
    activity_counts = defaultdict(lambda: defaultdict(int))
    total_counts = defaultdict(int)
    try:
        all_att = supabase.table("attendance").select("participant_id, source").execute().data
        for rec in all_att:
            activity_counts[rec["participant_id"]][rec["source"]] += 1
            total_counts[rec["participant_id"]] += 1
    except Exception:
        pass

    display_data = []
    for p in participants:
        if not p.get("active", True):
            continue
        if search:
            s = search.lower()
            if s not in p.get("name", "").lower() and s not in str(p.get("contact", ""))[-4:]:
                continue
        if filter_status == "New Only" and not p.get("is_new"):
            continue
        if filter_status == "Regular Only" and p.get("is_new"):
            continue
        current_type = p.get("member_type", "Resident")
        if filter_status == "RN Members Only" and current_type != "RN Member":
            continue
        if filter_status == "Volunteer Members Only" and current_type != "Volunteer Member":
            continue
        if filter_status == "Residents Only" and current_type != "Resident":
            continue
        pid = str(p.get("id", "UNKNOWN"))
        has_plot = pid.lower().strip() in plot_dict
        if filter_status == "Has Garden Plot" and not has_plot:
            continue
        if filter_status == "No Garden Plot" and has_plot:
            continue
        attendance_info = []
        for act in acts:
            count = activity_counts[pid][act["name"]]
            if count > 0:
                attendance_info.append(f"{act['name']}: {count}x")
        plot_info = ""
        if has_plot:
            plot_info = " + ".join([
                f"Plot {pd_item['plot_number']} ({pd_item.get('plot_type', 'B')}) @{pd_item.get('block_name') or 'Block 622'}"
                for pd_item in plot_dict[pid.lower().strip()]
            ])
        contact_display = (
            mask_phone(p.get("contact", "N/A"))
            if st.session_state.get("user_role") == "chairman"
            else p.get("contact", "N/A")
        )
        member_type = p.get('member_type', 'Resident')
        if member_type == 'RN Member':
            name_display = f"🏘️ {p.get('name', 'Unknown')}"
        elif member_type == 'Volunteer Member':
            name_display = f"🤝 {p.get('name', 'Unknown')}"
        else:
            name_display = f"👤 {p.get('name', 'Unknown')}"
        display_data.append(
            {
                "ID": pid,
                "Name": name_display,
                "Member Type": member_type,
                "Contact": contact_display,
                "Block": p.get('block_no', 'N/A'),
                "Status": "New" if p.get('is_new') else "Regular",
                "Indemnity": "Yes" if p.get('indemnity') else "No",
                "Garden Plot": plot_info if plot_info else "",
                "Activities": ", ".join(attendance_info) if attendance_info else "",
                "Total Attendance": total_counts.get(pid, 0),
                "Streak": (
                    f"🔥 {p.get('streak_weeks', 0)} weeks"
                    if p.get('streak_weeks', 0) >= 3
                    else f"{p.get('streak_weeks', 0)} weeks"
                ),
            }
        )

    if not display_data:
        st.info("No residents found matching criteria")
        return
    df = pd.DataFrame(display_data)
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.divider()
    if st.session_state.get("user_role") == "admin":
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Export Resident Directory (CSV)",
            data=csv,
            file_name=f"residents_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            key="btn_export_residents",
        )
    else:
        st.info("🔒 Full data export is restricted to Admins for PDPA compliance.")

    # ── GARDEN PLOT ENTITLEMENTS ─────────────────────────
    st.divider()
    st.subheader("Garden Plot Entitlements")
    all_plots = load_plots()

    try:
        blocks_data = supabase.table('garden_layout').select('block_name').execute().data
        ent_blocks = sorted(set(b['block_name'] for b in blocks_data)) or ['Block 622']
    except Exception:
        ent_blocks = ['Block 622']
    ent_block = st.selectbox("📍 Block", ent_blocks, key="ent_block_select")

    try:
        ent_layout = supabase.table('garden_layout').select('*').eq('block_name', ent_block).order('plot_number').execute().data or []
    except Exception:
        ent_layout = []
    layout_map = {i['plot_number']: i for i in ent_layout}
    ent_plot_nums = [i['plot_number'] for i in ent_layout] or list(range(1, 77))

    block_plots = [p for p in all_plots if (p.get('block_name') or 'Block 622') == ent_block]
    plots_dict = {p['plot_number']: p for p in block_plots}
    plot_owners = [p for p in block_plots if p.get('occupied')]
    total_in_block = len(ent_plot_nums)

    def _ptype_for(pn, plot):
        if plot and plot.get('plot_type'):
            return plot['plot_type']
        lr = layout_map.get(pn)
        if lr and lr.get('plot_type'):
            return lr['plot_type']
        return TYPE_MAP.get(pn, 'B')

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Plots", total_in_block)
    c2.metric("Occupied", len(plot_owners))
    c3.metric("Available", total_in_block - len(plot_owners))

    st.markdown(f"#### By Type ({ent_block})")
    layout_type_totals = {}
    for i in ent_layout:
        layout_type_totals[i.get('plot_type', 'B')] = layout_type_totals.get(i.get('plot_type', 'B'), 0) + 1
    tc = st.columns(4)
    for i, (tk, ti) in enumerate(PLOT_TYPES.items()):
        with tc[i]:
            to = len([p for p in block_plots if p.get('plot_type', _ptype_for(p['plot_number'], p)) == tk and p.get('occupied')])
            block_total = layout_type_totals.get(tk, 0)
            pc = (to / block_total) * 100 if block_total > 0 else 0
            st.markdown(
                f'<div style="background:{ti["colour"]};color:white;padding:10px;border-radius:8px;text-align:center;">'
                f'<div style="font-size:14px;font-weight:bold;">Type {tk}</div>'
                f'<div style="font-size:20px;margin:3px 0;">{to}/{block_total}</div>'
                f'<div>{ti["area"]} m\u00B2</div>'
                f'<div>({pc:.1f}%)</div></div>',
                unsafe_allow_html=True,
            )

    st.markdown("#### Plot Status Grid")
    st.caption("Occupied = Dimmed + Red X | Available = Bright | Green border = Available, Red border = Occupied")
    for row_start in range(0, len(ent_plot_nums), 10):
        row_nums = ent_plot_nums[row_start:row_start + 10]
        cols = st.columns(10)
        for i, pn in enumerate(row_nums):
            plot = plots_dict.get(pn)
            ptype = _ptype_for(pn, plot)
            color = PLOT_TYPES[ptype]['colour']
            is_occ = bool(plot and plot.get('occupied', False))
            with cols[i]:
                if is_occ:
                    renewal_date_str = plot.get('renewal_due_date')
                    warning_icon = 'X'
                    border_style = '1px solid #666'
                    if renewal_date_str:
                        try:
                            renewal_date = pd.to_datetime(renewal_date_str).date()
                            days_left = (renewal_date - pd.Timestamp.now().date()).days
                            if 0 <= days_left <= 30:
                                border_style = '3px solid #ff4444'
                                warning_icon = '⚠️'
                        except Exception:
                            pass
                    st.markdown(
                        f'<div style="background:{color};opacity:0.4;border:{border_style};border-radius:6px;padding:6px 0;margin:2px 0;text-align:center;font-weight:bold;font-size:12px;color:#ccc;">'
                        f'{pn}</div>'
                        f'<div style="text-align:center;font-size:12px;color:#ff4444;margin-top:-2px;font-weight:bold;">{warning_icon}</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        f'<div style="background:{color};border:2px solid #44ff44;border-radius:6px;padding:6px 0;margin:2px 0;text-align:center;font-weight:bold;font-size:12px;color:white;">'
                        f'{pn}</div>'
                        f'<div style="text-align:center;font-size:9px;color:#44ff44;margin-top:-2px;">Type {ptype}</div>',
                        unsafe_allow_html=True,
                    )

    st.divider()
    st.subheader("Export Garden Plot Entitlements")
    st.caption("CSV uses text labels: [OCCUPIED] / [AVAILABLE] to avoid encoding issues")
    plot_export_data = []
    for pn in ent_plot_nums:
        plot = plots_dict.get(pn)
        ptype = _ptype_for(pn, plot)
        area = PLOT_TYPES.get(ptype, PLOT_TYPES['B'])['area']
        if plot and plot.get('occupied'):
            resident = next(
                (p for p in participants
                 if str(p.get('id', '')).lower().strip() == str(plot.get('user_id', '')).lower().strip()),
                None,
            )
            plot_export_data.append(
                {
                    "Block": ent_block,
                    "Plot Number": pn,
                    "Plot Type": ptype,
                    "Area (sqm)": area,
                    "Status": "[OCCUPIED]",
                    "Owner ID": plot.get('user_id', ''),
                    "Owner Name": resident.get('name', '') if resident else plot.get('user_name', ''),
                    "Contact": resident.get('contact', '') if resident else '',
                    "Paid": 'Yes' if plot.get('paid') else 'No',
                }
            )
        else:
            plot_export_data.append(
                {
                    "Block": ent_block,
                    "Plot Number": pn,
                    "Plot Type": ptype,
                    "Area (sqm)": area,
                    "Status": "[AVAILABLE]",
                    "Owner ID": '',
                    "Owner Name": '',
                    "Contact": '',
                    "Paid": '',
                }
            )
    plot_df = pd.DataFrame(plot_export_data)
    st.dataframe(plot_df, use_container_width=True, hide_index=True)
    if st.session_state.get("user_role") == "admin":
        plot_csv = plot_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Export Garden Plot Entitlements (CSV)",
            data=plot_csv,
            file_name=f"garden_plots_{ent_block.replace(' ', '_')}_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            key="btn_export_garden",
        )
    else:
        st.info("🔒 Full data export is restricted to Admins for PDPA compliance.")

    st.divider()
    st.subheader("Activity Participation Summary")
    for act in acts:
        act_name = act["name"]
        unique_participants = sum(1 for pid, counts in activity_counts.items() if counts[act_name] > 0)
        total_records = sum(counts[act_name] for counts in activity_counts.values())
        c1, c2, c3 = st.columns(3)
        c1.metric(f"{act_name}", f"{unique_participants} unique")
        c2.metric("Total Records", total_records)
        c3.metric("Participation Rate", f"{(unique_participants / active * 100):.1f}%" if active > 0 else "0%")

    # ══════ QR CODE GENERATOR SECTION ══════
    st.divider()
    st.subheader("📱 Generate QR Code for Resident")
    st.caption("Generate a permanent QR code card for elderly residents to carry")
    qr_mode = st.radio(
        "Select Mode:",
        ["🔍 Search Specific Resident", "📋 Show All Residents for QR Generation"],
        horizontal=True,
        key="qr_mode_select",
    )
    if qr_mode == "🔍 Search Specific Resident":
        qr_search = st.text_input("Search resident to generate QR code", placeholder="Type name or ID...", key="qr_search_individual")
        if qr_search:
            s = qr_search.lower()
            matches = [p for p in participants if p.get("active", True) and (s in p.get("name", "").lower() or s in str(p.get("id", "")).lower())]
            if matches:
                for p in matches[:5]:
                    _display_qr_code(p)
            else:
                st.info("No residents found matching your search.")
    else:
        st.write(f"**Total Active Residents:** {len([p for p in participants if p.get('active', True)])}")
        qr_filter = st.selectbox(
            "Filter residents:",
            ["All Active Residents", "New Residents Only", "Regular Residents Only", "Without Block Number"],
            key="qr_filter_select",
        )
        filtered_participants = [p for p in participants if p.get("active", True)]
        if qr_filter == "New Residents Only":
            filtered_participants = [p for p in filtered_participants if p.get("is_new")]
        elif qr_filter == "Regular Residents Only":
            filtered_participants = [p for p in filtered_participants if not p.get("is_new")]
        elif qr_filter == "Without Block Number":
            filtered_participants = [p for p in filtered_participants if not p.get("block_no")]
        st.caption(f"Showing {len(filtered_participants)} resident(s)")
        if filtered_participants:
            cols = st.columns(3)
            for i, p in enumerate(filtered_participants):
                with cols[i % 3]:
                    with st.container():
                        resident_name = p.get("name", "Unknown")
                        resident_id = str(p.get("id", "N/A"))
                        resident_block = p.get("block_no", "N/A")
                        st.markdown(f"**{resident_name}**")
                        st.caption(f"🆔 {resident_id[:12]}...\n🏢 Block: {resident_block}")
                        if st.button("📱 Generate QR", key=f"qr_btn_{resident_id}", use_container_width=True):
                            st.session_state[f"show_qr_{resident_id}"] = True
                        if st.session_state.get(f"show_qr_{resident_id}"):
                            _display_qr_code(p)
                            if st.button("❌ Close", key=f"close_qr_{resident_id}"):
                                st.session_state[f"show_qr_{resident_id}"] = False
                                st.rerun()
                        st.divider()
        else:
            st.info("No residents found matching the filter.")


def _display_qr_code(p):
    """Display QR code card with working PNG download"""
    resident_id = p.get("id")
    if not resident_id:
        st.error("❌ Error: This resident has no ID in the database!")
        return
    resident_id = str(resident_id).strip()
    resident_name = str(p.get("name", "Unknown Resident")).strip()
    resident_block = str(p.get("block_no", "N/A")).strip()
    logo_src = _get_logo_base64()
    qr_data = resident_id
    qr_api_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={urllib.parse.quote(qr_data)}"
    try:
        import requests
        response = requests.get(qr_api_url)
        if response.status_code == 200:
            qr_base64 = base64.b64encode(response.content).decode()
            qr_image_src = f"data:image/png;base64,{qr_base64}"
        else:
            qr_image_src = qr_api_url
    except Exception:
        qr_image_src = qr_api_url

    card_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<script src="https://html2canvas.hertzen.com/dist/html2canvas.min.js"></script>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: transparent; display: flex; flex-direction: column; align-items: center; padding: 10px; }}
.card {{ background: #ffffff; color: #1a1a1a; border-radius: 20px; padding: 30px 24px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); width: 100%; max-width: 400px; text-align: center; }}
.header {{ display: flex; align-items: center; justify-content: center; gap: 15px; margin-bottom: 20px; }}
.logo {{ width: 60px; height: 60px; object-fit: contain; background: #f8f9fa; border-radius: 10px; padding: 5px; flex-shrink: 0; }}
.title-group {{ text-align: left; }}
.title-group h2 {{ color: #667eea; margin: 0; font-size: 22px; font-weight: 800; line-height: 1.1; }}
.title-group p {{ color: #666; margin: 2px 0 0 0; font-size: 12px; text-transform: uppercase; letter-spacing: 1px; }}
.divider {{ border: 0; border-top: 2px solid #eee; margin: 20px 0; }}
.resident-name {{ margin: 10px 0; font-size: 36px; font-weight: bold; color: #1a1a1a; word-break: break-word; }}
.resident-block {{ font-size: 20px; color: #555; margin: 5px 0 20px 0; font-weight: 500; }}
.qr-wrap {{ margin: 10px 0; }}
.qr-wrap img {{ width: 220px; height: 220px; border: 2px dashed #667eea; border-radius: 10px; padding: 10px; background: #fff; }}
.qr-hint {{ font-size: 12px; color: #888; margin: 8px 0 0 0; }}
.id-box {{ background: #f8f9fa; padding: 15px; border-radius: 10px; margin-top: 20px; }}
.id-box p {{ font-size: 24px; font-weight: bold; color: #1a1a1a; font-family: 'Courier New', monospace; margin: 0; letter-spacing: 1px; }}
.footer-text {{ font-weight: bold; color: #667eea; font-size: 16px; text-transform: uppercase; letter-spacing: 1px; margin-top: 15px; }}
.download-btn {{ margin-top: 20px; padding: 12px 24px; background: #667eea; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: bold; font-size: 16px; width: 100%; max-width: 400px; }}
</style>
</head>
<body>
<div class="card" id="residentCard">
  <div class="header">
    <img src="{logo_src}" class="logo" alt="Logo" onerror="this.style.display='none'">
    <div class="title-group"><h2>WOODLANDS ZONE 6</h2><p>Community Hub</p></div>
  </div>
  <hr class="divider">
  <h1 class="resident-name">{resident_name}</h1>
  <p class="resident-block">Block: {resident_block}</p>
  <hr class="divider">
  <div class="qr-wrap"><img src="{qr_image_src}" alt="QR Code"></div>
  <p class="qr-hint">Scan at Kiosk</p>
  <div class="id-box"><p>ID: {resident_id}</p></div>
  <p class="footer-text">Community Activities</p>
</div>
<button class="download-btn" onclick="downloadCard()">Download Card as PNG</button>
<script>
function downloadCard() {{
  const card = document.getElementById('residentCard');
  html2canvas(card, {{ backgroundColor: '#ffffff', scale: 2, useCORS: true, allowTaint: true }}).then(canvas => {{
    const link = document.createElement('a');
    link.download = 'Resident_Card_{resident_id}.png';
    link.href = canvas.toDataURL('image/png');
    link.click();
  }});
}}
</script>
</body>
</html>"""
    col1, col2, col3 = st.columns([1, 3, 1])
    with col2:
        components.html(card_html, height=750, scrolling=False)
    st.caption("💡 **Tip:** Click 'Download Card as PNG' button above, or use Ctrl+P to print.")
    card_info = f"""WOODLANDS ZONE 6 - COMMUNITY HUB
RESIDENT CARD
Name: {resident_name}
Block: {resident_block}
ID: {resident_id}
Valid for Community Activities Check-In
Scan QR code at check-in kiosk
"""
    st.download_button(
        label="📥 Download Card Info",
        data=card_info,
        file_name=f"Resident_Card_{resident_name.replace(' ', '_')}.txt",
        mime="text/plain",
        key=f"download_qr_{resident_id}_bulk",
    )