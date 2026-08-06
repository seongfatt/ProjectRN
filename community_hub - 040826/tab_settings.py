import streamlit as st
from datetime import datetime, timedelta
from config import supabase, DB_CONNECTED

def show_settings():
    st.header("⚙️ System Settings & Data Cleanup")
    st.caption("Manage data retention policies. By default, all data is kept indefinitely ('Never').")
    
    if not DB_CONNECTED:
        st.error("Database not connected")
        return
    
    st.divider()
    
    # ───────────────────────────────────────────────────
    # 1. VOLUNTEER LINKS CLEANUP
    # ───────────────────────────────────────────────────
    st.subheader("🔗 Volunteer Links")
    st.caption("Clean up expired or old volunteer access tokens.")
    
    token_retention = st.selectbox(
        "Select timeframe to delete old links:",
        ["Never", "7 days", "14 days", "30 days", "60 days", "90 days"],
        index=0,  # 🔥 DEFAULT IS "Never"
        key="setting_token_retention"
    )
    
    if st.button("🗑️ Clean Up Volunteer Links Now", type="secondary", use_container_width=True):
        if token_retention == "Never":
            st.warning("⚠️ Please select a timeframe (e.g., 30 days) to delete old links. 'Never' will not delete anything.")
        else:
            with st.spinner("Cleaning up volunteer links..."):
                try:
                    days = int(token_retention.split()[0])
                    cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
                    
                    # Delete links that are inactive OR expired before the cutoff date
                    supabase.table('volunteer_tokens').delete().eq('active', False).execute()
                    supabase.table('volunteer_tokens').delete().lte('expires_at', cutoff_date).execute()
                    
                    st.success(f"✅ Successfully deleted volunteer links older than {days} days!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error cleaning up links: {e}")

    st.divider()

    # ───────────────────────────────────────────────────
    # 2. SESSIONS CLEANUP
    # ───────────────────────────────────────────────────
    st.subheader("📅 Sessions & RSVPs")
    st.caption("Clean up completed community sessions and their RSVP records.")
    
    session_retention = st.selectbox(
        "Select timeframe to delete old sessions:",
        ["Never", "7 days", "14 days", "30 days", "60 days", "90 days"],
        index=0,  # 🔥 DEFAULT IS "Never"
        key="setting_session_retention"
    )
    
    if st.button("🗑️ Clean Up Sessions Now", type="secondary", use_container_width=True):
        if session_retention == "Never":
            st.warning("⚠️ Please select a timeframe to delete old sessions. 'Never' will not delete anything.")
        else:
            with st.spinner("Cleaning up old sessions..."):
                try:
                    days = int(session_retention.split()[0])
                    cutoff_date = datetime.now() - timedelta(days=days)
                    cutoff_str = cutoff_date.strftime('%Y-%m-%d')
                    cutoff_iso = cutoff_date.isoformat()
                    
                    # Delete old sessions
                    supabase.table('sessions').delete().lte('session_date', cutoff_str).execute()
                    
                    # Delete old RSVPs associated with those sessions
                    supabase.table('session_rsvp').delete().lte('created_at', cutoff_iso).execute()
                    
                    st.success(f"✅ Successfully deleted sessions and RSVPs older than {days} days!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error cleaning up sessions: {e}")

    st.divider()

    # ───────────────────────────────────────────────────
    # 3. ATTENDANCE RECORDS CLEANUP
    # ───────────────────────────────────────────────────
    st.subheader("📊 Attendance Records")
    st.caption("Clean up historical attendance check-in records.")
    st.warning("⚠️ **Caution:** Deleting attendance records is permanent and will affect historical reports and streaks.")
    
    attendance_retention = st.selectbox(
        "Select timeframe to delete old attendance:",
        ["Never", "30 days", "60 days", "90 days", "180 days", "1 year"],
        index=0,  # 🔥 DEFAULT IS "Never"
        key="setting_attendance_retention"
    )
    
    if st.button("🗑️ Clean Up Attendance Now", type="secondary", use_container_width=True):
        if attendance_retention == "Never":
            st.warning("⚠️ Please select a timeframe to delete old attendance. 'Never' will not delete anything.")
        else:
            # Add a final confirmation step for attendance
            confirm = st.checkbox("I understand this will permanently delete historical attendance data.", key="confirm_attendance_delete")
            
            if confirm:
                with st.spinner("Cleaning up attendance records..."):
                    try:
                        days_map = {"30 days": 30, "60 days": 60, "90 days": 90, "180 days": 180, "1 year": 365}
                        days = days_map.get(attendance_retention, 90)
                        cutoff_date = datetime.now() - timedelta(days=days)
                        cutoff_str = cutoff_date.strftime('%Y-%m-%d')
                        
                        supabase.table('attendance').delete().lte('date', cutoff_str).execute()
                        
                        st.success(f"✅ Successfully deleted attendance records older than {days} days!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error cleaning up attendance: {e}")
            else:
                st.info("Please check the confirmation box to proceed.")

    st.divider()
    
    # ───────────────────────────────────────────────────
    # CURRENT STATUS SUMMARY
    # ───────────────────────────────────────────────────
    st.subheader("📋 Current Retention Policy Summary")
    st.markdown(f"""
    - **Volunteer Links:** `{token_retention}`
    - **Sessions & RSVPs:** `{session_retention}`
    - **Attendance Records:** `{attendance_retention}`
    
    *Note: Data is only deleted when you manually click the cleanup buttons above. No automatic background deletion occurs.*
    """)