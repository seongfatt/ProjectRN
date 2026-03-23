# data_manager.py - Supabase Data Operations
import pandas as pd
import streamlit as st
from datetime import datetime
from config import supabase, DB_CONNECTED, refresh_data
from datetime import datetime, timezone


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

from datetime import datetime, timezone

def update_plot(plot_number, updates):
    """Update plot in garden_plots table — fixed for Supabase compatibility"""
    if not DB_CONNECTED:
        st.error("Database not connected!")
        return False

    # Clean empty strings → None
    for k, v in updates.items():
        if isinstance(v, str) and v.strip() == "":
            updates[k] = None

    # ✅ Critical: Use UTC timestamp in compatible format
    updates['updated_at'] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    try:
        st.caption(f"📤 Updating plot {plot_number} with: {updates}")
        
        response = supabase.table('garden_plots').update(updates).eq('plot_number', plot_number).execute()
        
        if response.data and len(response.data) > 0:
            st.success(f"✅ Updated plot {plot_number} successfully!")
            return True
        else:
            st.warning(f"⚠️ Update returned empty data. Response: {response}")
            return False

    except Exception as e:
        st.error(f"💥 Update failed: {e}")
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
    
    # PDPA Compliance Function
def mask_phone(phone):
    """Mask phone number to show only last 4 digits (PDPA compliance)"""
    if not phone or phone == "N/A" or str(phone).lower() == "nan":
        return "N/A"
    phone_str = str(phone).strip()
    if len(phone_str) <= 4:
        return phone_str
    return "••••" + phone_str[-4:]