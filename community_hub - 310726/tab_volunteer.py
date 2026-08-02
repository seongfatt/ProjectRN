import streamlit as st
import random
from datetime import datetime
from config import supabase, DB_CONNECTED, refresh_data
from utils import mask_phone, clean_phone_number

def show_volunteer():
    st.header("📝 Volunteer Registration")
    st.caption("Quick registration for new residents — no full admin access needed")
    
    if not DB_CONNECTED:
        st.error("Database not connected")
        return

    st.info("Fill in the details below to register a new community member. They will be marked as 'New' automatically.")

    with st.form("volunteer_register_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input("Full Name *", placeholder="e.g., AHMAD BIN ISMAIL")
        with c2:
            contact = st.text_input("Contact Number", placeholder="e.g., 91234567")

        no_phone = st.checkbox("👴 Resident does not have a phone")
        indemnity = st.checkbox("Indemnity Form Signed", value=False)

        st.markdown("""
         <div style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 10px; border-radius: 4px; color: #1a1a1a; font-size: 13px;">
             <strong>Reminder:</strong> Please ensure the resident understands and agrees to the community activity terms before registering.
         </div>
         """, unsafe_allow_html=True)

        submitted = st.form_submit_button("Register Resident", type="primary", use_container_width=True)

        if submitted:
            if not name.strip():
                st.error("Name is required")
            else:
                # Handle no phone case
                final_contact = "NO_PHONE" if no_phone else contact.strip()
                
                # 🔥 STRICT DUPLICATE CHECK (Hard Block for both Phone and Name)
                clean_contact = clean_phone_number(final_contact) if final_contact != "NO_PHONE" else None

                try:
                    # 1. Check Phone (Strict Block)
                    if clean_contact:
                        res_phone = supabase.table('participants').select('name').eq('contact', clean_contact).eq('active', True).execute()
                        if res_phone.data:
                            st.error(f"⛔ **Phone number already exists!**\n\nResident: **{res_phone.data[0]['name']}**\n\nPlease search for them in the system instead.")
                            st.stop()

                    # 2. Check Name (Strict Block)
                    res_name = supabase.table('participants').select('name', 'contact').eq('name', name.strip().upper()).eq('active', True).execute()
                    if res_name.data:
                        st.error(f"⛔ **Name already exists!**\n\nA resident named **{name.strip().upper()}** is already registered in the system.\n\nPlease search for them in the system instead of creating a duplicate.")
                        st.stop() # 🔥 STOP execution immediately
                        
                except Exception as e:
                    st.error(f"Error checking for duplicates: {e}")
                    st.stop()
                
                # If we get here, no duplicate found - proceed with registration
                try:
                    new_id = datetime.now().strftime("%Y%m%d%H%M%S") + str(random.randint(10, 99))
                    supabase.table('participants').insert({
                        "id": new_id,
                        "name": name.strip().upper(),
                        "contact": final_contact,
                        "indemnity": indemnity,
                        "is_new": True,
                        "active": True,
                        "registration_date": datetime.now().strftime("%Y-%m-%d")
                    }).execute()
                    refresh_data()
                    st.success(f"✅ {name.strip().upper()} registered successfully!")
                    st.info(f"Resident ID: `{new_id}`")
                    st.caption("They can now use the check-in QR for attendance.")
                except Exception as e:
                    st.error(f"Registration failed: {e}")

    st.divider()
    st.subheader("Recent Registrations (Today)")
    try:
        today_str = datetime.now().strftime("%Y-%m-%d")
        recent = supabase.table('participants').select("*").eq('registration_date', today_str).order('id', desc=True).limit(10).execute().data
        if recent:
            for p in recent:
                status = "🆕" if p.get('is_new') else "⭐"
                ind = "🟢" if p.get('indemnity') else "🔴"
                contact_display = mask_phone(p.get('contact', 'N/A')) if p.get('contact') != 'NO_PHONE' else "📵 No phone"
                st.write(f"{status} {ind} **{p['name']}** — {contact_display} — ID: `{p['id']}`")
        else:
            st.info("No registrations today")
    except Exception:
        st.info("Unable to load recent registrations")