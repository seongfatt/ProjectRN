# services/analytics_service.py
"""Analytics service — member breakdowns, activity stats, etc."""

from config import supabase, DB_CONNECTED, PLOT_TYPES

class AnalyticsService:
    """Handles analytics and reporting."""
    
    @staticmethod
    def get_member_breakdown(participants):
        """Get breakdown of member types."""
        active = [p for p in participants if p.get('active', True)]
        total = len(active)
        
        resident_count = sum(1 for p in active if p.get('member_type', 'Resident') == 'Resident')
        rn_count = sum(1 for p in active if p.get('member_type') == 'RN Member')
        volunteer_count = sum(1 for p in active if p.get('member_type') == 'Volunteer Member')
        
        return {
            'total': total,
            'resident': resident_count,
            'rn': rn_count,
            'volunteer': volunteer_count,
            'resident_pct': (resident_count / total * 100) if total > 0 else 0,
            'rn_pct': (rn_count / total * 100) if total > 0 else 0,
            'volunteer_pct': (volunteer_count / total * 100) if total > 0 else 0,
        }
    
    @staticmethod
    def render_member_breakdown_html(breakdown):
        """Generate HTML progress bars for member breakdown."""
        return f"""
        <div style="background: #f8f9fa; padding: 15px; border-radius: 10px; margin-bottom: 20px; font-family: 'Segoe UI', sans-serif;">
            <div style="margin-bottom: 14px;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                    <span style="font-weight: 600; color: #555;">🏠 Residents</span>
                    <span style="font-weight: 600; color: #1a1a1a;">{breakdown['resident_pct']:.1f}% ({breakdown['resident']})</span>
                </div>
                <div style="background: #e9ecef; border-radius: 6px; height: 14px; overflow: hidden;">
                    <div style="background: linear-gradient(90deg, #6c757d, #adb5bd); width: {breakdown['resident_pct']:.1f}%; height: 100%; border-radius: 6px;"></div>
                </div>
            </div>
            <div style="margin-bottom: 14px;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                    <span style="font-weight: 600; color: #555;">🏘️ RN Members</span>
                    <span style="font-weight: 600; color: #1a1a1a;">{breakdown['rn_pct']:.1f}% ({breakdown['rn']})</span>
                </div>
                <div style="background: #e9ecef; border-radius: 6px; height: 14px; overflow: hidden;">
                    <div style="background: linear-gradient(90deg, #0d6efd, #6ea8fe); width: {breakdown['rn_pct']:.1f}%; height: 100%; border-radius: 6px;"></div>
                </div>
            </div>
            <div>
                <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                    <span style="font-weight: 600; color: #555;">🤝 Volunteers</span>
                    <span style="font-weight: 600; color: #1a1a1a;">{breakdown['volunteer_pct']:.1f}% ({breakdown['volunteer']})</span>
                </div>
                <div style="background: #e9ecef; border-radius: 6px; height: 14px; overflow: hidden;">
                    <div style="background: linear-gradient(90deg, #198754, #75b798); width: {breakdown['volunteer_pct']:.1f}%; height: 100%; border-radius: 6px;"></div>
                </div>
            </div>
        </div>
        """