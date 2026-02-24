import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from config import supabase
import io

def show_tab3(selected_date):
    st.header("📊 Attendance Reports")
    
    # ============== REPORT TYPE SELECTION ==============
    report_type = st.radio(
        "Select Report Period",
        ["📅 Daily", "📆 Weekly", "📅 Monthly", "📆 Yearly", "📅 Custom Range"],
        horizontal=True
    )
    
    # ============== DATE RANGE SELECTION ==============
    if report_type == "📅 Daily":
        start_date = selected_date
        end_date = selected_date
    elif report_type == "📆 Weekly":
        # Current week (Monday to Sunday)
        start_date = selected_date - timedelta(days=selected_date.weekday())
        end_date = start_date + timedelta(days=6)
    elif report_type == "📅 Monthly":
        # Current month
        start_date = selected_date.replace(day=1)
        next_month = (selected_date.month % 12) + 1
        next_year = selected_date.year + (selected_date.month // 12)
        end_date = datetime(next_year, next_month, 1) - timedelta(days=1)
    elif report_type == "📆 Yearly":
        # Current year
        start_date = datetime(selected_date.year, 1, 1)
        end_date = datetime(selected_date.year, 12, 31)
    else:  # Custom Range
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Start Date", value=selected_date - timedelta(days=7))
        with col2:
            end_date = st.date_input("End Date", value=selected_date)
    
    # Display selected date range
    st.info(f"**Report Period:** {start_date.strftime('%d %b %Y')} to {end_date.strftime('%d %b %Y')}")
    
    st.divider()
    
    # ============== LOAD ATTENDANCE DATA ==============
    @st.cache_data(ttl=60)  # Cache for 1 minute
    def load_attendance_data(start, end):
        try:
            result = supabase.table('attendance')\
                .select('*')\
                .gte('date', str(start))\
                .lte('date', str(end))\
                .execute()
            return result.data
        except Exception as e:
            st.error(f"Error loading data: {e}")
            return []
    
    attendance_data = load_attendance_data(start_date, end_date)
    
    if not attendance_data:
        st.info("No attendance records found for this period")
        return
    
    # ============== DISPLAY SUMMARY STATISTICS ==============
    st.subheader("📈 Summary Statistics")
    
    total_records = len(attendance_data)
    total_participants = len(set([r['participant_id'] for r in attendance_data]))
    
    # Count sessions
    session1_count = sum(1 for r in attendance_data if r.get('session_1'))
    session2_count = sum(1 for r in attendance_data if r.get('session_2'))
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Records", total_records)
    col2.metric("Unique Participants", total_participants)
    col3.metric("Session 1", session1_count)
    col4.metric("Session 2", session2_count)
    
    st.divider()
    
    # ============== DETAILED ATTENDANCE TABLE ==============
    st.subheader("📋 Detailed Attendance")
    
    # Create DataFrame
    df = pd.DataFrame(attendance_data)
    
    # Format columns
    df['date'] = pd.to_datetime(df['date']).dt.strftime('%d %b %Y')
    
    # Select and reorder columns
    display_cols = ['date', 'name', 'session_1', 'session_2', 'timestamp']
    df_display = df[display_cols].copy()
    
    # Rename columns for display
    df_display.columns = ['Date', 'Name', 'Session 1', 'Session 2', 'Timestamp']
    
    # Format boolean values
    df_display['Session 1'] = df_display['Session 1'].map({True: '✅', False: '❌'})
    df_display['Session 2'] = df_display['Session 2'].map({True: '✅', False: '❌'})
    
    # Display table
    st.dataframe(
        df_display,
        use_container_width=True,
        hide_index=True
    )
    
    st.divider()
    
    # ============== PARTICIPANT FREQUENCY ANALYSIS ==============
    st.subheader("👥 Participant Frequency")
    
    # Group by participant
    participant_stats = df.groupby('name').agg({
        'date': 'count',
        'session_1': 'sum',
        'session_2': 'sum'
    }).reset_index()
    
    participant_stats.columns = ['Name', 'Total Days', 'Session 1 Count', 'Session 2 Count']
    participant_stats = participant_stats.sort_values('Total Days', ascending=False)
    
    st.dataframe(
        participant_stats,
        use_container_width=True,
        hide_index=True
    )
    
    st.divider()
    
    # ============== EXPORT OPTIONS ==============
    st.subheader("📥 Export Options")
    
    export_format = st.selectbox(
        "Select Export Format",
        ["CSV (Excel)", "Excel (.xlsx)", "PDF Report"]
    )
    
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        filename_prefix = st.text_input(
            "Filename Prefix",
            value=f"attendance_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
        )
    
    with col2:
        if st.button("📊 Export Summary", use_container_width=True):
            # Export summary statistics
            summary_data = {
                'Report Period': [f"{start_date.strftime('%d %b %Y')} to {end_date.strftime('%d %b %Y')}"],
                'Total Records': [total_records],
                'Unique Participants': [total_participants],
                'Session 1 Count': [session1_count],
                'Session 2 Count': [session2_count]
            }
            summary_df = pd.DataFrame(summary_data)
            
            if export_format.startswith("CSV"):
                csv = summary_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="⬇️ Download CSV",
                    data=csv,
                    file_name=f"{filename_prefix}_summary.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            else:
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                    summary_df.to_excel(writer, sheet_name='Summary', index=False)
                buffer.seek(0)
                st.download_button(
                    label="⬇️ Download Excel",
                    data=buffer,
                    file_name=f"{filename_prefix}_summary.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
    
    with col3:
        if st.button("📋 Export Full Data", use_container_width=True):
            # Export full attendance data
            export_df = df_display.copy()
            
            if export_format.startswith("CSV"):
                csv = export_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="⬇️ Download CSV",
                    data=csv,
                    file_name=f"{filename_prefix}_detailed.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            else:
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                    # Summary sheet
                    summary_data = {
                        'Report Period': [f"{start_date.strftime('%d %b %Y')} to {end_date.strftime('%d %b %Y')}"],
                        'Total Records': [total_records],
                        'Unique Participants': [total_participants],
                        'Session 1 Count': [session1_count],
                        'Session 2 Count': [session2_count]
                    }
                    summary_df = pd.DataFrame(summary_data)
                    summary_df.to_excel(writer, sheet_name='Summary', index=False)
                    
                    # Detailed data sheet
                    export_df.to_excel(writer, sheet_name='Detailed', index=False)
                    
                    # Frequency sheet
                    participant_stats.to_excel(writer, sheet_name='Frequency', index=False)
                
                buffer.seek(0)
                st.download_button(
                    label="⬇️ Download Excel",
                    data=buffer,
                    file_name=f"{filename_prefix}_attendance.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
    
    st.divider()
    
    # ============== QUICK FILTERS ==============
    st.subheader("🔍 Quick Filters")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        filter_session = st.selectbox(
            "Filter by Session",
            ["All", "Session 1 Only", "Session 2 Only", "Both Sessions"]
        )
    
    with col2:
        search_name = st.text_input("Search by Name", placeholder="Type name...")
    
    with col3:
        show_only = st.selectbox(
            "Show",
            ["All Records", "Self Check-in Only", "Manual Only"]
        )
    
    # Apply filters
    filtered_df = df_display.copy()
    
    if filter_session == "Session 1 Only":
        filtered_df = filtered_df[filtered_df['Session 1'] == '✅']
    elif filter_session == "Session 2 Only":
        filtered_df = filtered_df[filtered_df['Session 2'] == '✅']
    elif filter_session == "Both Sessions":
        filtered_df = filtered_df[(filtered_df['Session 1'] == '✅') & (filtered_df['Session 2'] == '✅')]
    
    if search_name:
        filtered_df = filtered_df[filtered_df['Name'].str.contains(search_name, case=False, na=False)]
    
    # Display filtered results
    st.write(f"**Showing {len(filtered_df)} of {len(df_display)} records**")
    st.dataframe(
        filtered_df,
        use_container_width=True,
        hide_index=True
    )