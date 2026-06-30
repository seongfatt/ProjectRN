import streamlit as st
from datetime import datetime
from config import supabase, DB_CONNECTED, refresh_data
from utils import mask_phone

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
            contact = st.text_input("Contact Number *", placeholder="e.g., 91234567")

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
            elif not contact.strip():
                st.error("Contact is required")
            else:
                try:
                    new_id = datetime.now().strftime("%Y%m%d%H%M%S") + str(random.randint(10, 99))
                    supabase.table('participants').insert({
                        "id": new_id,
                        "name": name.strip().upper(),
                        "contact": contact.strip(),
                        "indemnity": indemnity,
                        "is_new": True,
                        "active": True,
                        "registration_date": datetime.now().strftime("%Y-%m-%d")
                    }).execute()
                    refresh_data()
                    st.success(f"✅ {name.strip().upper()} registered successfully!")
                    st.balloons()
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
                st.write(f"{status} {ind} **{p['name']}** — {mask_phone(p.get('contact', 'N/A'))} — ID: `{p['id']}`")
        else:
            st.info("No registrations today")
    except Exception:
        st.info("Unable to load recent registrations")
