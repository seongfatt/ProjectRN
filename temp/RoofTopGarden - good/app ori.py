# app.py - Rooftop Garden Manager (Supabase Version)
import streamlit as st
from datetime import datetime
from config import (
    PLOT_TYPES, TOTAL_PLOTS, TYPE_MAP, PLOT_LAYOUTS, 
    ADMIN_PASSWORD, DB_CONNECTED, refresh_data
)
from data_manager import (
    load_plots, get_plot, update_plot, get_user_plot,
    create_request, get_pending_requests, update_request_status, get_occupied_count
)
from ui_components import render_legend, render_plot_grid

# ========== PAGE CONFIG ==========
st.set_page_config(
    page_title="Rooftop Garden Plot Manager",
    page_icon="🌿",
    layout="wide"
)

# ========== SESSION STATE ==========
if 'selected_plot' not in st.session_state:
    st.session_state.selected_plot = None
if 'is_admin' not in st.session_state:
    st.session_state.is_admin = False
if 'user_id' not in st.session_state:
    st.session_state.user_id = ""

# ========== MAIN APP ==========
def main():
    st.title("🌿 Woodlands Zone 6 - Rooftop Garden")
    
    if not DB_CONNECTED:
        st.error("⚠️ Database connection failed. Please check Supabase settings.")
        st.stop()
    
    # Load data from Supabase
    plots = load_plots()
    occupied_count = get_occupied_count()
    progress_percent = occupied_count / TOTAL_PLOTS
    
    # Progress bar
    st.progress(progress_percent)
    st.subheader(f"📊 **{occupied_count} / {TOTAL_PLOTS} plots occupied** ({progress_percent:.1%})")
    
    # Legend
    render_legend()
    st.markdown("---")
    
    # User Section
    st.markdown("## 👤 Your Account")
    user_id = st.text_input(
        "**Your User ID**",
        value=st.session_state.user_id,
        placeholder="Enter your nickname/ID",
        help="This identifies you as the plot owner"
    )
    
    if user_id:
        st.session_state.user_id = user_id.strip()
        user_plot = get_user_plot(user_id)
        
        if user_plot:
            st.success(f"✅ **You currently have Plot {user_plot['plot_number']} (Type {user_plot['plot_type']})**")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🗓️ Release My Plot", type="secondary", use_container_width=True):
                    if update_plot(user_plot['plot_number'], {
                        'occupied': False,
                        'user_id': None,
                        'user_name': None,
                        'contact': None,
                        'change_log': f"Released by {user_id}"
                    }):
                        refresh_data()
                        st.success(f"Plot {user_plot['plot_number']} released!")
                        st.rerun()
            
            with col2:
                if st.button("🔄 Refresh View", use_container_width=True):
                    refresh_data()
                    st.rerun()
    
    # Plot Grid
    render_plot_grid(plots, st.session_state.selected_plot, user_id)
    
    # Plot Selection Logic
    if st.session_state.selected_plot:
        plot_num = st.session_state.selected_plot
        plot_data = get_plot(plot_num)
        
        if not plot_data:
            st.error("Plot not found")
            st.session_state.selected_plot = None
            st.rerun()
        
        if plot_data['occupied']:
            st.error(f"❌ Plot {plot_num} is already taken by {plot_data['user_id']}!")
            st.session_state.selected_plot = None
            st.rerun()
        else:
            # Available plot - Show request form
            plot_type = TYPE_MAP[plot_num]
            area = PLOT_TYPES[plot_type]["area"]
            color = PLOT_TYPES[plot_type]["colour"]
            
            st.markdown(f"""
            <div style="background-color: {color}; color: white; padding: 20px; border-radius: 10px; text-align: center; margin: 15px 0;">
                <div style="font-size: 24px; font-weight: bold;">Plot {plot_num}</div>
                <div style="font-size: 18px;">Type {plot_type} ({area} m²)</div>
                <div style="font-size: 14px; margin-top: 10px;">✅ Available for request</div>
            </div>
            """, unsafe_allow_html=True)
            
            with st.form("plot_request_form", clear_on_submit=True):
                req_user_id = user_id or st.text_input("Your User ID:", key="req_user_id")
                req_name = st.text_input("Your Full Name:", key="req_name")
                req_contact = st.text_input("Contact Info (Email/Phone):", key="req_contact")
                req_notes = st.text_area("Additional Notes:", key="req_notes")
                
                submitted = st.form_submit_button("📨 Submit Plot Request", type="primary", use_container_width=True)
                
                if submitted and req_user_id:
                    # Check if user already has a plot
                    existing = get_user_plot(req_user_id)
                    if existing:
                        st.error(f"❌ You already have Plot {existing['plot_number']}! Release it first.")
                    else:
                        # Create request
                        result = create_request(plot_num, req_user_id, req_name, req_contact, req_notes)
                        if result:
                            st.success(f"✅ Request submitted for Plot {plot_num}!")
                            st.info("An admin will review and approve your request.")
                            st.session_state.selected_plot = None
                            st.rerun()
    
    # Statistics
    st.markdown("---")
    st.markdown("## 📈 Garden Statistics")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Plots", TOTAL_PLOTS)
    with col2:
        st.metric("Available", TOTAL_PLOTS - occupied_count)
    with col3:
        st.metric("Occupied", occupied_count)
    with col4:
        st.metric("Occupancy", f"{progress_percent:.1%}")
    
    # Type breakdown
    st.markdown("### 📊 Breakdown by Plot Type")
    type_cols = st.columns(4)
    
    for i, (type_key, info) in enumerate(PLOT_TYPES.items()):
        with type_cols[i]:
            # Count occupied for this type
            type_occupied = len([p for p in plots if p['plot_type'] == type_key and p['occupied']])
            pct = (type_occupied / info["total"]) * 100 if info["total"] > 0 else 0
            
            st.markdown(
                f'<div style="background-color: {info["colour"]}; color: white; padding: 15px; border-radius: 10px; text-align: center;">'
                f'<div style="font-size: 18px; font-weight: bold;">Type {type_key}</div>'
                f'<div style="font-size: 24px; margin: 5px 0;">{type_occupied}/{info["total"]}</div>'
                f'<div>{info["area"]} m² each</div>'
                f'<div>({pct:.1f}% occupied)</div>'
                f'</div>',
                unsafe_allow_html=True
            )
    
    # Admin Panel
    st.markdown("---")
    with st.expander("🔐 Admin Access"):
        if st.session_state.is_admin:
            st.success("✅ Admin mode active")
            
            admin_tab1, admin_tab2, admin_tab3 = st.tabs(["📝 Manage Requests", "🛠️ Direct Tools", "🚪 Logout"])
            
            with admin_tab1:
                st.subheader("📋 Pending Plot Requests")
                requests = get_pending_requests()
                
                if requests:
                    for req in requests:
                        with st.expander(f"Request #{req['id']}: Plot {req['plot_number']} - {req['user_id']}"):
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                st.write(f"**User ID:** {req['user_id']}")
                                st.write(f"**Name:** {req.get('user_name', 'N/A')}")
                                st.write(f"**Contact:** {req.get('contact', 'N/A')}")
                                st.write(f"**Requested Plot:** {req['plot_number']}")
                                st.write(f"**Notes:** {req.get('notes', 'N/A')}")
                                st.write(f"**Submitted:** {req['created_at']}")
                            
                            with col2:
                                plot_data = get_plot(req['plot_number'])
                                is_available = plot_data and not plot_data['occupied']
                                
                                if is_available:
                                    if st.button(f"✅ Approve", key=f"approve_{req['id']}", type="primary"):
                                        # Update plot
                                        if update_plot(req['plot_number'], {
                                            'occupied': True,
                                            'user_id': req['user_id'],
                                            'user_name': req.get('user_name', ''),
                                            'contact': req.get('contact', ''),
                                            'change_log': f"Approved request #{req['id']}"
                                        }):
                                            # Update request status
                                            update_request_status(req['id'], 'approved')
                                            refresh_data()
                                            st.success("Approved and assigned!")
                                            st.rerun()
                                else:
                                    st.warning("⚠️ Plot no longer available")
                                    if st.button(f"❌ Reject (Unavailable)", key=f"reject_unavail_{req['id']}"):
                                        update_request_status(req['id'], 'rejected')
                                        st.rerun()
                                
                                if st.button(f"❌ Reject", key=f"reject_{req['id']}", type="secondary"):
                                    update_request_status(req['id'], 'rejected')
                                    st.success("Request rejected")
                                    st.rerun()
                else:
                    st.info("No pending requests")
            
            with admin_tab2:
                st.subheader("🛠️ Direct Admin Tools")
                
                # Direct assignment
                st.markdown("### Direct Plot Assignment")
                col1, col2, col3 = st.columns(3)
                with col1:
                    assign_plot = st.number_input("Plot #", 1, TOTAL_PLOTS, 1, key="admin_assign_plot")
                with col2:
                    assign_user = st.text_input("User ID", key="admin_assign_user")
                with col3:
                    assign_name = st.text_input("User Name", key="admin_assign_name")
                
                if st.button("📝 Assign Plot Directly", type="primary"):
                    if assign_user:
                        if update_plot(assign_plot, {
                            'occupied': True,
                            'user_id': assign_user,
                            'user_name': assign_name,
                            'change_log': f"Direct assignment by admin"
                        }):
                            refresh_data()
                            st.success(f"Plot {assign_plot} assigned to {assign_user}!")
                            st.rerun()
                
                st.markdown("---")
                
                # Force release
                st.markdown("### Force Release Plot")
                release_plot = st.number_input("Plot to release", 1, TOTAL_PLOTS, 1, key="admin_release")
                
                if st.button("🗑️ Force Release", type="secondary"):
                    if update_plot(release_plot, {
                        'occupied': False,
                        'user_id': None,
                        'user_name': None,
                        'contact': None,
                        'change_log': "Force released by admin"
                    }):
                        refresh_data()
                        st.success(f"Plot {release_plot} released!")
                        st.rerun()
            
            with admin_tab3:
                if st.button("🚪 Logout Admin", type="primary", use_container_width=True):
                    st.session_state.is_admin = False
                    st.rerun()
        
        else:
            admin_pass = st.text_input("Admin Password:", type="password", key="admin_pass")
            if st.button("Login as Admin", type="primary"):
                if admin_pass == ADMIN_PASSWORD:
                    st.session_state.is_admin = True
                    st.success("✅ Admin access granted!")
                    st.rerun()
                else:
                    st.error("❌ Incorrect password!")
    
    # Footer
    st.markdown("---")
    st.caption(f"🌱 **Woodlands Zone 6 Rooftop Garden** | Data persists in Supabase | {datetime.now().strftime('%Y-%m-%d %H:%M')}")

if __name__ == "__main__":
    main()