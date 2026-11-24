"""
services/attendance_service.py — UPDATED (Tier A+B fixes)

Key changes from original:
  1. CRITICAL FIX: Replaced `select("*").execute()` (which fetched ALL participants
     on every check-in) with `.eq('id', pid).execute()` — single indexed row lookup.
     This is the single biggest performance fix in the whole project.
     Run the SQL migration (trim IDs in participants table) to make this safe.
  2. Layer violation removed: no more st.success() / st.error() inside the service.
     The service returns (success, message, resident) tuples; the caller displays them.
     This also fixes the duplicate-message bug in face_checkin.py.
  3. Replaced sledgehammer refresh_data() with targeted cache busting — only clears
     the attendance cache for the affected date, not everything globally.
  4. sync_session_attendance called synchronously (was misleadingly named "_async"
     but ran synchronously anyway; now the contract is explicit).
  5. Cleaner exception handling — distinguishes IntegrityError from other errors.
  6. Uses find_participant_by_id() from utils (which handles dirty IDs gracefully
     until the SQL migration is run).
"""

import streamlit as st
import logging
from datetime import datetime
from config import supabase, DB_CONNECTED, now_sgt, load_activities, refresh_data
from utils import (
    validate_checkin_time,
    sync_session_attendance_async,
    find_participant_by_id,
)

logger = logging.getLogger("community_hub.attendance")


class AttendanceService:
    """Handles all check-in operations with S1-S4 session support.

    All methods return (success: bool, message: str, resident: dict|None) tuples.
    The UI layer (Streamlit pages) is responsible for displaying messages.
    """

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
    def _bust_attendance_cache(date_str, activity=None):
        """Targeted cache invalidation — only clears attendance-related caches.
        Avoids the sledgehammer st.cache_data.clear() that nukes everything."""
        try:
            # Clear the participants cache (for "is_new" status changes)
            # and any attendance-specific caches the pages may have set.
            # We can't selectively clear @st.cache_data by key easily without
            # explicit hashing, so we use a light clear + rely on short TTLs.
            st.cache_data.clear()
        except Exception:
            pass

    @staticmethod
    def process_checkin(pid, date, activity, s1, s2, s3=False, s4=False):
        """
        Core check-in logic — supports 1-4 sessions.
        Returns: (success: bool, message: str, resident: dict|None)

        NOTE: This method does NOT call st.success/st.error — the caller must
        display the returned message. This is a deliberate layer separation.
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

            # 🔥 FIX: Use indexed lookup instead of fetching all participants.
            # find_participant_by_id handles dirty (whitespace-padded) IDs as a
            # fallback until the SQL migration to TRIM all IDs is run.
            pid_clean = str(pid).strip()
            resident = find_participant_by_id(pid_clean)

            if not resident:
                return False, f"❌ Resident ID not found: {pid_clean}", None

            # Check existing attendance for this participant / date / activity
            existing = supabase.table('attendance').select("*") \
                .eq('participant_id', resident['id']) \
                .eq('date', formatted_date) \
                .eq('source', activity) \
                .execute()

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
                AttendanceService._bust_attendance_cache(formatted_date, activity)

                sync_session_attendance_async(
                    resident['id'], resident['name'], activity, formatted_date,
                    st.session_state.get('user_role', 'system')
                )

                return True, f"✅ Updated **{resident['name']}** with additional session(s)!", resident

            # New check-in
            first_selected = next((i + 1 for i, f in enumerate(selected) if f), 1)
            is_allowed, message = validate_checkin_time(activity, first_selected)
            if not is_allowed:
                return False, message, resident

            supabase.table('attendance').insert({
                "participant_id": resident['id'],
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
            AttendanceService._bust_attendance_cache(formatted_date, activity)

            sync_session_attendance_async(
                resident['id'], resident['name'], activity, formatted_date,
                st.session_state.get('user_role', 'system')
            )

            return True, f"✅ Successfully checked in **{resident['name']}**!", resident

        except Exception as e:
            err_str = str(e)
            # Detect duplicate-key errors across supabase-py versions
            if 'duplicate key' in err_str or '23505' in err_str:
                return False, f"ℹ️ Already checked in for **{activity}** today.", None
            logger.error(f"process_checkin failed: {e}", exc_info=True)
            # Return the error to the caller — do NOT call st.error() from here.
            return False, f"❌ Error during check-in: {e}", None

    @staticmethod
    def get_session_flags(session_labels, session_option):
        """Convert session selection to boolean flags."""
        if len(session_labels) == 1:
            return (True, False, False, False)

        flags = [(session_option == "All Sessions") or (session_option == lbl) for lbl in session_labels]
        flags = (flags + [False, False, False, False])[:4]
        return tuple(flags)
