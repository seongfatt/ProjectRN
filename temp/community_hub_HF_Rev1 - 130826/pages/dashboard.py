import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone
from config import supabase, DB_CONNECTED, load_activities
from services import AnalyticsService

# Optional: For charts (install: pip install plotly)
try:
    import plotly.express as px
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

def show_dashboard():
    """
    POWER BI-STYLE PDPA-COMPLIANT DASHBOARD
    Shows meaningful activity metrics with trends and capacity utilization
    """
    
    # ===== MODERN CSS =====
    st.markdown("""
    <style>
        /* ── Metric Cards ── */
        .metric-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 15px;
            padding: 20px;
            color: white;
            text-align: center;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
            margin: 10px 0;
            min-height: 120px;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }
        .metric-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 8px 25px rgba(102, 126, 234, 0.4);
        }
        .metric-card .number {
            font-size: 36px;
            font-weight: 800;
            margin: 5px 0;
        }
        .metric-card .label {
            font-size: 13px;
            opacity: 0.9;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .metric-card .trend {
            font-size: 12px;
            opacity: 0.8;
            margin-top: 5px;
        }
        .metric-green { background: linear-gradient(135deg, #11998e, #38ef7d); }
        .metric-orange { background: linear-gradient(135deg, #f093fb, #f5576c); }
        .metric-blue { background: linear-gradient(135deg, #4facfe, #00f2fe); }
        .metric-purple { background: linear-gradient(135deg, #a18cd1, #fbc2eb); }
        .metric-gold { background: linear-gradient(135deg, #f7971e, #ffd200); }
        
        /* ── Timeline Items ── */
        .timeline-item {
            display: flex;
            align-items: center;
            gap: 15px;
            padding: 12px 15px;
            border-left: 3px solid #667eea;
            margin: 8px 0;
            background: #f8f9fa;
            border-radius: 0 8px 8px 0;
            transition: background 0.2s ease;
        }
        .timeline-item:hover {
            background: #e8ecf1;
        }
        .timeline-time {
            font-size: 12px;
            color: #666;
            font-weight: 600;
            min-width: 80px;
        }
        .timeline-text {
            font-size: 14px;
            color: #1a1a1a;
            flex: 1;
        }
        .timeline-badge {
            font-size: 12px;
            padding: 2px 12px;
            border-radius: 12px;
            font-weight: 600;
        }
        .badge-checkin { background: #4CAF50; color: white; }
        .badge-register { background: #2196F3; color: white; }
        
        /* ── Status Cards ── */
        .status-card {
            border-radius: 10px;
            padding: 15px;
            text-align: center;
            border-left: 4px solid #4CAF50;
            background: #f8f9fa;
            transition: transform 0.2s ease;
        }
        .status-card:hover {
            transform: scale(1.02);
        }
        .status-card .status-label {
            font-size: 11px;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .status-card .status-value {
            font-size: 16px;
            font-weight: 700;
            margin-top: 4px;
        }
        .status-green .status-value { color: #4CAF50; }
        .status-orange .status-value { color: #FF9800; }
        .status-red .status-value { color: #f44336; }
        .status-blue .status-value { color: #2196F3; }
        
        /* ── Quick Action Buttons ── */
        .quick-action-btn {
            text-align: center;
            padding: 15px;
            border-radius: 12px;
            background: white;
            border: 1px solid #e0e0e0;
            transition: all 0.3s ease;
            cursor: pointer;
        }
        .quick-action-btn:hover {
            border-color: #667eea;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.2);
            transform: translateY(-3px);
        }
        .quick-action-btn .icon {
            font-size: 28px;
        }
        .quick-action-btn .label {
            font-size: 12px;
            color: #555;
            margin-top: 5px;
        }
        
        /* ── Greeting Banner ── */
        .greeting-banner {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 15px;
            padding: 25px 30px;
            color: white;
            margin: 15px 0 25px 0;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
        }
        .greeting-banner .greeting-text {
            font-size: 24px;
            font-weight: 700;
        }
        .greeting-banner .greeting-sub {
            font-size: 14px;
            opacity: 0.85;
            margin-top: 4px;
        }
        .greeting-banner .greeting-date {
            font-size: 14px;
            opacity: 0.85;
            text-align: right;
        }
        
        /* ── Responsive ── */
        @media (max-width: 640px) {
            .metric-card .number { font-size: 28px; }
            .greeting-banner { flex-direction: column; text-align: center; }
            .greeting-banner .greeting-date { text-align: center; margin-top: 10px; }
            .timeline-item { flex-wrap: wrap; }
        }
    </style>
    """, unsafe_allow_html=True)
    
    # ===== GREETING BANNER =====
    now = datetime.now(timezone(timedelta(hours=8)))
    hour = now.hour
    
    if hour < 12:
        greeting = "🌅 Good Morning"
        emoji = "☀️"
    elif hour < 17:
        greeting = "☀️ Good Afternoon"
        emoji = "🌤️"
    else:
        greeting = "🌙 Good Evening"
        emoji = "🌙"
    
    role = st.session_state.get('user_role', 'Admin').capitalize()
    
    st.markdown(f"""
    <div class="greeting-banner">
        <div>
            <div class="greeting-text">{greeting}, {role}!</div>
            <div class="greeting-sub">{emoji} Welcome back. Here's what's happening today.</div>
        </div>
        <div class="greeting-date">
            {now.strftime('%A, %d %B %Y')}<br>
            <span style="font-size: 12px; opacity: 0.7;">{now.strftime('%I:%M %p')}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    if not DB_CONNECTED:
        st.error("Database not connected")
        return
    
    # ===== FETCH DATA =====
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
    
    # Calculate last week's data for comparison
    last_week_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    last_week_attendance = [a for a in attendance if a.get('date') == last_week_date]
    
    # ===== QUICK ACTION BUTTONS =====
    st.markdown("### ⚡ Quick Actions")
    
    q1, q2, q3, q4, q5 = st.columns(5)
    with q1:
        if st.button("🎟️ Check-In", use_container_width=True, type="primary"):
            st.session_state.active_page = "checkin"
            st.rerun()
    with q2:
        if st.button("👤 New Resident", use_container_width=True):
            st.session_state.active_page = "manage"
            st.rerun()
    with q3:
        if st.button("🌱 Garden", use_container_width=True):
            st.session_state.active_page = "garden"
            st.rerun()
    with q4:
        if st.button("📊 Reports", use_container_width=True):
            st.session_state.active_page = "reports"
            st.rerun()
    with q5:
        if st.button("📅 Sessions", use_container_width=True):
            st.session_state.active_page = "sessions"
            st.rerun()
    
    st.divider()
    
    # ===== ROW 1: KEY METRICS =====
    st.subheader("📈 Today's Overview")
    
    total_residents = len(participants)
    today_checkins = len(today_attendance)
    last_week_checkins = len(last_week_attendance)
    checkin_change = ((today_checkins - last_week_checkins) / last_week_checkins * 100) if last_week_checkins > 0 else 0
    
    active_sessions = len([s for s in sessions if s.get('status') == 'open'])
    garden_occupied = len([p for p in garden_plots if p.get('occupied')])
    garden_percentage = (garden_occupied / 76 * 100) if 76 > 0 else 0
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="label">👥 Total Residents</div>
            <div class="number">{total_residents}</div>
            <div class="trend">Active members</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        trend_icon = "📈" if checkin_change > 0 else ("📉" if checkin_change < 0 else "➡️")
        trend_text = f"{trend_icon} {abs(checkin_change):.1f}% vs last week" if last_week_checkins > 0 else "No comparison data"
        st.markdown(f"""
        <div class="metric-card metric-green">
            <div class="label">✅ Today's Check-Ins</div>
            <div class="number">{today_checkins}</div>
            <div class="trend">{trend_text}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="metric-card metric-orange">
            <div class="label">📅 Active Sessions</div>
            <div class="number">{active_sessions}</div>
            <div class="trend">Open now</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
        <div class="metric-card metric-blue">
            <div class="label">🌱 Garden Occupied</div>
            <div class="number">{garden_occupied}/76</div>
            <div class="trend">{garden_percentage:.0f}% capacity</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.divider()
    
    # ===== ROW 2: SYSTEM STATUS =====
    st.subheader("🔋 System Status")
    
    s1, s2, s3, s4 = st.columns(4)
    with s1:
        st.markdown("""
        <div class="status-card status-green">
            <div class="status-label">Database</div>
            <div class="status-value">🟢 Connected</div>
        </div>
        """, unsafe_allow_html=True)
    with s2:
        st.markdown("""
        <div class="status-card status-blue">
            <div class="status-label">Server</div>
            <div class="status-value">🟢 Running</div>
        </div>
        """, unsafe_allow_html=True)
    with s3:
        st.markdown("""
        <div class="status-card status-green">
            <div class="status-label">Session</div>
            <div class="status-value">🟢 Active</div>
        </div>
        """, unsafe_allow_html=True)
    with s4:
        alert_count = 0
        # Check for low attendance activities
        if attendance:
            for act in activities:
                act_attendance = [a for a in attendance if a.get('source') == act['name'] and a.get('date') == today]
                if len(act_attendance) < 3:
                    alert_count += 1
        st.markdown(f"""
        <div class="status-card status-{'red' if alert_count > 0 else 'green'}">
            <div class="status-label">Alerts</div>
            <div class="status-value">{'🔴 ' + str(alert_count) if alert_count > 0 else '🟢 0'}</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.divider()
    
    # ===== ROW 3: ACTIVITY PERFORMANCE =====
    st.subheader("📊 Activity Performance Analysis")
    st.caption("Shows capacity utilization and week-over-week trends")

    if attendance:
        # Group attendance by activity
        activity_stats = {}
        for att in attendance:
            act = att.get('source', 'Unknown')
            if act not in activity_stats:
                activity_stats[act] = {'total': 0, 'dates': set()}
            activity_stats[act]['total'] += 1
            activity_stats[act]['dates'].add(att.get('date'))
        
        # Calculate last week's stats for comparison
        last_week_stats = {}
        for att in last_week_attendance:
            act = att.get('source', 'Unknown')
            if act not in last_week_stats:
                last_week_stats[act] = 0
            last_week_stats[act] += 1
        
        # Sort by total attendance
        sorted_activities = sorted(activity_stats.items(), key=lambda x: x[1]['total'], reverse=True)
        
        for act_name, stats in sorted_activities[:6]:
            total_attendance = stats['total']
            unique_days = len(stats['dates'])
            avg_per_day = total_attendance / unique_days if unique_days > 0 else 0
            
            # Calculate capacity percentage (assuming 40 max per session)
            capacity_percentage = min((total_attendance / 40 * 100), 100)
            
            # Determine performance level
            if capacity_percentage >= 80:
                badge_color = "#4CAF50"
                badge_text = "🌟 Excellent"
            elif capacity_percentage >= 60:
                badge_color = "#8BC34A"
                badge_text = "✅ Good"
            elif capacity_percentage >= 40:
                badge_color = "#FFC107"
                badge_text = "📊 Moderate"
            else:
                badge_color = "#f44336"
                badge_text = "⚠️ Needs Attention"
            
            # Calculate trend
            last_week_count = last_week_stats.get(act_name, 0)
            if last_week_count > 0:
                trend_pct = ((total_attendance - last_week_count) / last_week_count * 100)
                if trend_pct > 5:
                    trend_icon = "📈"
                    trend_color = "#4CAF50"
                    trend_text = f"Up {trend_pct:.0f}%"
                elif trend_pct < -5:
                    trend_icon = "📉"
                    trend_color = "#f44336"
                    trend_text = f"Down {abs(trend_pct):.0f}%"
                else:
                    trend_icon = "➡️"
                    trend_color = "#FF9800"
                    trend_text = "Stable"
            else:
                trend_icon = "🆕"
                trend_color = "#2196F3"
                trend_text = "New Activity"
            
            # Display activity card
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"**{act_name}**")
                st.progress(capacity_percentage / 100)
            with col2:
                st.markdown(f'<div style="background:{badge_color};color:white;padding:6px 12px;border-radius:20px;text-align:center;font-weight:bold;font-size:13px;">{badge_text}</div>', unsafe_allow_html=True)
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Check-ins", total_attendance)
            c2.metric("Active Days", unique_days)
            c3.metric("Avg/Day", f"{avg_per_day:.1f}")
            c4.metric("Last Week", last_week_count)
            
            st.markdown(f'<div style="color:{trend_color};font-weight:600;margin:5px 0 15px 0;">{trend_icon} {trend_text} vs last week</div>', unsafe_allow_html=True)
    else:
        st.info("No attendance data available yet.")
    
    st.divider()
    
    # ===== ROW 4: RECENT ACTIVITY =====
    st.subheader("📝 Recent Activity")
    st.caption("PDPA Compliant: Only aggregate counts shown")
    
    if attendance:
        recent_attendance = sorted(attendance, key=lambda x: x.get('timestamp', ''), reverse=True)[:10]
        
        time_groups = {}
        for att in recent_attendance:
            timestamp = att.get('timestamp', '')
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    minute = (dt.minute // 15) * 15
                    time_key = dt.replace(minute=minute, second=0, microsecond=0)
                    time_str = time_key.strftime("%I:%M %p")
                    
                    activity = att.get('source', 'Unknown')
                    key = f"{time_str}|{activity}"
                    
                    if key not in time_groups:
                        time_groups[key] = {'time': time_str, 'activity': activity, 'count': 0}
                    time_groups[key]['count'] += 1
                except:
                    pass
        
        if time_groups:
            for key, data in sorted(time_groups.items(), reverse=True)[:6]:
                st.markdown(f"""
                <div class="timeline-item">
                    <span class="timeline-time">🕐 {data['time']}</span>
                    <span class="timeline-text">✅ <strong>{data['count']} resident(s)</strong> checked in</span>
                    <span class="timeline-badge badge-checkin">{data['activity']}</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No recent activity.")
    else:
        st.info("No attendance data available.")
    
    st.divider()
    
    # ===== ROW 5: CHARTS =====
    if PLOTLY_AVAILABLE and attendance:
        st.subheader("📈 Weekly Trends")
        
        # Prepare data
        daily_data = {}
        for att in attendance:
            date = att.get('date', '')
            if date:
                daily_data[date] = daily_data.get(date, 0) + 1
        
        if daily_data:
            df = pd.DataFrame(list(daily_data.items()), columns=['Date', 'Check-ins'])
            df['Date'] = pd.to_datetime(df['Date'])
            df = df.sort_values('Date').tail(14)  # Last 14 days
            
            fig = px.line(df, x='Date', y='Check-ins', 
                         title='Daily Check-ins (Last 14 Days)',
                         markers=True, template='plotly_white')
            fig.update_layout(height=300, margin=dict(l=0, r=0, t=40, b=0))
            st.plotly_chart(fig, use_container_width=True)
    
    st.divider()
    
    # ===== ROW 6: INSIGHTS & RECOMMENDATIONS =====
    st.subheader("💡 Key Insights & Recommendations")
    
    if attendance:
        if sorted_activities:
            top_activity = sorted_activities[0][0]
            top_count = sorted_activities[0][1]['total']
            st.success(f"🏆 **Most Popular Activity:** {top_activity} with {top_count} total check-ins")
        
        low_performers = [act for act, stats in activity_stats.items() 
                         if (stats['total'] / max(len(stats['dates']), 1)) < 5]
        if low_performers:
            st.warning(f"⚠️ **Activities Needing Attention:** {', '.join(low_performers)}")
        
        if garden_percentage >= 90:
            st.info(f"🌱 **Garden Status:** Nearly full ({garden_percentage:.0f}% occupied).")
        elif garden_percentage >= 70:
            st.info(f"🌱 **Garden Status:** Good occupancy ({garden_percentage:.0f}%).")
        else:
            st.info(f"🌱 **Garden Status:** Room for growth ({garden_percentage:.0f}%).")
    
    st.divider()
    
    # ===== COMMUNITY MEMBERSHIP BREAKDOWN =====
    st.subheader("👥 Community Membership Breakdown")

    breakdown = AnalyticsService.get_member_breakdown(st.session_state.participants)
    resident_count = breakdown['resident']
    rn_count = breakdown['rn']
    volunteer_count = breakdown['volunteer']
    res_pct = breakdown['resident_pct']
    rn_pct = breakdown['rn_pct']
    vol_pct = breakdown['volunteer_pct']
    total_active = breakdown['total']

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Members", total_active)
    c2.metric("🏠 Residents", resident_count, f"{res_pct:.1f}%")
    c3.metric("🏘️ RN Members", rn_count, f"{rn_pct:.1f}%")
    c4.metric("🤝 Volunteers", volunteer_count, f"{vol_pct:.1f}%")

    st.markdown("---")

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

    st.html(progress_html)
    st.divider()
    
    st.caption("📊 Dashboard auto-refreshes when you navigate away and back")