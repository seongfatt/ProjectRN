# services/attendance_service.py
"""Unified attendance service — eliminates duplicate check-in logic"""

import streamlit as st
from datetime import datetime
from config import supabase, DB_CONNECTED, now_sgt, load_activities, refresh_data  # ← ADD refresh_data here
from utils import validate_checkin_time, sync_session_attendance_async

class AttendanceService:
    """Handles all check-in operations with S1-S4 session support."""
    
    @staticmethod
    def get_session_labels(activity_name):
        """Get dynamic session labels (1-4 sessions)."""
        acts = load_activities()
        act_config = next((a for a in acts if a['name'] == activity_name), None)
        labels = []
        if act_config:
            for i in range(1, 5):
                lbl = (act_config.get(f'session_{i}_label') or '').strip()
                if lbl:
                    labels.append(lbl)
        return labels or ['Session 1']
    
    @staticmethod
    def process_checkin(pid, date, activity, s1, s2, s3=False, s4=False):
        """
        Core check-in logic — supports 1-4 sessions.
        Returns: (success: bool, message: str, resident: dict)
        """
        try:
            selected = [s1, s2, s3, s4]
            
            # Format date
            if isinstance(date, str):
                if len(date) == 8 and date.isdigit():
                    formatted_date = datetime.strptime(date, "%Y%m%d").strftime("%Y-%m-%d")
                else:
                    formatted_date = date
            else:
                formatted_date = date.strftime("%Y-%m-%d")
            
            # Get resident
            res = supabase.table('participants').select("*").eq('id', pid).execute()
            if not res.data:
                return False, f"❌ Resident ID not found: {pid}", None
            resident = res.data[0]
            
            # Check existing attendance
            existing = supabase.table('attendance').select("*") \
                .eq('participant_id', pid).eq('date', formatted_date).eq('source', activity).execute()
            
            if existing.data and len(existing.data) > 0:
                record = existing.data[0]
                missing = [i + 1 for i, f in enumerate(selected) if f and not record.get(f'session_{i + 1}', False)]
                
                if not missing:
                    return False, f"ℹ️ **{resident['name']}** is already fully checked in for {activity} today.", resident
                
                # Validate time for the first missing session
                is_allowed, message = validate_checkin_time(activity, missing[0])
                if not is_allowed:
                    return False, message, resident
                
                # Update with missing sessions
                updates = {"timestamp": now_sgt().isoformat()}
                for n in missing:
                    updates[f'session_{n}'] = True
                current_activities = record.get('activities') or []
                if activity not in current_activities:
                    current_activities.append(activity)
                updates['activities'] = current_activities
                
                supabase.table('attendance').update(updates).eq('id', record['id']).execute()
                refresh_data()
                
                sync_session_attendance_async(pid, resident['name'], activity, formatted_date,
                                              st.session_state.get('user_role', 'system'))
                
                return True, f"✅ Updated **{resident['name']}** with additional session(s)!", resident
            
            # New check-in
            first_selected = next((i + 1 for i, f in enumerate(selected) if f), 1)
            is_allowed, message = validate_checkin_time(activity, first_selected)
            if not is_allowed:
                return False, message, resident
            
            # Insert new attendance
            supabase.table('attendance').insert({
                "participant_id": pid,
                "name": resident['name'],
                "date": formatted_date,
                "session_1": s1,
                "session_2": s2,
                "session_3": s3,
                "session_4": s4,
                "timestamp": now_sgt().isoformat(),
                "self_checkin": False,
                "source": activity,
                "activities": [activity]
            }).execute()
            refresh_data()
            
            sync_session_attendance_async(pid, resident['name'], activity, formatted_date,
                                          st.session_state.get('user_role', 'system'))
            
            return True, f"✅ Successfully checked in **{resident['name']}**!", resident
            
        except Exception as e:
            if 'duplicate key' in str(e):
                return False, f"ℹ️ Already checked in for **{activity}** today.", None
            else:
                return False, f"Error: {e}", None
    
    @staticmethod
    def get_session_flags(session_labels, session_option):
        """Convert session selection to boolean flags."""
        if len(session_labels) == 1:
            return (True, False, False, False)
        
        flags = [(session_option == "All Sessions") or (session_option == lbl) for lbl in session_labels]
        flags = (flags + [False, False, False, False])[:4]
        return tuple(flags)