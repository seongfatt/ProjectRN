# routes/auto_checkin.py
import streamlit as st
from datetime import datetime, timezone, timedelta
import urllib.parse
from config import supabase, DB_CONNECTED, load_activities, now_sgt
from utils import verify_token, clean_phone_number, check_and_convert_status
from utils import sync_session_attendance_async

def handle_auto_checkin(params):
    """Handle mode=auto check-in flow"""
    if not DB_CONNECTED or supabase is None:
        st.error("Database not connected.")
        return

    pid = params.get("pid")
    date_str = params.get("date", now_sgt().strftime("%Y%m%d"))
    token = params.get("tk")
    act = params.get("act", "Cardio Drumming")
    session_param = params.get("session", "both")

    if not verify_token(pid, date_str, token):
        st.title("Woodlands Zone 6 Community Hub")
        st.markdown("""
        <div style="background: #e3f2fd; border-left: 5px solid #2196f3; padding: 20px; border-radius: 8px; margin: 20px 0;">
            <h3 style="margin-top:0; color: #0d47a1;">Hello!</h3>
            <p style="font-size: 18px; color: #1a1a1a;">
                Please present this QR code to the <strong>Volunteer at the entrance</strong> to check in.
            </p>
            <p style="color: #666;">Self check-in from home is not allowed to ensure accurate attendance.</p>
        </div>
        """, unsafe_allow_html=True)
        return

    # ... rest of the auto check-in logic from app.py
    # (I'll provide the complete extracted version)