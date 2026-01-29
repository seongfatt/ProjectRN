import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from config import supabase, DB_CONNECTED, refresh_data
import streamlit as st

def to_sgt(ts):
    try:
        dt = pd.to_datetime(ts)
        
        # Detect if running on Hugging Face (they set specific env vars)
        is_hf = st.secrets.get("SPACE_ID") is not None or os.environ.get("SPACE_ID") is not None
        
        if is_hf:
            # Hugging Face stores UTC, add 8 hours
            dt = dt + timedelta(hours=8)
        else:
            # Local PC - check if already has timezone
            if dt.tzinfo is None:
                # Local time stored, no conversion needed or add 8 if it's UTC stored locally
                pass
        
        return dt.strftime('%d %b %I:%M %p')
    except:
        return ts
    
def show_tab3(selected_date):
    st.header("📊 Reports & Analytics")
    
    # ADD REFRESH BUTTON
    col1, col2 = st.columns([3, 1])
    with col1:
        st.caption(f"Showing data for: {selected_date}")
    with col2:
        if st.button("🔄 Refresh Data", use_container_width=True):
            refresh_data()  # Clear all caches
            st.rerun()
    
    if not DB_CONNECTED:
        st.error("Database not connected")
        return
    
    # TODAY'S ATTENDANCE - NO CACHING (Real-time)
    st.subheader("📅 Today's Attendance")
    
    try:
        # Direct query without caching
        today_data = supabase.table('attendance')\
            .select("*")\
            .eq('date', str(selected_date))\
            .order('timestamp', desc=True)\
            .execute()
        
        if today_data.data:
            df = pd.DataFrame(today_data.data)
            
            # Convert to Singapore Time
            def to_sgt(ts):
                try:
                    dt = pd.to_datetime(ts)
                    if dt.tzinfo is None:
                        dt = dt + timedelta(hours=8)
                    return dt.strftime('%d %b %I:%M %p')
                except:
                    return ts
            
            if 'timestamp' in df.columns:
                df['Time (SGT)'] = df['timestamp'].apply(to_sgt)
            
            # Stats
            c1, c2, c3 = st.columns(3)
            c1.metric("Total", len(df))
            c2.metric("Session 1", int(df['session_1'].sum()))
            c3.metric("Session 2", int(df['session_2'].sum()))
            
            # Show table
            display_cols = ['name', 'session_1', 'session_2', 'Time (SGT)']
            if 'source' in df.columns:
                display_cols.append('source')
            
            st.dataframe(df[display_cols], use_container_width=True, hide_index=True)
            
            # Download
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download CSV", csv, f"attendance_{selected_date}.csv", "text/csv")
        else:
            st.info("No records for this date yet")
            st.caption("Tip: Use Import tab to add WhatsApp poll data, or Check-In tab for manual entry")
            
    except Exception as e:
        st.error(f"Error loading data: {e}")
    
    # SUMMARY STATS
    st.divider()
    st.subheader("📈 Quick Summary")
    
    try:
        # Count by source
        all_data = supabase.table('attendance')\
            .select('source')\
            .eq('date', str(selected_date))\
            .execute()
        
        if all_data.data:
            sources = pd.DataFrame(all_data.data)
            if 'source' in sources.columns:
                counts = sources['source'].value_counts()
                cols = st.columns(len(counts))
                for idx, (source, count) in enumerate(counts.items()):
                    with cols[idx]:
                        label = "WhatsApp Import" if source == "whatsapp_import" else "Manual Check-in"
                        st.metric(label, count)
    except:
        pass

def to_sgt(ts):
    try:
        # Parse the timestamp
        dt = pd.to_datetime(ts)
        
        # If it has timezone info (like +00:00 from UTC), convert to SGT
        if dt.tzinfo is not None:
            # Convert from UTC to SGT (+8 hours)
            dt = dt.tz_convert('Asia/Singapore')
        else:
            # No timezone, assume it's UTC and add 8 hours
            dt = dt + timedelta(hours=8)
        
        return dt.strftime('%d %b %I:%M %p')
    except:
        return str(ts)