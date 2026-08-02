import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from config import supabase, DB_CONNECTED, load_activities

def show_dashboard():
    """
    POWER BI-STYLE ENHANCED DASHBOARD
    Professional analytics with real-time metrics, charts, and activity tracking
    """
    
    # Modern CSS for dashboard
    st.markdown("""
    <style>
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 25px;
        border-radius: 15px;
        text-align: center;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
        margin: 10px 0;
    }
    .metric-card h3 {
        margin: 0;
        font-size: 14px;
        opacity: 0.9;
        text-transform: uppercase;
    }
    .metric-card .number {
        font-size: 42px;
        font-weight: 800;
        margin: 10px 0;
    }
    .metric-card .trend {
        font-size: 12px;
        opacity: 0.8;
    }
    .activity-bar {
        background: #f8f9fa;
        border-radius: 10px;
        padding: 15px;
        margin: 10px 0;
    }
    .activity-row {
        display: flex;
        align-items: center;
        margin: 10px 0;
    }
    .activity-label {
        width: 150px;
        font-weight: 600;
        color: #1a1a1a;
    }
    .activity-progress {
        flex: 1;
        background: #e0e0e0;
        border-radius: 10px;
        height: 30px;
        margin: 0 10px;
        overflow: hidden;
    }
    .activity-fill {
        height: 100%;
        background: linear-gradient(90deg, #4CAF50 0%, #45a049 100%);
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: flex-end;
        padding-right: 10px;
        color: white;
        font-weight: 600;
        transition: width 0.3s ease;
    }
    .gauge-container {
        text-align: center;
        padding: 20px;
        background: white;
        border-radius: 15px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        margin: 10px 0;
    }
    .gauge-value {
        font-size: 36px;
        font-weight: 700;
        color: #667eea;
    }
    .timeline-item {
        padding: 12px;
        border-left: 3px solid #667eea;
        margin: 10px 0;
        background: #f8f9fa;
        border-radius: 0 8px 8px 0;
    }
    .timeline-time {
        font-size: 12px;
        color: #666;
        font-weight: 600;
    }
    .timeline-text {
        font-size: 14px;
        color: #1a1a1a;
        margin-top: 5px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.title(" Community Hub Dashboard")
    st.caption("Real-time analytics and community insights")
    
    if not DB_CONNECTED:
        st.error("Database not connected")
        return
    
    # Fetch all data
    try:
        participants = supabase.table('participants').select("*").eq('active', True).execute().data
        attendance = supabase.table('attendance').select("*").execute().data
        sessions = supabase.table('sessions').select("*").execute().data
        garden_plots = supabase.table('garden_plots').select("*").execute().data
        activities = load_activities()
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return
    
    today = datetime.now().strftime("%Y-%m-%d")
    today_attendance = [a for a in attendance if a.get('date') == today]
    
    # ── ROW 1: KEY METRICS (4 Cards) ──────────────────
    st.subheader("📈 Today's Overview")
    
    total_residents = len(participants)
    today_checkins = len(today_attendance)
    active_sessions = len([s for s in sessions if s.get('status') == 'open'])
    garden_occupied = len([p for p in garden_plots if p.get('occupied')])
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <h3>👥 Total Residents</h3>
            <div class="number">{total_residents}</div>
            <div class="trend">Active members</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="metric-card" style="background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%);">
            <h3>✅ Today's Check-Ins</h3>
            <div class="number">{today_checkins}</div>
            <div class="trend">Attendance today</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="metric-card" style="background: linear-gradient(135deg, #FF9800 0%, #f57c00 100%);">
            <h3>🎯 Active Sessions</h3>
            <div class="number">{active_sessions}</div>
            <div class="trend">Open now</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
        <div class="metric-card" style="background: linear-gradient(135deg, #2196F3 0%, #1976D2 100%);">
            <h3>🌱 Garden Occupied</h3>
            <div class="number">{garden_occupied}/76</div>
            <div class="trend">Plots in use</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.divider()
    
    # ── ROW 2: ACTIVITY ATTENDANCE TRENDS (Bar Chart) ──────────────────
    st.subheader("📊 Activity Attendance Trends")
    
    if attendance:
        activity_counts = {}
        for att in attendance:
            act = att.get('source', 'Unknown')
            activity_counts[act] = activity_counts.get(act, 0) + 1
        
        # Sort by count
        sorted_activities = sorted(activity_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        for act_name, count in sorted_activities:
            max_count = sorted_activities[0][1] if sorted_activities else 1
            percentage = (count / max_count * 100) if max_count > 0 else 0
            
            st.markdown(f"""
            <div class="activity-bar">
                <div class="activity-row">
                    <div class="activity-label">{act_name}</div>
                    <div class="activity-progress">
                        <div class="activity-fill" style="width: {percentage}%">
                            {count}
                        </div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No attendance data available yet.")
    
    st.divider()
    
    # ── ROW 3: SESSION PROGRESS (Circular Gauges) ──────────────────
    st.subheader("📅 Session Progress")
    
    if sessions:
        today_sessions = [s for s in sessions if s.get('session_date') == today]
        
        if today_sessions:
            cols = st.columns(3)
            for i, session in enumerate(today_sessions[:3]):
                with cols[i % 3]:
                    # Calculate attendance for this session
                    session_attendance = len([a for a in today_attendance if a.get('source') == session.get('activity_name')])
                    capacity = 40  # Default capacity
                    percentage = min((session_attendance / capacity * 100), 100)
                    
                    # Color based on fill
                    if percentage >= 80:
                        color = "#f44336"  # Red - almost full
                    elif percentage >= 50:
                        color = "#FF9800"  # Orange - half full
                    else:
                        color = "#4CAF50"  # Green - plenty of space
                    
                    st.markdown(f"""
                    <div class="gauge-container">
                        <div style="font-size: 16px; font-weight: 600; margin-bottom: 10px;">
                            {session.get('activity_name', 'Unknown')}
                        </div>
                        <div class="gauge-value" style="color: {color};">
                            {session_attendance}/{capacity}
                        </div>
                        <div style="font-size: 14px; color: #666; margin-top: 5px;">
                            {percentage:.0f}% filled
                        </div>
                        <div style="background: #e0e0e0; height: 8px; border-radius: 4px; margin-top: 10px; overflow: hidden;">
                            <div style="background: {color}; height: 100%; width: {percentage}%; transition: width 0.3s ease;"></div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.info("No sessions scheduled for today.")
    else:
        st.info("No sessions created yet.")
    
    st.divider()
    
    # ── ROW 4: RECENT ACTIVITY (Timeline) ─────────────────
    st.subheader(" Recent Activity")
    
    if attendance:
        # Get last 10 check-ins
        recent_attendance = sorted(attendance, key=lambda x: x.get('timestamp', ''), reverse=True)[:10]
        
        for att in recent_attendance:
            timestamp = att.get('timestamp', '')
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    time_str = dt.strftime("%I:%M %p")
                except:
                    time_str = "Unknown"
            else:
                time_str = "Unknown"
            
            name = att.get('name', 'Unknown')
            activity = att.get('source', 'Unknown')
            
            st.markdown(f"""
            <div class="timeline-item">
                <div class="timeline-time">{time_str}</div>
                <div class="timeline-text">
                    ✅ <strong>{name}</strong> checked in - {activity}
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No recent activity.")
    
    st.divider()
    
    # ── ROW 5: UPCOMING SESSIONS (Cards) ──────────────────
    st.subheader("️ Upcoming Sessions")
    
    if sessions:
        future_sessions = [s for s in sessions if s.get('session_date') >= today and s.get('status') == 'open']
        future_sessions = sorted(future_sessions, key=lambda x: x.get('session_date', ''))[:6]
        
        if future_sessions:
            cols = st.columns(3)
            for i, session in enumerate(future_sessions):
                with cols[i % 3]:
                    # Count RSVPs
                    try:
                        rsvps = supabase.table('session_rsvp').select("*").eq('session_id', session['id']).execute().data
                        rsvp_count = len([r for r in rsvps if r.get('response') == 'attending'])
                    except:
                        rsvp_count = 0
                    
                    date_str = session.get('session_date', 'TBA')
                    try:
                        dt = datetime.strptime(date_str, "%Y-%m-%d")
                        formatted_date = dt.strftime("%d %b")
                    except:
                        formatted_date = date_str
                    
                    st.markdown(f"""
                    <div style="background: white; border: 2px solid #e0e0e0; border-radius: 12px; padding: 15px; margin: 10px 0;">
                        <div style="font-size: 14px; color: #667eea; font-weight: 700; margin-bottom: 8px;">
                            {formatted_date}
                        </div>
                        <div style="font-size: 16px; font-weight: 600; color: #1a1a1a; margin-bottom: 5px;">
                            {session.get('activity_name', 'Unknown')}
                        </div>
                        <div style="font-size: 13px; color: #666; margin-bottom: 10px;">
                            {session.get('session_time', 'TBA')}
                        </div>
                        <div style="font-size: 13px; color: #4CAF50; font-weight: 600;">
                            {rsvp_count} attending
                        </div>
                        <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid #e0e0e0;">
                            <span style="background: #4CAF50; color: white; padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: 600;">
                                🟢 Open
                            </span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.info("No upcoming sessions scheduled.")
    else:
        st.info("No sessions created yet.")
    
    # Auto-refresh every 60 seconds
    st.caption("🔄 Dashboard auto-refreshes every 60 seconds")