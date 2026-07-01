"""
tab_sessions.py
Session RSVP & Live Check-In for Woodlands Zone 6 Community Hub
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import uuid
import urllib.parse
from config import supabase, DB_CONNECTED, APP_URL, load_activities

# ─── Helpers ─────────────────────────────────────────────
def _generate_rsvp_url(token):
    base = APP_URL.rstrip('/') if APP_URL else 'https://your-app.streamlit.app'
    return f"{base}/?mode=rsvp&tk={token}"

def _generate_whatsapp_message(session, rsvp_url):
    title = session.get('activity_name', 'Community Session')
    date = session.get('session_date', 'TBA')
    time = session.get('session_time', 'TBA')
    return (
        f"🌳 Woodlands Zone 6 Community Hub\n\n"
        f"📅 {title}\n"
        f"🗓️ Date: {date}\n"
        f"🕐 Time: {time}\n\n"
        f"Please confirm your attendance by tapping the link:\n{rsvp_url}"
    )

def _is_session_expired(session):
    """Check if current time is past the session start time (expires the link)."""
    try:
        date_str = session.get('session_date')
        time_str = session.get('session_time', '23:59')
        start_time_str = time_str.split('-')[0].strip()
        try:
            start_time = datetime.strptime(start_time_str, "%I:%M %p").time()
        except:
            start_time = datetime.strptime(start_time_str, "%H:%M").time()
        
        session_dt = datetime.combine(datetime.strptime(date_str, "%Y-%m-%d").date(), start_time)
        return datetime.now() > session_dt
    except:
        return False

# ─── DB Functions ────────────────────────────────────────
def _fetch_sessions(status=None):
    query = supabase.table("sessions").select("*")
    if status: query = query.eq("status", status)
    return query.order("session_date", desc=False).execute().data or []

def _fetch_session_by_token(token):
    resp = supabase.table("sessions").select("*").eq("rsvp_link_token", token).single().execute()
    return resp.data if resp.data else None

def _fetch_rsvps(session_id):
    return supabase.table("session_rsvp").select("*").eq("session_id", session_id).execute().data or []

def _upsert_rsvp(session_id, name, phone, response, checked_in, is_walk_in=False):
    existing = supabase.table("session_rsvp").select("*").eq("session_id", session_id).eq("name", name).execute().data
    data = {
        "session_id": session_id, "name": name, "phone": phone,
        "response": response, "checked_in": checked_in, "is_walk_in": is_walk_in,
        "updated_at": datetime.now().isoformat()
    }
    if existing:
        supabase.table("session_rsvp").update(data).eq("id", existing[0]['id']).execute()
    else:
        data["id"] = str(uuid.uuid4())
        data["created_at"] = datetime.now().isoformat()
        supabase.table("session_rsvp").insert(data).execute()

def _sync_to_main_attendance(sup, session, rsvp):
    """
    BRIDGE FUNCTION: Syncs a checked-in RSVP to the main 'attendance' table 
    so it automatically appears in your Monthly Reports and Meeting Dashboard!
    """
    if rsvp.get('response') != 'attending' or not rsvp.get('checked_in'):
        return
    
    session_date = session.get('session_date')
    activity_name = session.get('activity_name')
    name = rsvp.get('name', '').strip().upper()
    phone = rsvp.get('phone', '').strip()
    
    # 1. Try to find the resident's actual participant_id
    pid = None
    try:
        # Try exact name match first
        res = sup.table('participants').select('id').eq('name', name).execute()
        if res.data:
            pid = res.data[0]['id']
        elif phone and len(phone) >= 4:
            # Fallback: match by last 4 digits of phone number
            all_p = sup.table('participants').select('id', 'contact').execute()
            for p in all_p.data:
                if str(p.get('contact', '')).replace(' ', '').endswith(phone[-4:]):
                    pid = p['id']
                    break
    except:
        pass
        
    # If they aren't in the main DB (e.g., a walk-in), use a temporary ID
    if not pid:
        pid = f"WALKIN_{rsvp.get('id', 'unknown')}"
        
    # 2. Check if they are already in the attendance table for this date/activity
    try:
        existing = sup.table('attendance').select('id') \
            .eq('participant_id', pid).eq('date', session_date).eq('source', activity_name).execute()
        
        # 3. If not, insert them into the main attendance table!
        if not existing.data:
            sup.table('attendance').insert({
                "participant_id": pid,
                "name": name,
                "date": session_date,
                "session_1": True,
                "session_2": False,
                "timestamp": datetime.now().isoformat(),
                "self_checkin": False,
                "source": activity_name
            }).execute()
    except Exception as e:
        print(f"Sync to main attendance error: {e}")
        
def _delete_rsvp(rsvp_id):
    supabase.table("session_rsvp").delete().eq("id", rsvp_id).execute()

def _close_session(session_id):
    supabase.table("sessions").update({"status": "closed", "updated_at": datetime.now().isoformat()}).eq("id", session_id).execute()

# ─── UI: Live Check-In (At Venue) ────────────────────────
def _render_live_checkin(session):
    st.title(f"🔍 Live Check-In: {session['activity_name']}")
    st.caption(f"{session['session_date']} | {session['session_time']} | {session.get('location', '')}")
    
    is_closed = session.get('status') == 'closed' or _is_session_expired(session)
    if is_closed:
        st.warning("⚠️ Session is CLOSED or EXPIRED. Check-in is locked.")
    st.divider()
    
    search = st.text_input("🔎 Search resident...", key="live_search")
    
    participants = st.session_state.get('participants', [])
    if not participants:
        from utils import load_participants
        participants = load_participants()
        
    rsvps = _fetch_rsvps(session['id'])
    rsvp_dict = {r['name'].lower().strip(): r for r in rsvps}
    
    active_p = [p for p in participants if p.get('active', True)]
    if search:
        s = search.lower()
        active_p = [p for p in active_p if s in p['name'].lower() or s in p.get('contact', '')[-4:]]
        
    st.subheader("Residents")
    if not active_p:
        st.info("No residents found.")
    else:
        for p in active_p:
            name = p['name']
            phone = p.get('contact', '')
            rsvp = rsvp_dict.get(name.lower().strip())
            
            col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
            with col1:
                st.write(f"**{name}**")
                if rsvp:
                    if rsvp.get('response') == 'attending' and rsvp.get('checked_in'):
                        st.caption("✅ Present")
                    elif rsvp.get('response') == 'not_attending':
                        st.caption("❌ No-Show")
                    else:
                        st.caption("⏳ Pending")
            
            # Inside _render_live_checkin, inside the `for p in active_p:` loop:
            with col2:
                if st.button("👍", key=f"p_{p['id']}", disabled=is_closed, help="Mark Present"):
                    _upsert_rsvp(session['id'], name, phone, 'attending', True)
                    # 🔥 SYNC TO MAIN ATTENDANCE TABLE FOR REPORTS!
                    _sync_to_main_attendance(supabase, session, {'name': name, 'phone': phone, 'response': 'attending', 'checked_in': True, 'id': p['id']})
                    st.rerun()
            with col3:
                if st.button("👎", key=f"n_{p['id']}", disabled=is_closed, help="Mark No-Show"):
                    _upsert_rsvp(session['id'], name, phone, 'not_attending', False)
                    st.rerun()
            with col4:
                if st.button("⏳", key=f"s_{p['id']}", disabled=is_closed, help="Skip/Pending"):
                    _upsert_rsvp(session['id'], name, phone, 'maybe', False)
                    st.rerun()
                    
    st.divider()
    
    # Walk-ins Section
    st.subheader("Walk-ins")
    walkins = [r for r in rsvps if r.get('is_walk_in')]
    
    c1, c2 = st.columns([3, 1])
    with c1:
        walkin_name = st.text_input("Add walk-in name", key="walkin_name")
    with c2:
        st.write(""); st.write("")
        if st.button("➕ Add", disabled=is_closed):
            if walkin_name.strip():
                _upsert_rsvp(session['id'], walkin_name.strip(), '', 'attending', True, is_walk_in=True)
                # 🔥 SYNC WALK-INS TO REPORTS TOO!
                _sync_to_main_attendance(supabase, session, {'name': walkin_name.strip(), 'phone': '', 'response': 'attending', 'checked_in': True, 'id': 'walkin'})
                st.rerun()
                
    if walkins:
        for w in walkins:
            c1, c2 = st.columns([4, 1])
            with c1: st.write(f"🚶 **{w['name']}**")
            with c2:
                if st.button("🗑️", key=f"del_{w['id']}", disabled=is_closed):
                    _delete_rsvp(w['id'])
                    st.rerun()
    else:
        st.caption("No walk-ins added yet.")
        
    st.divider()
    
    # Footer Counters & Close Button
    confirmed = len([r for r in rsvps if r.get('response') == 'attending'])
    noshow = len([r for r in rsvps if r.get('response') == 'not_attending'])
    
    c1, c2, c3 = st.columns(3)
    c1.metric("✅ Confirmed", confirmed)
    c2.metric("❌ No-Show", noshow)
    c3.metric("⏳ Pending", len(rsvps) - confirmed - noshow)
    
    if not is_closed:
        if st.button("🔒 Close Session", type="primary", use_container_width=True):
            _close_session(session['id'])
            st.success("Session closed and locked!")
            st.rerun()
    else:
        st.success("✅ Session Closed & Locked")

# ─── UI: Create Session (Before Session) ─────────────────
def _render_session_form():
    st.subheader("➕ Create New Session")
    with st.form("create_sess"):
        acts = load_activities()
        act_names = [a['name'] for a in acts]
        activity = st.selectbox("Activity", act_names, index=0)
        date = st.date_input("Date", value=datetime.now().date())
        time = st.text_input("Time", value="7:00 PM - 9:00 PM")
        location = st.text_input("Location", value="Woodlands Zone 6")
        
        submitted = st.form_submit_button("Create Session", type="primary", use_container_width=True)
        if submitted:
            data = {
                "id": str(uuid.uuid4()), "activity_name": activity,
                "session_date": date.strftime("%Y-%m-%d"), "session_time": time,
                "location": location, "status": "open",
                "rsvp_link_token": str(uuid.uuid4())[:8],
                "created_at": datetime.now().isoformat()
            }
            supabase.table("sessions").insert(data).execute()
            st.session_state['new_session_token'] = data['rsvp_link_token']
            st.rerun()
            
    if 'new_session_token' in st.session_state:
        token = st.session_state.pop('new_session_token')
        url = _generate_rsvp_url(token)
        session = _fetch_session_by_token(token)
        msg = _generate_whatsapp_message(session, url)
        
        st.info("📋 Copy & Broadcast via WhatsApp:")
        st.code(msg, language="text")

# ─── Main Router ─────────────────────────────────────────
def show(supabase, role):
    st.title("📅 Session Check-In")
    
    query_params = st.query_params
    if query_params.get("mode") == "checkin_desk":
        sid = query_params.get("sid")
        session = supabase.table("sessions").select("*").eq("id", sid).single().execute().data
        if session:
            _render_live_checkin(session)
        else:
            st.error("Session not found.")
        return
        
    tab1, tab2 = st.tabs(["📋 Sessions", "➕ Create"])
    
    with tab1:
        sessions = _fetch_sessions()
        if not sessions:
            st.info("No sessions yet. Create one!")
        else:
            for s in sessions:
                with st.container():
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        st.markdown(f"### {s['activity_name']} — {s['session_date']}")
                        st.caption(f"{s['session_time']} | {s.get('location', '')}")
                        icon = "🟢" if s.get('status') == 'open' else "🔴"
                        st.caption(f"Status: {icon} {s.get('status', 'open').capitalize()}")
                    with c2:
                        if st.button("🔍 Live Check-In", key=f"live_{s['id']}", use_container_width=True):
                            st.query_params["mode"] = "checkin_desk"
                            st.query_params["sid"] = s['id']
                            st.rerun()
                    st.divider()
                    
    with tab2:
        _render_session_form()

show_sessions = show