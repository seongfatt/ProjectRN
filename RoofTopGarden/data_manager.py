# data_manager.py - Supabase Data Operations
import streamlit as st
from datetime import datetime
from config import supabase, DB_CONNECTED, refresh_data

def load_plots():
    """Load all garden plots from Supabase"""
    if not DB_CONNECTED:
        st.error("Database not connected!")
        return []
    
    try:
        response = supabase.table('garden_plots').select("*").order('plot_number').execute()
        return response.data if response.data else []
    except Exception as e:
        st.error(f"Error loading plots: {e}")
        return []

def get_plot(plot_number):
    """Get single plot details"""
    if not DB_CONNECTED:
        return None
    try:
        response = supabase.table('garden_plots').select("*").eq('plot_number', plot_number).execute()
        return response.data[0] if response.data else None
    except:
        return None

def update_plot(plot_number, updates):
    """Update plot with new data"""
    if not DB_CONNECTED:
        return False
    
    try:
        # Add timestamp to change log
        if 'change_log' in updates:
            updates['change_log'] = f"{updates['change_log']} - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        updates['updated_at'] = datetime.now().isoformat()
        
        result = supabase.table('garden_plots').update(updates).eq('plot_number', plot_number).execute()
        return True if result.data else False
    except Exception as e:
        st.error(f"Update failed: {e}")
        return False

def get_user_plot(user_id):
    """Find plot owned by user"""
    if not user_id or not DB_CONNECTED:
        return None
    
    try:
        response = supabase.table('garden_plots').select("*").eq('user_id', user_id.lower().strip()).eq('occupied', True).execute()
        return response.data[0] if response.data else None
    except:
        return None

# Request Management Functions
def create_request(plot_number, user_id, user_name, contact, notes=""):
    """Create new plot request"""
    if not DB_CONNECTED:
        return None
    
    try:
        data = {
            "plot_number": plot_number,
            "user_id": user_id,
            "user_name": user_name,
            "contact": contact,
            "notes": notes,
            "status": "pending"
        }
        result = supabase.table('plot_requests').insert(data).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        st.error(f"Request failed: {e}")
        return None

def get_pending_requests():
    """Get all pending requests"""
    if not DB_CONNECTED:
        return []
    
    try:
        response = supabase.table('plot_requests').select("*").eq('status', 'pending').order('created_at').execute()
        return response.data if response.data else []
    except:
        return []

def update_request_status(request_id, status):
    """Approve or reject request"""
    if not DB_CONNECTED:
        return False
    
    try:
        result = supabase.table('plot_requests').update({"status": status}).eq('id', request_id).execute()
        return True if result.data else False
    except:
        return False

def get_occupied_count():
    """Get count of occupied plots"""
    if not DB_CONNECTED:
        return 0
    
    try:
        response = supabase.table('garden_plots').select('*', count="exact").eq('occupied', True).execute()
        return response.count
    except:
        return 0