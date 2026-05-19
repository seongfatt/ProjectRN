import streamlit as st
from datetime import datetime
from config import supabase, DB_CONNECTED

def check_and_convert_status(participant_id, participant_name):
    """Auto-convert New to Regular after 3 attendances"""
    if not DB_CONNECTED:
        return None
    
    try:
        count_data = supabase.table('attendance').select('*', count='exact').eq('participant_id', participant_id).execute()
        count = count_data.count
        
        if count >= 3:
            participant = supabase.table('participants').select('is_new').eq('id', participant_id).execute()
            if participant.data and participant.data[0].get('is_new', False):
                supabase.table('participants').update({'is_new': False}).eq('id', participant_id).execute()
                return f"🎉 {participant_name} graduated to Regular!"
        return None
    except:
        return None

def get_attendance_count(participant_id):
    """Get attendance count for a participant"""
    try:
        data = supabase.table('attendance').select('*', count='exact').eq('participant_id', participant_id).execute()
        return data.count
    except:
        return 0