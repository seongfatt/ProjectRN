import streamlit as st
import pandas as pd
from datetime import datetime
from config import supabase, DB_CONNECTED, load_activities, TYPE_MAP, PLOT_TYPES, APP_URL
from utils import mask_phone, get_user_plot, load_plots
from collections import defaultdict
import urllib.parse

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

    plot_dict = {str(p.get('user_id', '')).lower().strip(): p for p in plots if p.get('occupied')}

    # 🚀 SPEED FIX: Pre-calculate all attendance stats in ONE query (Fixes N+1 problem)
    activity_counts = defaultdict(lambda: defaultdict(int))
    total_counts = defaultdict(int)

    try:
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
            if s not in p.get('name', '').lower() and s not in str(p.get('contact', ''))[-4:]:
                continue

        if filter_status == "New Only" and not p.get('is_new'): continue
        if filter_status == "Regular Only" and p.get('is_new'): continue

        # 🔥 SAFE ID ACCESS: Prevents crashes if 'id' is missing
        pid = str(p.get('id', 'UNKNOWN'))
        has_plot = pid.lower().strip() in plot_dict

        if filter_status == "Has Garden Plot" and not has_plot: continue
        if filter_status == "No Garden Plot" and has_plot: continue

        attendance_info = []
        for act in acts:
            count = activity_counts[pid][act['name']]
            if count > 0:
                attendance_info.append(f"{act['name']}: {count}x")

        plot_info = ""
        if has_plot:
            plot_data = plot_dict[pid.lower().strip()]
            plot_info = f"Plot {plot_data['plot_number']} (Type {plot_data['plot_type']})"

        contact_display = mask_phone(p.get('contact', 'N/A')) if st.session_state.get('user_role') == 'chairman' else p.get('contact', 'N/A')

        display_data.append({
            "ID": pid,
            "Name": p.get('name', 'Unknown'),
            "Contact": contact_display,
            "Block": p.get('block_no', 'N/A'),
            "Status": "New" if p.get('is_new') else "Regular",
            "Indemnity": "Yes" if p.get('indemnity') else "No",
            "Garden Plot": plot_info if plot_info else "",
            "Activities": ", ".join(attendance_info) if attendance_info else "",
            "Total Attendance": total_counts.get(pid, 0),
            "Streak": f"🔥 {p.get('streak_weeks', 0)} weeks" if p.get('streak_weeks', 0) >= 3 else f"{p.get('streak_weeks', 0)} weeks"
        })

    if not display_data:
        st.info("No residents found matching criteria")
        return

    df = pd.DataFrame(display_data)
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()
    
    if st.session_state.get('user_role') == 'admin':
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Export Resident Directory (CSV)", 
            data=csv, 
            file_name=f"residents_{pd.Timestamp.now().strftime('%Y%m%d')}.csv", 
            mime="text/csv",
            key="btn_export_residents"
        )
    else:
        st.info("🔒 Full data export is restricted to Admins for PDPA compliance.")

    # GARDEN PLOT ENTITLEMENTS
    st.divider()
    st.subheader("Garden Plot Entitlements")

    all_plots = load_plots()
    plots_dict = {p['plot_number']: p for p in all_plots}

    plot_owners = [p for p in plots if p.get('occupied')]
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Plots", 76)
    c2.metric("Occupied", len(plot_owners))
    c3.metric("Available", 76 - len(plot_owners))

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
    
    st.markdown("#### Plot Status Grid")
    st.caption("Occupied = Dimmed + Red X | Available = Bright | Green border = Available, Red border = Occupied")

    for row_start in range(1, 77, 10):
        cols = st.columns(10)
        for i, pn in enumerate(range(row_start, min(row_start + 10, 77))):
            plot = plots_dict.get(pn)
            ptype = TYPE_MAP.get(pn, 'B')
            color = PLOT_TYPES[ptype]["colour"]
            is_occ = plot and plot.get('occupied', False)

            with cols[i]:
                if is_occ:
                    renewal_date_str = plot.get('renewal_due_date')
                    warning_icon = "X"
                    border_style = "1px solid #666"
                    
                    if renewal_date_str:
                        try:
                            renewal_date = pd.to_datetime(renewal_date_str).date()
                            days_left = (renewal_date - pd.Timestamp.now().date()).days
                            if 0 <= days_left <= 30:
                                border_style = "3px solid #ff4444"
                                warning_icon = "⚠️"
                        except:
                            pass
                    
                    st.markdown(
                        f'<div style="background:{color};opacity:0.4;border:{border_style};border-radius:6px;padding:6px 0;margin:2px 0;text-align:center;font-weight:bold;font-size:12px;color:#ccc;">'
                        f'{pn}</div>'
                        f'<div style="text-align:center;font-size:12px;color:#ff4444;margin-top:-2px;font-weight:bold;">{warning_icon}</div>',
                        unsafe_allow_html=True
                    )
                else:
                    st.markdown(
                        f'<div style="background:{color};border:2px solid #44ff44;border-radius:6px;padding:6px 0;margin:2px 0;text-align:center;font-weight:bold;font-size:12px;color:white;">'
                        f'{pn}</div>'
                        f'<div style="text-align:center;font-size:9px;color:#44ff44;margin-top:-2px;">Type {ptype}</div>',
                        unsafe_allow_html=True
                    )

    st.divider()
    st.subheader("Export Garden Plot Entitlements")
    st.caption("CSV uses text labels: [OCCUPIED] / [AVAILABLE] to avoid encoding issues")

    plot_export_data = []
    for pn in range(1, 77):
        ptype = TYPE_MAP.get(pn, 'B')
        area = PLOT_TYPES[ptype]["area"]
        plot = plots_dict.get(pn)
        if plot and plot.get('occupied'):
            resident = next((p for p in participants if str(p.get('id', '')).lower().strip() == str(plot.get('user_id', '')).lower().strip()), None)
            plot_export_data.append({
                "Plot Number": pn,
                "Plot Type": ptype,
                "Area (sqm)": area,
                "Status": "[OCCUPIED]",
                "Owner ID": plot.get('user_id', ''),
                "Owner Name": plot.get('user_name', resident.get('name', '') if resident else ''),
                "Contact": plot.get('contact', resident.get('contact', '') if resident else ''),
                "Paid": "Yes" if plot.get('paid') else "No"
            })
        else:
            plot_export_data.append({
                "Plot Number": pn, "Plot Type": ptype, "Area (sqm)": area, "Status": "[AVAILABLE]",
                "Owner ID": "", "Owner Name": "", "Contact": "", "Paid": ""
            })

    plot_df = pd.DataFrame(plot_export_data)
    st.dataframe(plot_df, use_container_width=True, hide_index=True)

    if st.session_state.get('user_role') == 'admin':
        plot_csv = plot_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Export Garden Plot Entitlements (CSV)", 
            data=plot_csv, 
            file_name=f"garden_plots_{pd.Timestamp.now().strftime('%Y%m%d')}.csv", 
            mime="text/csv",
            key="btn_export_garden"
        )
    else:
        st.info("🔒 Full data export is restricted to Admins for PDPA compliance.")

    st.divider()
    st.subheader("Activity Participation Summary")

    for act in acts:
        act_name = act['name']
        unique_participants = sum(1 for pid, counts in activity_counts.items() if counts[act_name] > 0)
        total_records = sum(counts[act_name] for counts in activity_counts.values())

        c1, c2, c3 = st.columns(3)
        c1.metric(f"{act_name}", f"{unique_participants} unique")
        c2.metric("Total Records", total_records)
        c3.metric("Participation Rate", f"{(unique_participants / active * 100):.1f}%" if active > 0 else "0%")

    # ========================================================================
    # 🔥 QR CODE GENERATOR SECTION (Fixed Syntax Error & Applied Security Fix)
    # ========================================================================
    st.divider()
    st.subheader("📱 Generate QR Code for Resident")
    st.caption("Generate a permanent QR code card for elderly residents to carry")
    
    qr_mode = st.radio(
        "Select Mode:",
        ["🔍 Search Specific Resident", "📋 Show All Residents for QR Generation"],
        horizontal=True,
        key="qr_mode_select"
    )
    
    if qr_mode == "🔍 Search Specific Resident":
        qr_search = st.text_input("Search resident to generate QR code", placeholder="Type name or ID...", key="qr_search_individual")
        
        if qr_search:
            s = qr_search.lower()
            matches = [p for p in participants if p.get('active', True) and (s in p.get('name', '').lower() or s in str(p.get('id', '')).lower())]
            
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
            key="qr_filter_select"
        )
        
        filtered_participants = [p for p in participants if p.get('active', True)]
        
        if qr_filter == "New Residents Only":
            filtered_participants = [p for p in filtered_participants if p.get('is_new')]
        elif qr_filter == "Regular Residents Only":
            filtered_participants = [p for p in filtered_participants if not p.get('is_new')]
        elif qr_filter == "Without Block Number":
            filtered_participants = [p for p in filtered_participants if not p.get('block_no')]
        
        st.caption(f"Showing {len(filtered_participants)} resident(s)")
        
        if filtered_participants:
            cols = st.columns(3)
            for i, p in enumerate(filtered_participants):  # Show ALL residents
                with cols[i % 3]:
                    with st.container():
                        resident_name = p.get('name', 'Unknown')
                        resident_id = str(p.get('id', 'N/A'))
                        resident_block = p.get('block_no', 'N/A')

                        # 🔒 SECURITY FIX: QR code now ONLY contains the ID. 
                        # It will only work when scanned into the volunteer's Check-In Hub.
                        qr_data = resident_id 
                        
                        # Generate QR code image URL (Fixed truncated line)
                        qr_image_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={urllib.parse.quote(qr_data)}"
                        
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
    """Helper function to display QR code card with proper ID handling and Security Fix"""
    resident_id = p.get('id')
    
    if not resident_id:
        st.error("❌ Error: This resident has no ID in the database!")
        return
    
    resident_id = str(resident_id).strip()
    resident_name = p.get('name', 'Unknown Resident')
    resident_block = p.get('block_no', 'N/A')
    
    # 🔒 SECURITY FIX: QR code now ONLY contains the ID.
    # This prevents residents from scanning it on their phones at home.
    # It will ONLY work when a volunteer scans it into the Check-In Hub text box.
    qr_data = resident_id
    
    # Generate QR code image URL
    qr_image_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={urllib.parse.quote(qr_data)}"
    
    st.markdown(f"""
    <div style="border: 3px solid #333; padding: 20px; border-radius: 15px; text-align: center; background: white; color: black; max-width: 400px; margin: 10px auto;">
        <h2 style="margin:0; color:#1a1a1a;">{resident_name}</h2>
        <p style="font-size: 16px; margin: 10px 0;">Block: {resident_block}</p>
        <img src="{qr_image_url}" style="width: 250px; height: 250px; margin: 15px 0; border: 2px solid #ddd;">
        <p style="font-size: 12px; color: #666;">Scan at Woodlands Zone 6 Kiosk</p>
        <p style="font-size: 10px; color: #999; margin-top: 10px;">ID: {resident_id}</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.caption("💡 **Tip:** Right-click the QR code image to save and print, or use Ctrl+P to print the card.")
    
    qr_info = f"""
Woodlands Zone 6 - Resident QR Card
=====================================
Name: {resident_name}
Block: {resident_block}
ID: {resident_id}

Scan this QR code at the check-in kiosk for instant attendance!
    """
    st.download_button(
        label="📥 Download QR Card Info",
        data=qr_info,
        file_name=f"QR_Card_{resident_name.replace(' ', '_')}.txt",
        mime="text/plain",
        key=f"download_qr_{resident_id}_bulk"
    )