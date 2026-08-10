import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from config import supabase, DB_CONNECTED, load_activities

def show_dashboard():
    """
    POWER BI-STYLE PDPA-COMPLIANT DASHBOARD
    Shows meaningful activity metrics with trends and capacity utilization
    """
    
    # Modern CSS
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
        min-height: 150px;
        display: flex;
        flex-direction: column;
        justify-content: center;
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
    .activity-card {
        background: white;
        border-radius: 15px;
        padding: 20px;
        margin: 15px 0;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        border-left: 5px solid #667eea;
    }
    .activity-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 15px;
    }
    .activity-name {
        font-size: 20px;
        font-weight: 700;
        color: #1a1a1a;
    }
    .activity-badge {
        padding: 5px 15px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
    }
    .badge-excellent { background: #4CAF50; color: white; }
    .badge-good { background: #8BC34A; color: white; }
    .badge-warning { background: #FFC107; color: #1a1a1a; }
    .badge-poor { background: #f44336; color: white; }
    .progress-container {
        background: #e0e0e0;
        border-radius: 10px;
        height: 30px;
        overflow: hidden;
        margin: 10px 0;
        position: relative;
    }
    .progress-bar {
        height: 100%;
        display: flex;
        align-items: center;
        justify-content: flex-end;
        padding-right: 10px;
        color: white;
        font-weight: 600;
        transition: width 0.5s ease;
    }
    .progress-excellent { background: linear-gradient(90deg, #4CAF50 0%, #45a049 100%); }
    .progress-good { background: linear-gradient(90deg, #8BC34A 0%, #7cb342 100%); }
    .progress-warning { background: linear-gradient(90deg, #FFC107 0%, #ffb300 100%); }
    .progress-poor { background: linear-gradient(90deg, #f44336 0%, #e53935 100%); }
    .stats-row {
        display: flex;
        justify-content: space-around;
        margin-top: 15px;
        padding-top: 15px;
        border-top: 1px solid #e0e0e0;
    }
    .stat-item {
        text-align: center;
    }
    .stat-value {
        font-size: 24px;
        font-weight: 700;
        color: #667eea;
    }
    .stat-label {
        font-size: 11px;
        color: #666;
        text-transform: uppercase;
        margin-top: 5px;
    }
    .trend-indicator {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        font-size: 13px;
        font-weight: 600;
        margin-top: 8px;
    }
    .trend-up { color: #4CAF50; }
    .trend-down { color: #f44336; }
    .trend-stable { color: #FF9800; }
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
    
    st.title("📊 Community Hub Dashboard")
    st.caption("Real-time analytics and community insights - PDPA Compliant")
    
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
    
    # Calculate last week's data for comparison
    last_week_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    last_week_attendance = [a for a in attendance if a.get('date') == last_week_date]
    
    # ── ROW 1: KEY METRICS (4 Cards) ──────────────────
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
            <h3>👥 Total Residents</h3>
            <div class="number">{total_residents}</div>
            <div class="trend">Active members</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        trend_icon = "📈" if checkin_change > 0 else ("📉" if checkin_change < 0 else "️")
        trend_text = f"{trend_icon} {abs(checkin_change):.1f}% vs last week" if last_week_checkins > 0 else "No comparison data"
        st.markdown(f"""
        <div class="metric-card" style="background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%);">
            <h3>✅ Today's Check-Ins</h3>
            <div class="number">{today_checkins}</div>
            <div class="trend">{trend_text}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="metric-card" style="background: linear-gradient(135deg, #FF9800 0%, #f57c00 100%);">
            <h3> Active Sessions</h3>
            <div class="number">{active_sessions}</div>
            <div class="trend">Open now</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
        <div class="metric-card" style="background: linear-gradient(135deg, #2196F3 0%, #1976D2 100%);">
            <h3>🌱 Garden Occupied</h3>
            <div class="number">{garden_occupied}/76</div>
            <div class="trend">{garden_percentage:.0f}% capacity</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.divider()
    
    # ── ROW 2: ACTIVITY PERFORMANCE WITH CAPACITY & TRENDS ──────────────────
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
        
        for act_name, stats in sorted_activities[:8]:
            total_attendance = stats['total']
            unique_days = len(stats['dates'])
            avg_per_day = total_attendance / unique_days if unique_days > 0 else 0
            
            # Calculate capacity percentage (assuming 40 max per session)
            capacity_percentage = min((total_attendance / 40 * 100), 100)
            
            # Determine performance level
            if capacity_percentage >= 80:
                badge_color = "#4CAF50"
                badge_text = "Excellent"
                bar_color = "#4CAF50"
            elif capacity_percentage >= 60:
                badge_color = "#8BC34A"
                badge_text = "Good"
                bar_color = "#8BC34A"
            elif capacity_percentage >= 40:
                badge_color = "#FFC107"
                badge_text = "Moderate"
                bar_color = "#FFC107"
            else:
                badge_color = "#f44336"
                badge_text = "Needs Attention"
                bar_color = "#f44336"
            
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
            
            # Use Streamlit components instead of raw HTML
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"**{act_name}**")
                st.progress(capacity_percentage / 100)
            with col2:
                st.markdown(f'<div style="background:{badge_color};color:white;padding:8px 15px;border-radius:20px;text-align:center;font-weight:bold;">{badge_text}</div>', unsafe_allow_html=True)
            
            # Stats row
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Check-ins", total_attendance)
            c2.metric("Active Days", unique_days)
            c3.metric("Avg/Day", f"{avg_per_day:.1f}")
            c4.metric("Last Week", last_week_count)
            
            st.markdown(f'<div style="color:{trend_color};font-weight:600;margin:10px 0;">{trend_icon} {trend_text} vs last week</div>', unsafe_allow_html=True)
            st.divider()
    else:
        st.info("No attendance data available yet.")
    
    st.divider()
    
    # ── ROW 3: RECENT ACTIVITY (PDPA-Compliant Timeline) ─────────────────
    st.subheader("📝 Recent Activity (Last 30 Minutes)")
    st.caption(" PDPA Compliant: Only aggregate counts shown, no personal names")
    
    if attendance:
        # Get last 10 check-ins, grouped by time and activity
        recent_attendance = sorted(attendance, key=lambda x: x.get('timestamp', ''), reverse=True)[:10]
        
        # Group by 15-minute intervals
        time_groups = {}
        for att in recent_attendance:
            timestamp = att.get('timestamp', '')
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    # Round to 15-minute intervals
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
            for key, data in sorted(time_groups.items(), reverse=True)[:8]:
                st.markdown(f"""
                <div class="timeline-item">
                    <div class="timeline-time">{data['time']}</div>
                    <div class="timeline-text">
                        ✅ <strong>{data['count']} resident(s)</strong> checked in - {data['activity']}
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No recent activity in the last 30 minutes.")
    else:
        st.info("No attendance data available.")
    
    st.divider()
    
    # ── ROW 4: QUICK INSIGHTS & RECOMMENDATIONS ──────────────────
    st.subheader("💡 Key Insights & Recommendations")
    
    if attendance:
        # Find most popular activity
        if sorted_activities:
            top_activity = sorted_activities[0][0]
            top_count = sorted_activities[0][1]['total']
            st.success(f"🏆 **Most Popular Activity:** {top_activity} with {top_count} total check-ins")
        
        # Find activities needing attention
        low_performers = [act for act, stats in activity_stats.items() 
                         if (stats['total'] / max(len(stats['dates']), 1)) < 5]
        if low_performers:
            st.warning(f"⚠️ **Activities Needing Attention:** {', '.join(low_performers)} - Consider promoting these activities")
        
        # Garden occupancy insight
        if garden_percentage >= 90:
            st.info("🌱 **Garden Status:** Nearly full ({:.0f}% occupied). Consider expanding or creating waiting list.".format(garden_percentage))
        elif garden_percentage >= 70:
            st.info("🌱 **Garden Status:** Good occupancy ({:.0f}%). Healthy utilization.".format(garden_percentage))
        else:
            st.info(" **Garden Status:** Room for growth ({:.0f}% occupied). Consider outreach to fill plots.".format(garden_percentage))
    else:
        st.info("Insufficient data for insights yet.")
    
    st.caption(" Dashboard auto-refreshes when you navigate away and back")

    # ═══════════════════════════════════════════════════════
    # COMMUNITY MEMBERSHIP BREAKDOWN
    # ═══════════════════════════════════════════════════════
    st.subheader("👥 Community Membership Breakdown")

    # Filter active participants for accurate percentages
    active_participants = [p for p in st.session_state.participants if p.get('active', True)]
    total_active = len(active_participants)

    # Count member types (defaults to 'Resident' if not set yet)
    resident_count = sum(1 for p in active_participants if p.get('member_type', 'Resident') == 'Resident')
    rn_count = sum(1 for p in active_participants if p.get('member_type') == 'RN Member')
    volunteer_count = sum(1 for p in active_participants if p.get('member_type') == 'Volunteer Member')

    # Calculate percentages safely
    res_pct = (resident_count / total_active * 100) if total_active > 0 else 0
    rn_pct = (rn_count / total_active * 100) if total_active > 0 else 0
    vol_pct = (volunteer_count / total_active * 100) if total_active > 0 else 0

    # Display top-level metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Members", total_active)
    c2.metric(" Residents", resident_count, f"{res_pct:.1f}%")
    c3.metric("️ RN Members", rn_count, f"{rn_pct:.1f}%")
    c4.metric(" Volunteers", volunteer_count, f"{vol_pct:.1f}%")

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