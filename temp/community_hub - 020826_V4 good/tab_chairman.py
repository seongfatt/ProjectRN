import streamlit as st
from config import supabase, DB_CONNECTED, load_activities, PLOT_TYPES, TOTAL_PLOTS
from utils import load_plots, get_occupied_count

def show_chairman():
    st.header(" Community Overview")
    st.caption("High-level metrics for RN Chairman oversight")

    if not DB_CONNECTED:
        st.error("Database not connected"); return

    participants = st.session_state.participants
    plots = load_plots()
    acts = load_activities()

    # 1. Resident Metrics
    st.subheader(" Resident Network")
    total = len(participants)
    active = len([p for p in participants if p.get('active', True)])
    newbies = len([p for p in participants if p.get('is_new')])
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Registered", total)
    c2.metric("Active Residents", active)
    c3.metric("New This Month", newbies)

    st.divider()

    # 2. Garden Metrics
    st.subheader(" Roof Top Garden")
    occupied = get_occupied_count()
    available = TOTAL_PLOTS - occupied
    rate = occupied / TOTAL_PLOTS if TOTAL_PLOTS else 0

    gc1, gc2, gc3 = st.columns(3)
    gc1.metric("Total Plots", TOTAL_PLOTS)
    gc2.metric("Occupied", occupied)
    gc3.metric("Occupancy Rate", f"{rate:.1%}")
    
    st.progress(rate, text=f"Garden Utilization: {rate:.1%}")

    st.divider()

    # 3. Activity Highlights
    st.subheader("🥁 Active Activities")
    if acts:
        for act in acts:
            st.markdown(f"- **{act['name']}** ({act.get('session_1_label', 'Session 1')})")
    else:
        st.info("No activities configured")

    st.divider()
    st.info("🔒 **PDPA Notice:** Detailed resident contact information and full data exports are restricted to the System Admin to ensure compliance.")