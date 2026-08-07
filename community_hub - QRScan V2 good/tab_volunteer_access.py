import streamlit as st
from datetime import datetime, timedelta, timezone
import uuid
import secrets
import hashlib
import urllib.parse
from config import supabase, DB_CONNECTED, APP_URL, load_activities
from utils import generate_token

# ─── Helper Functions ──────────────────────────────────────
def generate_volunteer_token(admin_id="admin"):
    raw = f"{admin_id}{datetime.now().isoformat()}{secrets.token_hex(8)}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]

def create_volunteer_link(token, expires_at, created_by="admin"):
    if not DB_CONNECTED: return None
    try:
        supabase.table('volunteer_tokens').insert({
            "token": token,
            "created_by": created_by,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": expires_at.isoformat(),
            "active": True,
            "usage_count": 0
        }).execute()
        return f"{APP_URL}/?mode=volunteer&tk={token}"
    except Exception as e:
        st.error(f"Failed to create link: {e}")
        return None

def validate_volunteer_token(token):
    if not DB_CONNECTED or not token:
        return False, "Database not connected"
    try:
        r = supabase.table('volunteer_tokens').select("*").eq('token', token).eq('active', True).execute()
        if not r.data: return False, "Invalid or revoked link"
        record = r.data[0]
        expires_str = record['expires_at']
        
        # Handle 'Z' suffix from Supabase
        if expires_str.endswith('Z'):
            expires_str = expires_str.replace('Z', '+00:00')
            
        expires = datetime.fromisoformat(expires_str)
        
        # Ensure the expiry time is timezone-aware (UTC)
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
            
        # Compare using UTC time
        now_utc = datetime.now(timezone.utc)
        
        if now_utc > expires: 
            return False, "This volunteer link has expired"
            
        supabase.table('volunteer_tokens').update({
            "usage_count": record.get('usage_count', 0) + 1,
            "last_used": datetime.now(timezone.utc).isoformat()
        }).eq('token', token).execute()
        return True, "Valid"
    except Exception as e:
        return False, f"Validation error: {e}"

def revoke_token(token):
    if not DB_CONNECTED: return False
    try:
        supabase.table('volunteer_tokens').update({"active": False}).eq('token', token).execute()
        return True
    except: return False

def get_active_tokens():
    if not DB_CONNECTED: return []
    try:
        r = supabase.table('volunteer_tokens').select("*").eq('active', True).order('created_at', desc=True).execute()
        return r.data if r.data else []
    except: return []

def to_sgt(dt):
    """Convert UTC datetime to Singapore Time (UTC+8) for display"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    sgt = timezone(timedelta(hours=8))
    return dt.astimezone(sgt)

# ─── Main UI Function ──────────────────────────────────────
def show_volunteer_access():
    current_role = st.session_state.get('user_role', 'admin')
    
    st.header("🤝 Volunteer Access Control")
    st.caption("Create time-limited volunteer links for check-in and registration")
    
    if not DB_CONNECTED:
        st.error("Database not connected")
        return

    # ─ UNIFIED VOLUNTEER PORTAL (MOVED TO TOP) ──
    st.divider()
    st.subheader("🎟️ Unified Volunteer Portal")
    st.caption("All-in-one access for volunteers: QR scanner, phone search, and registration")
    
    c1, c2, c3 = st.columns([2, 2, 1])
    with c1:
        duration_type = st.selectbox(
            "Duration Type",
            ["Hours from now", "End of today", "Specific date & time"],
            key="vp_duration_type"
        )
    with c2:
        sgt = timezone(timedelta(hours=8))
        if duration_type == "Hours from now":
            hours = st.number_input("Hours", min_value=1, max_value=168, value=4, key="vp_hours")
            expires_at_sgt = datetime.now(sgt) + timedelta(hours=hours)
            expires_at = expires_at_sgt.astimezone(timezone.utc) # Save to DB in UTC
            st.caption(f"Expires: {expires_at_sgt.strftime('%d %b %Y, %I:%M %p')} (SG Time)")
        elif duration_type == "End of today":
            now_sgt = datetime.now(sgt)
            expires_at_sgt = now_sgt.replace(hour=23, minute=59, second=59)
            expires_at = expires_at_sgt.astimezone(timezone.utc) # Save to DB in UTC
            st.caption(f"Expires: {expires_at_sgt.strftime('%d %b %Y, %I:%M %p')} (SG Time)")
        else:
            exp_date = st.date_input("Expiry Date", value=datetime.now().date(), key="vp_exp_date")
            exp_time = st.time_input("Expiry Time", value=datetime.strptime("23:59", "%H:%M").time(), key="vp_exp_time")
            
            expires_at_sgt = datetime.combine(exp_date, exp_time, tzinfo=sgt)
            expires_at = expires_at_sgt.astimezone(timezone.utc) # Save to DB in UTC
            
            st.caption(f"Expires: {expires_at_sgt.strftime('%d %b %Y, %I:%M %p')} (SG Time)")
    with c3:
        st.write(""); st.write("")
        if st.button("📱 Generate Unified Portal Link", type="primary", use_container_width=True):
            new_token = generate_volunteer_token(current_role)
            selected_activity = st.session_state.get('selected_activity', 'Cardio Drumming')
            
            try:
                supabase.table('volunteer_tokens').insert({
                    "token": new_token,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "expires_at": expires_at.isoformat(),
                    "active": True,
                    "usage_count": 0,
                    "created_by": current_role
                }).execute()
            except Exception as e:
                st.error(f"⚠️ Network Error: Could not connect to database.")
                st.info("💡 This is usually a temporary internet glitch on the server. Please wait 1 minute and try again, or restart the Space.")
                st.stop()
            
            portal_url = f"{APP_URL}/?mode=volunteer_portal&tk={new_token}&act={urllib.parse.quote(selected_activity)}"
            
            st.success("✅ Unified Portal Link Generated!")
            st.session_state.portal_link = portal_url
            st.session_state.portal_expires = expires_at
            st.rerun()

    if st.session_state.get('portal_link'):
        st.divider()
        st.markdown("### 🔗 Unified Volunteer Portal Link")
        st.caption("All-in-one access: QR scanner, phone search, and registration")
        st.code(st.session_state.portal_link, language="text")

        portal_qr = f"https://api.qrserver.com/v1/create-qr-code/?size=250x250&data={urllib.parse.quote(st.session_state.portal_link)}"
        c1, c2 = st.columns([1, 2])
        with c1:
            st.image(portal_qr, width=200)
            st.caption("Portal QR — scan to open")
        with c2:
            portal_expires_sgt = to_sgt(st.session_state.portal_expires)
            st.markdown(f"""
            <div style="background: #e3f2fd; border-left: 4px solid #2196f3; padding: 15px; border-radius: 4px; color: #1a1a1a;">
                <strong>Unified Portal Access</strong><br>
                • Scan QR codes (camera) ✅<br>
                • Phone number search ✅<br>
                • Register new residents ✅<br>
                • Session selection included ✅<br>
                • Real-time statistics ✅<br>
                • Token: <code>{st.session_state.portal_link.split('tk=')[1][:12]}...</code><br>
                • Expires: <strong>{portal_expires_sgt.strftime('%d %b %Y, %I:%M %p')} (SG Time)</strong><br>
                • Status: 🟢 Active
            </div>
            """, unsafe_allow_html=True)
            wa_msg = urllib.parse.quote(f"Hi! Here's your unified volunteer portal link for Woodlands Zone 6. Link expires {portal_expires_sgt.strftime('%d %b %Y, %I:%M %p')}: {st.session_state.portal_link}")
            st.markdown(f"[📱 Share via WhatsApp](https://wa.me/?text={wa_msg})")

    st.divider()

    # ── CREATE NEW LEGACY LINK ─
    st.subheader("📝 Create Legacy Volunteer Link")
    st.caption("Original volunteer link (check-in + registration)")
    
    c1, c2, c3 = st.columns([2, 2, 1])
    with c1:
        duration_type = st.selectbox(
            "Duration Type",
            ["Hours from now", "End of today", "Specific date & time"],
            key="va_duration_type"
        )
    with c2:
        sgt = timezone(timedelta(hours=8))
        if duration_type == "Hours from now":
            hours = st.number_input("Hours", min_value=1, max_value=168, value=4, key="va_hours")
            expires_at_sgt = datetime.now(sgt) + timedelta(hours=hours)
            expires_at = expires_at_sgt.astimezone(timezone.utc) # Save to DB in UTC
            st.caption(f"Expires: {expires_at_sgt.strftime('%d %b %Y, %I:%M %p')} (SG Time)")
        elif duration_type == "End of today":
            now_sgt = datetime.now(sgt)
            expires_at_sgt = now_sgt.replace(hour=23, minute=59, second=59)
            expires_at = expires_at_sgt.astimezone(timezone.utc) # Save to DB in UTC
            st.caption(f"Expires: {expires_at_sgt.strftime('%d %b %Y, %I:%M %p')} (SG Time)")
        else:
            exp_date = st.date_input("Expiry Date", value=datetime.now().date(), key="va_exp_date")
            exp_time = st.time_input("Expiry Time", value=datetime.strptime("23:59", "%H:%M").time(), key="va_exp_time")
            
            expires_at_sgt = datetime.combine(exp_date, exp_time, tzinfo=sgt)
            expires_at = expires_at_sgt.astimezone(timezone.utc) # Save to DB in UTC
            
            st.caption(f"Expires: {expires_at_sgt.strftime('%d %b %Y, %I:%M %p')} (SG Time)")
    with c3:
        st.write(""); st.write("")
        if st.button("🔗 Generate Legacy Link", type="secondary", use_container_width=True):
            token = generate_volunteer_token(current_role)
            link = create_volunteer_link(token, expires_at, created_by=current_role)
            if link:
                st.success("✅ Link generated!")
                st.session_state.new_volunteer_link = link
                st.session_state.new_volunteer_token = token
                st.session_state.new_volunteer_expires = expires_at
                st.rerun()

    if st.session_state.get('new_volunteer_link'):
        st.divider()
        st.markdown("### 📤 Volunteer Check-In Link (Full Access)")
        st.caption("Volunteers can check-in existing residents AND register new ones")
        st.code(st.session_state.new_volunteer_link, language="text")

        vol_qr = f"https://api.qrserver.com/v1/create-qr-code/?size=250x250&data={urllib.parse.quote(st.session_state.new_volunteer_link)}"
        c1, c2 = st.columns([1, 2])
        with c1:
            st.image(vol_qr, width=200)
            st.caption("Full Volunteer QR — scan to open")
        with c2:
            new_vol_expires_sgt = to_sgt(st.session_state.new_volunteer_expires)
            st.markdown(f"""
            <div style="background: #e8f5e9; border-left: 4px solid #4caf50; padding: 15px; border-radius: 4px; color: #1a1a1a;">
                <strong>Full Access Link</strong><br>
                • Check-in existing residents ✅<br>
                • Register new residents ✅<br>
                • Token: <code>{st.session_state.new_volunteer_token[:12]}...</code><br>
                • Expires: <strong>{new_vol_expires_sgt.strftime('%d %b %Y, %I:%M %p')} (SG Time)</strong><br>
                • Status: 🟢 Active
            </div>
            """, unsafe_allow_html=True)
            wa_msg = urllib.parse.quote(f"Hi! Here's your volunteer access link for Woodlands Zone 6. Link expires {new_vol_expires_sgt.strftime('%d %b %Y, %I:%M %p')}: {st.session_state.new_volunteer_link}")
            st.markdown(f"[📱 Share via WhatsApp](https://wa.me/?text={wa_msg})")

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
            wa_msg2 = urllib.parse.quote(f"Hi! Here's the registration link for Woodlands Zone 6 outreach. Link expires {new_vol_expires_sgt.strftime('%d %b %Y, %I:%M %p')}: {reg_only_link}")
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
            exp_str = tok['expires_at']
            if exp_str.endswith('Z'):
                exp_str = exp_str.replace('Z', '+00:00')
            exp = datetime.fromisoformat(exp_str)
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
                
            exp_sgt = to_sgt(exp)
            remaining = exp - datetime.now(timezone.utc)
            remaining_str = f"{remaining.days}d {remaining.seconds//3600}h" if remaining.total_seconds() > 0 else "Expired"
            is_expired = remaining.total_seconds() <= 0

            with st.expander(f"🔗 {tok['token'][:16]}... | Used {tok.get('usage_count', 0)}x | Expires: {exp_sgt.strftime('%d %b %Y, %I:%M %p')} (SG Time)"):
                c1, c2, c3 = st.columns([3, 2, 1])
                with c1:
                    full_link = f"{APP_URL}/?mode=volunteer&tk={tok['token']}"
                    reg_link = f"{APP_URL}/?mode=register&tk={tok['token']}"
                    st.write("**Full Access:**")
                    st.code(full_link, language="text")
                    st.write("**Registration Only:**")
                    st.code(reg_link, language="text")
                    st.write(f"Created by: {tok.get('created_by', 'Unknown').capitalize()}")
                with c2:
                    status_color = "🔴" if is_expired else "🟢"
                    st.write(f"**Status:** {status_color} {'Expired' if is_expired else 'Active'}")
                    st.write(f"**Time left:** {remaining_str}")
                with c3:
                    if st.button("Revoke", key=f"revoke_{tok['token']}", type="secondary", use_container_width=True):
                        revoke_token(tok['token'])
                        st.success("Revoked!")
                        st.rerun()

        st.divider()
        if st.button("🗑️ Revoke ALL Active Links", type="secondary"):
            for tok in active:
                revoke_token(tok['token'])
            st.success("All links revoked!")
            st.rerun()