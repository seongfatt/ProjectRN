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

def _sync_to_main_attendance(sup, session, rsvp, s1=True, s2=False):
    """Syncs a checked-in RSVP to the main 'attendance' table with S1/S2 flags."""
    if rsvp.get('response') != 'attending' or not rsvp.get('checked_in'):
        return
    
    session_date = session.get('session_date')
    activity_name = session.get('activity_name')
    name = rsvp.get('name', '').strip().upper()
    phone = rsvp.get('phone', '').strip()
    
    pid = None
    try:
        res = sup.table('participants').select('id').eq('name', name).execute()
        if res.data:
            pid = res.data[0]['id']
        elif phone and len(phone) >= 4:
            all_p = sup.table('participants').select('id', 'contact').execute()
            for p in all_p.data:
                if str(p.get('contact', '')).replace(' ', '').endswith(phone[-4:]):
                    pid = p['id']
                    break
    except:
        pass
        
    if not pid:
        pid = f"WALKIN_{rsvp.get('id', 'unknown')}"
        
    try:
        existing = sup.table('attendance').select('id') \
            .eq('participant_id', pid).eq('date', session_date).eq('source', activity_name).execute()
        
        if not existing.data:
            sup.table('attendance').insert({
                "participant_id": pid,
                "name": name,
                "date": session_date,
                "session_1": s1,
                "session_2": s2,
                "timestamp": datetime.now().isoformat(),
                "self_checkin": False,
                "source": activity_name
            }).execute()
    except Exception as e:
        print(f"Sync to main attendance error: {e}")

# ─── DB Functions ────────────────────────────────────────
def _fetch_sessions(sup, status=None, activity=None, future_only=False):
    query = sup.table("sessions").select("*")
    if status: query = query.eq("status", status)
    if activity: query = query.eq("activity_name", activity)
    if future_only: query = query.gte("session_date", datetime.now().strftime("%Y-%m-%d"))
    return query.order("session_date", desc=False).execute().data or []

def _fetch_session_by_id(sup, session_id):
    resp = sup.table("sessions").select("*").eq("id", session_id).single().execute()
    return resp.data if resp.data else None

def _fetch_session_by_token(token):
    resp = supabase.table("sessions").select("*").eq("rsvp_link_token", token).single().execute()
    return resp.data if resp.data else None

def _fetch_rsvps(sup, session_id):
    return sup.table("session_rsvp").select("*").eq("session_id", session_id).execute().data or []

def _upsert_rsvp(sup, session_id, name, phone, response, checked_in, is_walk_in=False, s1=True, s2=False):
    existing = sup.table("session_rsvp").select("*").eq("session_id", session_id).eq("name", name).execute().data
    data = {
        "session_id": session_id, "name": name, "phone": phone,
        "response": response, "checked_in": checked_in, "is_walk_in": is_walk_in,
        "session_1": s1, "session_2": s2,
        "updated_at": datetime.now().isoformat()
    }
    if existing:
        sup.table("session_rsvp").update(data).eq("id", existing[0]['id']).execute()
    else:
        data["id"] = str(uuid.uuid4())
        data["created_at"] = datetime.now().isoformat()
        sup.table("session_rsvp").insert(data).execute()

def _delete_rsvp(sup, rsvp_id):
    sup.table("session_rsvp").delete().eq("id", rsvp_id).execute()

def _close_session(sup, session_id):
    sup.table("sessions").update({"status": "closed", "updated_at": datetime.now().isoformat()}).eq("id", session_id).execute()

# ─── UI: Session Card ────────────────────────────────────
def _render_session_card(sup, session, role, app_url):
    st.markdown(f"### {session.get('activity_name','Untitled')} — {session.get('session_date','')}")
    st.caption(f"{session.get('session_time','')} | {session.get('location','TBA')}")
    
    icon = "🟢" if session.get('status') == 'open' else "🔴"
    st.caption(f"Status: {icon} {session.get('status', 'open').capitalize()}")
    
    rsvps = _fetch_rsvps(sup, session['id'])
    confirmed = len([r for r in rsvps if r.get('response') == 'attending'])
    st.caption(f"Attending: {confirmed}")

# ─── UI: Live Check-In (At Venue) ────────────────────────
def _render_live_checkin(sup, session):
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
        
    rsvps = _fetch_rsvps(sup, session['id'])
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
            
            with col2:
                if st.button("👍", key=f"p_{p['id']}", disabled=is_closed, help="Mark Present"):
                    _upsert_rsvp(sup, session['id'], name, phone, 'attending', True, s1=True, s2=False)
                    _sync_to_main_attendance(sup, session, {'name': name, 'phone': phone, 'response': 'attending', 'checked_in': True, 'id': p['id']}, s1=True, s2=False)
                    st.rerun()
            with col3:
                if st.button("👎", key=f"n_{p['id']}", disabled=is_closed, help="Mark No-Show"):
                    _upsert_rsvp(sup, session['id'], name, phone, 'not_attending', False)
                    st.rerun()
            with col4:
                if st.button("⏳", key=f"s_{p['id']}", disabled=is_closed, help="Skip/Pending"):
                    _upsert_rsvp(sup, session['id'], name, phone, 'maybe', False)
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
                _upsert_rsvp(sup, session['id'], walkin_name.strip(), '', 'attending', True, is_walk_in=True, s1=True, s2=False)
                _sync_to_main_attendance(sup, session, {'name': walkin_name.strip(), 'phone': '', 'response': 'attending', 'checked_in': True, 'id': 'walkin'}, s1=True, s2=False)
                st.rerun()
                
    if walkins:
        for w in walkins:
            c1, c2 = st.columns([4, 1])
            with c1: st.write(f"🚶 **{w['name']}**")
            with c2:
                if st.button("🗑️", key=f"del_{w['id']}", disabled=is_closed):
                    _delete_rsvp(sup, w['id'])
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
            _close_session(sup, session['id'])
            st.success("Session closed and locked!")
            st.rerun()
    else:
        st.success("✅ Session Closed & Locked")

# ─── UI: Create Session (Before Session) ─────────────────
def _render_session_form(sup, app_url=None, form_key_suffix=""):
    st.subheader("➕ Create New Session")
    with st.form(f"create_sess_{form_key_suffix}"):
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
            sup.table("sessions").insert(data).execute()
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
    """Main entry point for tab_sessions."""
    app_url = APP_URL
    sup = supabase

    if 'live_checkin_session_id' not in st.session_state:
        st.session_state['live_checkin_session_id'] = None

    st.title("📅 Session RSVP & Check-In")

    # 🔥 PINNED LIVE CHECK-IN DESK
    if st.session_state['live_checkin_session_id']:
        active_sid = st.session_state['live_checkin_session_id']
        session = _fetch_session_by_id(sup, active_sid)
        
        if session:
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #ff416c, #ff4b2b); color: white; padding: 15px; border-radius: 10px; margin-bottom: 15px; text-align: center;">
                <h2 style="color:white; margin:0;">🔴 LIVE CHECK-IN ACTIVE</h2>
                <p style="margin:5px 0 0 0; font-size:16px;">{session['activity_name']} | {session['session_date']}</p>
            </div>
            """, unsafe_allow_html=True)
            
            _render_live_checkin(sup, session)
            
            if st.button("🚪 Exit Live Check-In & Return to List", use_container_width=True):
                st.session_state['live_checkin_session_id'] = None
                st.rerun()
            st.divider()
        else:
            st.session_state['live_checkin_session_id'] = None

    # ─── Main Tab UI ───
    if role == "admin":
        tab_list = ["📋 All Sessions", "➕ Create Session", "📊 Analytics"]
    elif role == "checker":
        tab_list = ["📋 Today's Sessions", "🔍 Check-In Desk"]
    else:
        st.warning("You don't have access to this tab.")
        return

    tabs = st.tabs(tab_list)

    if role == "admin":
        with tabs[0]:
            col1, col2, col3 = st.columns([2, 2, 1])
            with col1:
                try:
                    acts = sup.table('activities').select('name').execute().data or []
                    act_names = [a['name'] for a in acts]
                except:
                    act_names = []
                filter_activity = st.selectbox("Filter by Activity", ["All"] + act_names)
            with col2:
                filter_status = st.selectbox("Filter by Status", ["All", "open", "closed", "cancelled"])
            with col3:
                st.write(" "); st.write(" ")
                future_only = st.toggle("Future Only")

            sessions = _fetch_sessions(sup, 
                                     status=filter_status if filter_status != "All" else None,
                                     activity=filter_activity if filter_activity != "All" else None,
                                     future_only=future_only)

            if not sessions:
                st.info("No sessions found.")
            else:
                for s in sessions:
                    with st.container():
                        _render_session_card(sup, s, role, app_url)
                        # 🔥 Open Live Desk Button
                        if st.button("🔍 Open Live Check-In Desk", key=f"open_live_{s['id']}", use_container_width=True):
                            st.session_state['live_checkin_session_id'] = s['id']
                            st.rerun()
                    st.divider()

        with tabs[1]:
            _render_session_form(sup, app_url=app_url, form_key_suffix="create")

        with tabs[2]:
            st.subheader("📊 Session Analytics")
            all_sessions = _fetch_sessions(sup)
            all_rsvps = sup.table("session_rsvp").select("*").execute().data or []

            if all_sessions and all_rsvps:
                df_sess = pd.DataFrame(all_sessions)
                df_rsvp = pd.DataFrame(all_rsvps)
                c1, c2, c3 = st.columns(3)
                c1.metric("Total Sessions", len(all_sessions))
                c2.metric("Total RSVPs", len(all_rsvps))
                attended = df_rsvp['checked_in'].sum() if 'checked_in' in df_rsvp.columns else 0
                c3.metric("Checked-In", int(attended))
            else:
                st.info("Not enough data for analytics.")

    elif role == "checker":
        with tabs[0]:
            today = datetime.now().strftime("%Y-%m-%d")
            sessions = _fetch_sessions(sup)
            today_sessions = [s for s in sessions if s.get('session_date') == today]

            if not today_sessions:
                st.info("No sessions scheduled for today.")
            else:
                for s in today_sessions:
                    st.subheader(s.get('activity_name','Session'))
                    st.caption(f"{s.get('session_time','')} @ {s.get('location','TBA')}")
                    if st.button("🔍 Open Live Check-In Desk", key=f"ck_today_{s['id']}", use_container_width=True):
                        st.session_state['live_checkin_session_id'] = s['id']
                        st.rerun()
                    st.divider()

show_sessions = show