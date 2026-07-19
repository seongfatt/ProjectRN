import streamlit as st
from datetime import datetime, timedelta
import uuid
import secrets
import hashlib
from config import supabase, DB_CONNECTED, APP_URL, load_activities

def generate_volunteer_token(admin_id="admin"):
    """Generate a unique, time-limited token for volunteer access."""
    raw = f"{admin_id}{datetime.now().isoformat()}{secrets.token_hex(8)}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]

def create_volunteer_link(token, expires_at):
    """Store token in DB with expiration."""
    if not DB_CONNECTED:
        return None
    try:
        supabase.table('volunteer_tokens').insert({
            "token": token,
            "created_at": datetime.now().isoformat(),
            "expires_at": expires_at.isoformat(),
            "active": True,
            "usage_count": 0
        }).execute()
        return f"{APP_URL}/?mode=volunteer&tk={token}"
    except Exception as e:
        st.error(f"Failed to create link: {e}")
        return None

def validate_volunteer_token(token):
    """Check if token is valid and not expired."""
    if not DB_CONNECTED or not token:
        return False, "Database not connected"
    try:
        r = supabase.table('volunteer_tokens').select("*").eq('token', token).eq('active', True).execute()
        if not r.data:
            return False, "Invalid or revoked link"
        record = r.data[0]
        expires = datetime.fromisoformat(record['expires_at'].replace('Z', '+00:00'))
        if datetime.now().astimezone() > expires:
            return False, "This volunteer link has expired"
        # Increment usage count
        supabase.table('volunteer_tokens').update({
            "usage_count": record.get('usage_count', 0) + 1,
            "last_used": datetime.now().isoformat()
        }).eq('token', token).execute()
        return True, "Valid"
    except Exception as e:
        return False, f"Validation error: {e}"

def revoke_token(token):
    """Revoke a volunteer token."""
    if not DB_CONNECTED:
        return False
    try:
        supabase.table('volunteer_tokens').update({"active": False}).eq('token', token).execute()
        return True
    except:
        return False

def get_active_tokens():
    """Get all active volunteer tokens."""
    if not DB_CONNECTED:
        return []
    try:
        r = supabase.table('volunteer_tokens').select("*").eq('active', True).order('created_at', desc=True).execute()
        return r.data if r.data else []
    except:
        return []

def show_volunteer_access():
    st.header("🔐 Volunteer Access Control")
    st.caption("Create time-limited volunteer links for check-in and registration")

    if not DB_CONNECTED:
        st.error("Database not connected")
        return

    # ── CREATE NEW LINK ──
    st.subheader("Create New Volunteer Link")
    st.info("Volunteers with this link can check in residents AND register new ones — no login needed. Link auto-expires.")

    c1, c2, c3 = st.columns([2, 2, 1])
    with c1:
        duration_type = st.selectbox(
            "Duration Type",
            ["Hours from now", "End of today", "Specific date & time"],
            key="va_duration_type"
        )
    with c2:
        if duration_type == "Hours from now":
            hours = st.number_input("Hours", min_value=1, max_value=168, value=4, key="va_hours")
            expires_at = datetime.now() + timedelta(hours=hours)
            st.caption(f"Expires: {expires_at.strftime('%d %b %Y, %I:%M %p')}")
        elif duration_type == "End of today":
            expires_at = datetime.now().replace(hour=23, minute=59, second=59)
            st.caption(f"Expires: {expires_at.strftime('%d %b %Y, %I:%M %p')}")
        else:  # Specific date & time
            exp_date = st.date_input("Expiry Date", value=datetime.now().date(), key="va_exp_date")
            exp_time = st.time_input("Expiry Time", value=datetime.strptime("23:59", "%H:%M").time(), key="va_exp_time")
            expires_at = datetime.combine(exp_date, exp_time)
            st.caption(f"Expires: {expires_at.strftime('%d %b %Y, %I:%M %p')}")
    with c3:
        st.write(""); st.write("")
        if st.button("Generate Link", type="primary", use_container_width=True):
            token = generate_volunteer_token()
            link = create_volunteer_link(token, expires_at)
            if link:
                st.success("Link generated!")
                st.session_state.new_volunteer_link = link
                st.session_state.new_volunteer_token = token
                st.session_state.new_volunteer_expires = expires_at
                st.rerun()

    if st.session_state.get('new_volunteer_link'):
        st.divider()
        st.markdown("### 📤 Volunteer Check-In Link (Full Access)")
        st.caption("Volunteers can check-in existing residents AND register new ones")
        st.code(st.session_state.new_volunteer_link, language="text")

        # QR for the volunteer link
        import urllib.parse
        vol_qr = f"https://api.qrserver.com/v1/create-qr-code/?size=250x250&data={urllib.parse.quote(st.session_state.new_volunteer_link)}"
        c1, c2 = st.columns([1, 2])
        with c1:
            st.image(vol_qr, width=200)
            st.caption("Full Volunteer QR — scan to open")
        with c2:
            st.markdown(f"""
            <div style="background: #e8f5e9; border-left: 4px solid #4caf50; padding: 15px; border-radius: 4px; color: #1a1a1a;">
                <strong>Full Access Link</strong><br>
                • Check-in existing residents ✅<br>
                • Register new residents ✅<br>
                • Token: <code>{st.session_state.new_volunteer_token[:12]}...</code><br>
                • Expires: <strong>{st.session_state.new_volunteer_expires.strftime('%d %b %Y, %I:%M %p')}</strong><br>
                • Status: 🟢 Active
            </div>
            """, unsafe_allow_html=True)
            wa_msg = urllib.parse.quote(f"Hi! Here's your volunteer access link for Woodlands Zone 6. You can check-in residents AND register new ones. Link expires {st.session_state.new_volunteer_expires.strftime('%d %b %Y, %I:%M %p')}: {st.session_state.new_volunteer_link}")
            st.markdown(f"[📱 Share via WhatsApp](https://wa.me/?text={wa_msg})")

        # Registration-Only Link
        st.divider()
        reg_only_link = f"{APP_URL}/?mode=register&tk={st.session_state.new_volunteer_token}"
        st.markdown("### 📝 Registration-Only Link")
        st.caption("For ad-hoc volunteers — register new residents only, no check-in access")
        st.code(reg_only_link, language="text")

        reg_qr = f"https://api.qrserver.com/v1/create-qr-code/?size=250x250&data={urllib.parse.quote(reg_only_link)}"
        c1, c2 = st.columns([1, 2])
        with c1:
            st.image(reg_qr, width=200)
            st.caption("Registration-Only QR — scan to open")
        with c2:
            st.markdown(f"""
            <div style="background: #e3f2fd; border-left: 4px solid #2196f3; padding: 15px; border-radius: 4px; color: #1a1a1a;">
                <strong>Registration Only</strong><br>
                • Register new walk-ins ✅<br>
                • Check-in existing residents ❌<br>
                • Perfect for outreach tables<br>
                • Same expiry as full access link<br>
                • Token: <code>{st.session_state.new_volunteer_token[:12]}...</code>
            </div>
            """, unsafe_allow_html=True)
            wa_msg2 = urllib.parse.quote(f"Hi! Here's the registration link for Woodlands Zone 6 outreach. Use this to register new residents only. Link expires {st.session_state.new_volunteer_expires.strftime('%d %b %Y, %I:%M %p')}: {reg_only_link}")
            st.markdown(f"[📱 Share via WhatsApp](https://wa.me/?text={wa_msg2})")

    st.divider()

    # ── ACTIVE LINKS ──
    st.subheader("Active Volunteer Links")
    active = get_active_tokens()

    if not active:
        st.info("No active volunteer links. Create one above.")
    else:
        st.write(f"**{len(active)} active link(s)**")
        for tok in active:
            exp = datetime.fromisoformat(tok['expires_at'].replace('Z', '+00:00'))
            remaining = exp - datetime.now().astimezone()
            remaining_str = f"{remaining.days}d {remaining.seconds//3600}h" if remaining.total_seconds() > 0 else "Expired"
            is_expired = remaining.total_seconds() <= 0

            with st.expander(f"🔗 {tok['token'][:16]}... | Used {tok.get('usage_count', 0)}x | Expires: {exp.strftime('%d %b %I:%M %p')}"):
                c1, c2, c3 = st.columns([3, 2, 1])
                with c1:
                    full_link = f"{APP_URL}/?mode=volunteer&tk={tok['token']}"
                    reg_link = f"{APP_URL}/?mode=register&tk={tok['token']}"
                    st.write("**Full Access:**")
                    st.code(full_link, language="text")
                    st.write("**Registration Only:**")
                    st.code(reg_link, language="text")
                    st.write(f"Created: {datetime.fromisoformat(tok['created_at'].replace('Z', '+00:00')).strftime('%d %b %I:%M %p')}")
                with c2:
                    status_color = "🔴" if is_expired else "🟢"
                    st.write(f"**Status:** {status_color} {'Expired' if is_expired else 'Active'}")
                    st.write(f"**Time left:** {remaining_str}")
                    st.write(f"**Usage:** {tok.get('usage_count', 0)} registrations")
                with c3:
                    if st.button("Revoke", key=f"revoke_{tok['token']}", type="secondary", use_container_width=True):
                        revoke_token(tok['token'])
                        st.success("Revoked!")
                        st.rerun()

        # Bulk revoke
        st.divider()
        if st.button("🗑️ Revoke ALL Active Links", type="secondary"):
            for tok in active:
                revoke_token(tok['token'])
            st.success("All links revoked!")
            st.rerun()
