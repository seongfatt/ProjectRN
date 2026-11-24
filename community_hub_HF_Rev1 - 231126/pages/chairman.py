import streamlit as st
from config import supabase, DB_CONNECTED, load_activities, PLOT_TYPES, TOTAL_PLOTS
from utils import load_plots, get_occupied_count
# pages/chairman.py — Add this import
from services import AnalyticsService

def show_chairman():
    st.header("🧭 Community Overview")
    st.caption("High-level metrics for RN Chairman oversight")
    
    if not DB_CONNECTED:
        st.error("Database not connected")
        return
        
    participants = st.session_state.participants
    plots = load_plots()
    acts = load_activities()
    
    # Filter active participants for accurate percentages
    active_participants = [p for p in participants if p.get('active', True)]
    total_active = len(active_participants)
    
    # ═══════════════════════════════════════════════════════
    # 1. NEW: Community Membership Breakdown
    # ═══════════════════════════════════════════════════════
    st.subheader("👥 Community Membership Breakdown")
    
    # Count member types (defaults to 'Resident' if not set yet)
    breakdown = AnalyticsService.get_member_breakdown(participants)
    resident_count = breakdown['resident']
    rn_count = breakdown['rn']
    volunteer_count = breakdown['volunteer']
    res_pct = breakdown['resident_pct']
    rn_pct = breakdown['rn_pct']
    vol_pct = breakdown['volunteer_pct']
    total_active = breakdown['total']
    
    # Display top-level metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Members", total_active)
    c2.metric("👤 Residents", resident_count, f"{res_pct:.1f}%")
    c3.metric("🏘️ RN Members", rn_count, f"{rn_pct:.1f}%")
    c4.metric("🤝 Volunteers", volunteer_count, f"{vol_pct:.1f}%")
    
    st.markdown("---")
    
     # Display visual progress bars
    # Use st.html() (Streamlit ≥1.38) or components.v1.html for older versions
    # This preserves all CSS including width animations
    progress_html = f"""
    <div style="background: #f8f9fa; padding: 15px; border-radius: 10px; margin-bottom: 20px; font-family: 'Segoe UI', sans-serif;">
        <div style="margin-bottom: 14px;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                <span style="font-weight: 600; color: #555;">🏠 Residents</span>
                <span style="font-weight: 600; color: #1a1a1a;">{res_pct:.1f}% ({resident_count})</span>
            </div>
            <div style="background: #e9ecef; border-radius: 6px; height: 14px; overflow: hidden;">
                <div style="background: linear-gradient(90deg, #6c757d, #adb5bd); width: {res_pct:.1f}%; height: 100%; border-radius: 6px;"></div>
            </div>
        </div>

        <div style="margin-bottom: 14px;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                <span style="font-weight: 600; color: #555;">🏘️ RN Members</span>
                <span style="font-weight: 600; color: #1a1a1a;">{rn_pct:.1f}% ({rn_count})</span>
            </div>
            <div style="background: #e9ecef; border-radius: 6px; height: 14px; overflow: hidden;">
                <div style="background: linear-gradient(90deg, #0d6efd, #6ea8fe); width: {rn_pct:.1f}%; height: 100%; border-radius: 6px;"></div>
            </div>
        </div>

        <div>
            <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                <span style="font-weight: 600; color: #555;">🤝 Volunteers</span>
                <span style="font-weight: 600; color: #1a1a1a;">{vol_pct:.1f}% ({volunteer_count})</span>
            </div>
            <div style="background: #e9ecef; border-radius: 6px; height: 14px; overflow: hidden;">
                <div style="background: linear-gradient(90deg, #198754, #75b798); width: {vol_pct:.1f}%; height: 100%; border-radius: 6px;"></div>
            </div>
        </div>
    </div>
    """

    # Option A: st.html() — best for Streamlit ≥1.38 (no CSS stripping)
    st.html(progress_html)

    # Option B: If on older Streamlit, uncomment below and comment out
    
    st.divider()
    
    # ═══════════════════════════════════════════════════════
    # 2. Resident Network (Existing)
    # ═══════════════════════════════════════════════════════
    st.subheader("🏘️ Resident Network")
    total = len(participants)
    active = len([p for p in participants if p.get('active', True)])
    newbies = len([p for p in participants if p.get('is_new')])
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Registered", total)
    c2.metric("Active Residents", active)
    c3.metric("New This Month", newbies)
    
    st.divider()
    
    # ═══════════════════════════════════════════════════════
    # 3. Garden Metrics (Existing)
    # ═══════════════════════════════════════════════════════
    st.subheader("🌱 Roof Top Garden")
    occupied = get_occupied_count()
    available = TOTAL_PLOTS - occupied
    rate = occupied / TOTAL_PLOTS if TOTAL_PLOTS else 0
    
    gc1, gc2, gc3 = st.columns(3)
    gc1.metric("Total Plots", TOTAL_PLOTS)
    gc2.metric("Occupied", occupied)
    gc3.metric("Occupancy Rate", f"{rate:.1%}")
    
    st.progress(rate, text=f"Garden Utilization: {rate:.1%}")
    
    st.divider()
    
    # ═══════════════════════════════════════════════════════
    # 4. Activity Highlights (Existing)
    # ═══════════════════════════════════════════════════════
    st.subheader("🥁 Active Activities")
    if acts:
        for act in acts:
            st.markdown(f"- **{act['name']}** ({act.get('session_1_label', 'Session 1')})")
    else:
        st.info("No activities configured")
        
    st.divider()
    st.info("🔒 **PDPA Notice:** Detailed resident contact information and full data exports are restricted to the System Admin to ensure compliance.")