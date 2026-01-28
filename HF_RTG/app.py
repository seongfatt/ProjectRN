# app.py - MAIN APPLICATION (FIXED VERSION)
import streamlit as st
import pandas as pd
from datetime import datetime
import json
import os

# Local imports - IMPORT HF_REPO_ID FROM CONFIG
from config import PLOT_TYPES, TOTAL_PLOTS, TYPE_MAP, PLOT_LAYOUTS, HF_REPO_ID
from data_manager import load_data, save_data
from ui_components import render_legend, render_plot_grid

# ---------- ADMIN CONFIG ----------
ADMIN_PASSWORD = "gardenadmin"

# ---------- SESSION STATE ----------
def init_session_state():
    """Initialize session state"""
    defaults = {
        'selected_plot': None,
        'is_admin': False,
        'user_id': '',
        'requests': [],
        'data_loaded': False
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

# ---------- REQUEST HANDLING ----------
def load_requests():
    """Load plot requests"""
    REQUESTS_FILE = "plot_requests.json"
    if os.path.exists(REQUESTS_FILE):
        try:
            with open(REQUESTS_FILE, 'r') as f:
                return json.load(f)
        except:
            return []
    return []

def save_requests(requests):
    """Save plot requests"""
    REQUESTS_FILE = "plot_requests.json"
    with open(REQUESTS_FILE, 'w') as f:
        json.dump(requests, f, indent=2)

# ---------- MAIN APP ----------
def main():
    st.set_page_config(
        page_title="Rooftop Garden Plot Manager",
        page_icon="🌿",
        layout="wide"
    )
    
    # Initialize session state
    init_session_state()
    
    # Title
    st.title("🌿 Rooftop Garden Plot Manager")
    
    # Load data
    df = load_data()
    
    # REMOVE THE WARNING CHECK - HF_REPO_ID IS ALREADY SET IN CONFIG
    # Progress stats
    occupied_count = int(df["Occupy"].sum())
    progress_percent = occupied_count / TOTAL_PLOTS
    
    st.progress(progress_percent)
    st.subheader(f"📊 **{occupied_count} / {TOTAL_PLOTS} plots occupied** ({progress_percent:.1%})")
    
    # Show legend
    render_legend()
    st.markdown("---")
    
    # User section
    st.markdown("## 👤 Your Account")
    user_id = st.text_input(
        "**Your User ID**",
        value=st.session_state.user_id,
        placeholder="Enter your nickname/ID",
        help="This identifies you as the plot owner",
        key="user_id_input"
    )
    
    if user_id:
        st.session_state.user_id = user_id
        
        # Check if user has a plot
        user_has_plot = df[
            df["User_ID"].astype(str).str.strip().str.lower() == 
            user_id.strip().lower()
        ]
        
        if not user_has_plot.empty:
            user_plot = user_has_plot.iloc[0]
            st.success(f"✅ **You currently have Plot {user_plot['Plot']} (Type {user_plot['Type']})**")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🗓️ Release My Plot", type="secondary", use_container_width=True):
                    df.loc[
                        df["User_ID"].astype(str).str.strip().str.lower() == user_id.strip().lower(),
                        ["Occupy", "User_ID", "Change"]
                    ] = [
                        False,
                        pd.NA,
                        f"Released by {user_id} - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                    ]
                    save_data(df)
                    st.success(f"Plot {user_plot['Plot']} has been released!")
                    st.rerun()
            
            with col2:
                if st.button("🔄 Refresh View", use_container_width=True):
                    st.rerun()
    
    # Show plot grid
    render_plot_grid(df, st.session_state.selected_plot, user_id)
    
    # Plot selection and request
    if st.session_state.selected_plot:
        selected_plot_num = st.session_state.selected_plot
        plot_data = df[df["Plot"] == selected_plot_num].iloc[0]
        occupied = bool(plot_data["Occupy"]) if pd.notna(plot_data["Occupy"]) else False
        
        if occupied:
            st.error(f"❌ Plot {selected_plot_num} is already taken!")
            st.session_state.selected_plot = None
        else:
            plot_type = TYPE_MAP[selected_plot_num]
            area = PLOT_TYPES[plot_type]["area"]
            color = PLOT_TYPES[plot_type]["colour"]
            
            st.markdown(f"""
            <div style="background-color: {color}; color: white; padding: 20px; border-radius: 10px; text-align: center; margin: 15px 0;">
                <div style="font-size: 24px; font-weight: bold;">Plot {selected_plot_num}</div>
                <div style="font-size: 18px;">Type {plot_type} ({area} m²)</div>
            </div>
            """, unsafe_allow_html=True)
            
            # Request form
            with st.form("plot_request_form", clear_on_submit=True):
                request_user_id = user_id or st.text_input("Your User ID:", key="request_user_id")
                request_name = st.text_input("Your Full Name:", key="request_name")
                request_contact = st.text_input("Contact Info (Email/Phone):", key="request_contact")
                request_notes = st.text_area("Additional Notes:", key="request_notes")
                
                submitted = st.form_submit_button("📨 Submit Plot Request")
                
                if submitted and request_user_id:
                    # Add request
                    requests = load_requests()
                    new_request = {
                        "timestamp": datetime.now().isoformat(),
                        "plot": selected_plot_num,
                        "user_id": request_user_id,
                        "name": request_name,
                        "contact": request_contact,
                        "notes": request_notes,
                        "status": "pending"
                    }
                    requests.append(new_request)
                    save_requests(requests)
                    st.session_state.requests = requests
                    
                    st.success(f"✅ Request submitted for Plot {selected_plot_num}!")
                    st.info("An admin will review your request and contact you.")
                    st.session_state.selected_plot = None
                    st.rerun()
    
    # Statistics
    st.markdown("---")
    st.markdown("## 📈 Plot Statistics")
    
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
            occupied = df[df["Type"] == type_key]["Occupy"].sum()
            pct = (occupied / info["total"]) * 100 if info["total"] > 0 else 0
            
            st.markdown(
                f'<div style="background-color: {info["colour"]}; color: white; padding: 15px; border-radius: 10px; text-align: center;">'
                f'<div style="font-size: 18px; font-weight: bold;">Type {type_key}</div>'
                f'<div style="font-size: 24px; margin: 5px 0;">{int(occupied)}/{info["total"]}</div>'
                f'<div>{info["area"]} m² each</div>'
                f'<div>({pct:.1f}% occupied)</div>'
                f'</div>',
                unsafe_allow_html=True
            )
    
    # Admin access
    st.markdown("---")
    with st.expander("🔐 Admin Access"):
        if st.session_state.get("is_admin", False):
            st.success("✅ Admin mode active")
            
            # Admin tabs
            admin_tab1, admin_tab2, admin_tab3 = st.tabs(["📝 Manage Requests", "🛠️ Tools", "🚪 Logout"])
            
            with admin_tab1:
                st.subheader("📋 Pending Requests")
                requests = load_requests()
                pending = [r for r in requests if r.get("status") == "pending"]
                
                if pending:
                    for i, req in enumerate(pending):
                        with st.expander(f"Request #{i+1}: Plot {req['plot']} - {req['user_id']}"):
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                st.write(f"**User:** {req['user_id']}")
                                st.write(f"**Name:** {req.get('name', 'N/A')}")
                                st.write(f"**Contact:** {req.get('contact', 'N/A')}")
                                st.write(f"**Plot:** {req['plot']}")
                                st.write(f"**Submitted:** {req['timestamp']}")
                            
                            with col2:
                                plot_data = df[df["Plot"] == req["plot"]].iloc[0]
                                is_occupied = bool(plot_data["Occupy"])
                                
                                if not is_occupied:
                                    if st.button(f"✅ Approve", key=f"approve_{i}"):
                                        df.loc[df["Plot"] == req["plot"], ["Occupy", "User_ID", "Change"]] = [
                                            True,
                                            req["user_id"],
                                            f"Approved from request - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                                        ]
                                        save_data(df)
                                        req["status"] = "approved"
                                        save_requests(requests)
                                        st.success("Approved!")
                                        st.rerun()
                                else:
                                    st.warning("Plot already occupied")
                                
                                if st.button(f"❌ Reject", key=f"reject_{i}"):
                                    req["status"] = "rejected"
                                    save_requests(requests)
                                    st.success("Rejected!")
                                    st.rerun()
                else:
                    st.info("No pending requests")
            
            with admin_tab2:
                st.subheader("🛠️ Admin Tools")
                
                # Release plot
                st.markdown("### Release Plot")
                release_plot = st.number_input("Plot to release", 1, TOTAL_PLOTS, 1)
                
                if st.button("🗑️ Release Plot", type="secondary"):
                    plot_data = df[df["Plot"] == release_plot].iloc[0]
                    if plot_data["Occupy"]:
                        df.loc[df["Plot"] == release_plot, ["Occupy", "User_ID", "Change"]] = [
                            False,
                            pd.NA,
                            f"Released by ADMIN - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                        ]
                        save_data(df)
                        st.success(f"Plot {release_plot} released!")
                        st.rerun()
                    else:
                        st.info("Plot already available")
            
            with admin_tab3:
                if st.button("🚪 Logout Admin", type="primary"):
                    st.session_state.is_admin = False
                    st.rerun()
        
        else:
            # Login form
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
    st.caption(f"🌱 **Rooftop Garden Management System** | {datetime.now().strftime('%Y-%m-%d %H:%M')}")

if __name__ == "__main__":
    main()