import streamlit as st
import random
import secrets
import urllib.parse
from datetime import datetime, timedelta, timezone
from config import supabase, DB_CONNECTED, refresh_data, APP_URL
from utils import mask_phone, clean_phone_number
# pages/volunteer.py — Add this import
from services import RegistrationService

def show_volunteer():
    st.header("🤝 Volunteer Registration")
    st.caption("Quick registration for new residents — no full admin access needed")
    
    if not DB_CONNECTED:
        st.error("Database not connected")
        return

    # 🔥 NEW: Generate Temporary Registration Link
    with st.expander("🔗 Generate Temporary Registration Link (No Login Required)"):
        st.markdown("Generate a time-limited link or QR code to let volunteers register residents without needing system login.")
        col1, col2 = st.columns([2, 1])
        with col1:
            duration = st.selectbox("Link expires in:", ["2 Hours", "4 Hours", "8 Hours", "24 Hours"], index=1)
        with col2:
            st.write("") # spacer
            st.write("") # spacer
            if st.button("🚀 Generate Link", type="primary", use_container_width=True):
                # Parse duration
                hours = int(duration.split()[0])
                token = secrets.token_urlsafe(16)
                expires_at = datetime.now(timezone.utc) + timedelta(hours=hours)
                
                try:
                    supabase.table('volunteer_tokens').insert({
                        "token": token,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "expires_at": expires_at.isoformat(),
                        "active": True,
                        "usage_count": 0,
                        "created_by": "volunteer_reg"
                    }).execute()
                    
                    reg_link = f"{APP_URL}/?mode=register&tk={token}"
                    st.session_state['temp_reg_link'] = reg_link
                    st.session_state['temp_reg_expires'] = expires_at
                    st.success("✅ Link generated successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to generate link: {e}")
        
        # Display the generated link and QR code
        if 'temp_reg_link' in st.session_state:
            st.divider()
            st.markdown("**📤 Share this link or QR code with volunteers:**")
            st.code(st.session_state['temp_reg_link'], language="text")
            
            # Generate QR Code using a free API
            qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={urllib.parse.quote(st.session_state['temp_reg_link'])}"
            c1, c2 = st.columns([1, 2])
            with c1:
                st.image(qr_url, width=150, caption="Scan to Register")
            with c2:
                # Convert to SG Time for display
                exp_time = st.session_state['temp_reg_expires'].astimezone(timezone(timedelta(hours=8))).strftime('%d %b %Y, %I:%M %p')
                st.markdown(f"""
                <div style="background: #e3f2fd; border-left: 4px solid #2196f3; padding: 15px; border-radius: 4px; color: #1a1a1a;">
                    <strong>Registration-Only Access</strong><br>
                    • Volunteers can register new residents ✅<br>
                    • No system login required ✅<br>
                    • Expires: <strong>{exp_time} (SG Time)</strong><br>
                </div>
                """, unsafe_allow_html=True)

    st.divider()

    st.info("Fill in the details below to register a new community member. They will be marked as 'New' automatically.")

    # FIX: Use standard widgets instead of st.form to allow instant checkbox reactivity
    name = st.text_input("Full Name *", placeholder="e.g., AHMAD BIN ISMAIL", key="vol_name")
    contact = st.text_input("Contact Number", placeholder="e.g., 91234567", key="vol_contact")

    no_phone = st.checkbox("👴 Resident does not have a phone", key="vol_no_phone")
    indemnity = st.checkbox("Indemnity Form Signed", value=False, key="vol_indemnity")
    
    # 🔥 NEW: Member Type Selection
    st.markdown("---")
    st.markdown("**👤 Member Type:**")
    member_type = st.radio(
        "Select member category:",
        ["Resident", "RN Member", "Volunteer Member", "Gardener"],
        horizontal=True,
        key="vol_member_type",
        help="RN Member = Resident Network Committee | Volunteer Member = Activity Volunteer"
    )
    
    # 🔥 This checkbox will now work instantly!
    block_consent = st.checkbox("🏢 I agree to share my block information (Optional)", key="vol_block_consent")
    
    block_no = ""
    if block_consent:
        block_no = st.text_input("Block No.", placeholder="e.g., 622, 624A", key="vol_block_no").strip().upper()

    st.markdown("""
     <div style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 10px; border-radius: 4px; color: #1a1a1a; font-size: 13px;">
         <strong>Reminder:</strong> Please ensure the resident understands and agrees to the community activity terms before registering.
     </div>
     """, unsafe_allow_html=True)

    # Use a regular button instead of form_submit_button
    if st.button("Register Resident", type="primary", use_container_width=True, key="vol_register_btn"):
        if not name.strip():
            st.error("❌ Name is required")
        elif not no_phone and not contact.strip():
            # 🔥 FIX: Only require phone if "no phone" checkbox is NOT checked
            st.error("❌ Contact number is required (check 'Resident does not have a phone' if they don't have one)")
        else:
            final_contact = "NO_PHONE" if no_phone else contact.strip()
            clean_contact = clean_phone_number(final_contact) if final_contact != "NO_PHONE" else None

            try:
                if clean_contact and clean_contact != "NO_PHONE":
                    res_phone = supabase.table('participants').select('name').eq('contact', clean_contact).eq('active', True).execute()
                    if res_phone.data:
                        st.error(f"⛔ **Phone number already exists!**\n\nResident: **{res_phone.data[0]['name']}**")
                        st.stop()

                res_name = supabase.table('participants').select('name', 'contact').eq('name', name.strip().upper()).eq('active', True).execute()
                if res_name.data:
                    st.error(f"⛔ **Name already exists!**\n\nA resident named **{name.strip().upper()}** is already registered.")
                    st.stop()
                    
            except Exception as e:
                st.error(f"Error checking for duplicates: {e}")
                st.stop()
            
            try:
                success, message, new_id = RegistrationService.register_resident(
                    name=name,
                    contact=contact,
                    no_phone=no_phone,
                    indemnity=indemnity,
                    member_type=member_type,
                    block_no=block_no
                )
                if success:
                    st.success(f"✅ {name.strip().upper()} registered as **{member_type}** successfully!")
                    st.info(f"Resident ID: `{new_id}`")
                else:
                    st.error(message)
                refresh_data()
                st.success(f"✅ {name.strip().upper()} registered as **{member_type}** successfully!")
                st.info(f"Resident ID: `{new_id}`")
            except Exception as e:
                st.error(f"Registration failed: {e}")

    st.divider()
    st.subheader("Recent Registrations (Today)")
    try:
        today_str = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
        recent = supabase.table('participants').select("*").eq('registration_date', today_str).order('id', desc=True).limit(10).execute().data
        if recent:
            for p in recent:
                status = "🆕" if p.get('is_new') else "⭐"
                ind = "🟢" if p.get('indemnity') else ""
                contact_display = mask_phone(p.get('contact', 'N/A')) if p.get('contact') != 'NO_PHONE' else "📵 No phone"
                block_display = f" | Block: {p.get('block_no', 'N/A')}" if p.get('block_no') else ""
                member_type_display = f" | {p.get('member_type', 'Resident')}"
                st.write(f"{status} {ind} **{p['name']}** — {contact_display}{block_display}{member_type_display} — ID: `{p['id']}`")
        else:
            st.info("No registrations today")
    except Exception:
        st.info("Unable to load recent registrations")