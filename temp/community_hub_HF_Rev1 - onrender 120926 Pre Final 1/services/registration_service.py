# services/registration_service.py
"""Unified registration service — eliminates duplicate registration logic"""

import streamlit as st
import random
from datetime import datetime
from config import supabase, DB_CONNECTED, refresh_data, now_sgt
from utils import clean_phone_number, mask_phone

class RegistrationService:
    """Handles all resident registration operations."""
    
    @staticmethod
    def register_resident(name, contact, no_phone=False, indemnity=False, 
                          member_type="Resident", block_no=None, 
                          registration_date=None):
        """
        Register a new resident.
        Returns: (success: bool, message: str, resident_id: str)
        """
        if not name.strip():
            return False, "❌ Name is required", None
        
        if not no_phone and not contact.strip():
            return False, "❌ Contact number is required (check 'No phone' if they don't have one)", None
        
        final_contact = "NO_PHONE" if no_phone else contact.strip()
        clean_contact = clean_phone_number(final_contact) if final_contact != "NO_PHONE" else None
        
        # Check for duplicates
        try:
            if clean_contact and clean_contact != "NO_PHONE":
                res_phone = supabase.table('participants').select('name').eq('contact', clean_contact).eq('active', True).execute()
                if res_phone.data:
                    return False, f"⛔ **Phone number already exists!**\n\nResident: **{res_phone.data[0]['name']}**", None
            
            res_name = supabase.table('participants').select('name', 'contact').eq('name', name.strip().upper()).eq('active', True).execute()
            if res_name.data:
                if final_contact == "NO_PHONE":
                    return False, f"⛔ **Name already exists!**\n\nA resident named **{name.strip().upper()}** is already registered without a phone number.", None
                else:
                    # Name exists but different phone — warn but proceed
                    st.warning(f"⚠️ **Name Match:** A resident named '{name.strip().upper()}' already exists. Proceeding because phone numbers differ.")
        except Exception as e:
            return False, f"Error checking duplicates: {e}", None
        
        # Generate ID
        new_id = datetime.now().strftime("%Y%m%d%H%M%S") + str(random.randint(10, 99))
        reg_date = registration_date or datetime.now().strftime("%Y-%m-%d")
        
        try:
            supabase.table('participants').insert({
                "id": new_id,
                "name": name.strip().upper(),
                "contact": final_contact,
                "block_no": block_no.strip().upper() if block_no else None,
                "indemnity": indemnity,
                "is_new": True,
                "active": True,
                "registration_date": reg_date,
                "member_type": member_type
            }).execute()
            refresh_data()
            return True, f"✅ {name.strip().upper()} registered as **{member_type}** successfully!", new_id
        except Exception as e:
            return False, f"Registration failed: {e}", None
    
    @staticmethod
    def get_member_types():
        """Get list of available member types."""
        return ["Resident", "RN Member", "Volunteer Member", "Gardener"]