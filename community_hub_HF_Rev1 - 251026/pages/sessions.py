"""
tab_sessions.py
Session RSVP & Live Check-In for Woodlands Zone 6 Community Hub
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone
import uuid
import urllib.parse
from config import supabase, DB_CONNECTED, APP_URL, load_activities
from utils import clean_phone_number, find_participant_by_phone, mask_phone

# ─── Helpers ────────────────────────────────────────────
def _generate_rsvp_url(token):
    base = APP_URL.rstrip('/') if APP_URL else 'https://your-app.streamlit.app'
    return f"{base}/?mode=rsvp&tk={token}"

def _generate_whatsapp_link(phone, message):
    clean_phone = str(phone).strip().replace(" ", "").replace("-", "").lstrip("+")
    if not clean_phone.startswith('65') and len(clean_phone) == 8:
        clean_phone = '65' + clean_phone
    encoded_msg = urllib.parse.quote(message, safe='')
    return f"https://wa.me/{clean_phone}?text={encoded_msg}"

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
    try:
        date_str = session.get('session_date')
        time_str = session.get('session_time', '23:59')
        start_time_str = time_str.split('-')[0].strip()
        try:
            start_time = datetime.strptime(start_time_str, "%I:%M %p").time()
        except:
            start_time = datetime.strptime(start_time_str, "%H:%M").time()
        session_dt = datetime.combine(datetime.strptime(date_str, "%Y-%m-%d").date(), start_time)
        return datetime.now(timezone(timedelta(hours=8))) > session_dt
    except:
        return False

def _auto_close_expired_sessions(sup):
    try:
        open_sessions = sup.table('sessions').select('*').eq('status', 'open').execute().data
        for sess in open_sessions:
            if _is_session_expired(sess):
                sup.table('sessions').update({
                    'status': 'closed', 
                    'updated_at': datetime.now(timezone(timedelta(hours=8))).isoformat()
                }).eq('id', sess['id']).execute()
    except Exception as e:
        print(f"Auto-close error: {e}")

# ─── DB Functions ────────────────────────────────────────
def _fetch_sessions(sup, status=None, activity=None, future_only=False):
    query = sup.table("sessions").select("*")
    if status: query = query.eq("status", status)
    if activity: query = query.eq("activity_name", activity)
    if future_only: query = query.gte("session_date", datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d"))
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
        "updated_at": datetime.now(timezone(timedelta(hours=8))).isoformat()
    }
    if existing:
        sup.table("session_rsvp").update(data).eq("id", existing[0]['id']).execute()
    else:
        data["id"] = str(uuid.uuid4())
        data["created_at"] = datetime.now(timezone(timedelta(hours=8))).isoformat()
        sup.table("session_rsvp").insert(data).execute()

def _delete_rsvp(sup, rsvp_id):
    sup.table("session_rsvp").delete().eq("id", rsvp_id).execute()

def _close_session(sup, session_id):
    sup.table("sessions").update({"status": "closed", "updated_at": datetime.now(timezone(timedelta(hours=8))).isoformat()}).eq("id", session_id).execute()

# ─── UI: Session Card ────────────────────────────────────
def _render_session_card(sup, session, role, app_url):
    st.markdown(f"### {session.get('activity_name','Untitled')} — {session.get('session_date','')}")
    st.caption(f"{session.get('session_time','')} | {session.get('location','TBA')}")
    
    icon = "🟢" if session.get('status') == 'open' else "🔴"
    st.caption(f"Status: {icon} {session.get('status', 'open').capitalize()}")
    
    rsvps = _fetch_rsvps(sup, session['id'])
    confirmed = len([r for r in rsvps if r.get('response') == 'attending'])
    st.caption(f"Attending: {confirmed}")

# ─── UI: Live Check-In (FULL ROSTER) ────────────────────
def _render_live_checkin(sup, session):
    st.title(f"🔍 Live Check-In Desk: {session['activity_name']}")
    st.caption(f"{session['session_date']} | {session['session_time']} | {session.get('location', '')}")
    
    is_closed = session.get('status') == 'closed' or _is_session_expired(session)
    if is_closed:
        st.warning("⚠️ Session is CLOSED or EXPIRED. Check-in is locked.")
    
    # ─── Fetch All RSVPs ──────────────────────────────────────
    rsvps = _fetch_rsvps(sup, session['id'])
    
    attending = [r for r in rsvps if r.get('response') == 'attending']
    maybe = [r for r in rsvps if r.get('response') == 'maybe']
    noshow = [r for r in rsvps if r.get('response') == 'not_attending']
    checked_in_count = len([r for r in attending if r.get('checked_in')])
    attending_count = len(attending)
    
    c1, c2, c3 = st.columns(3)
    c1.metric("✅ Checked-In", checked_in_count)
    c2.metric("📋 Attending", attending_count)
    c3.metric("⏳ Maybe", len(maybe))
    
    st.divider()
    
    # ─── 1. ROSTER: Attending Residents (Yellow / Green) ────
    st.subheader("📋 Attending Roster")
    if attending:
        for rsvp in attending:
            rsvp_name = rsvp.get('name', 'Unknown')
            rsvp_phone = rsvp.get('phone', 'No Phone')
            rsvp_checked_in = rsvp.get('checked_in', False)
            
            participant_id = None
            try:
                res = sup.table('participants').select('id').eq('name', rsvp_name).execute()
                if res.data:
                    participant_id = res.data[0]['id']
            except:
                pass
            
            if rsvp_checked_in:
                # ✅ Already Checked In (Green)
                st.markdown(f"""
                <div style="background: #d4edda; border: 1px solid #c3e6cb; border-radius: 10px; padding: 15px; margin: 5px 0; opacity: 0.8;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <h4 style="margin:0; color: #155724;">✅ {rsvp_name}</h4>
                            <div style="font-size:12px; color: #666;">
                                📞 {mask_phone(rsvp_phone)} | 🆔 {participant_id[:8] if participant_id else 'N/A'}...
                            </div>
                        </div>
                        <div style="color: #155724; font-weight: bold;">Checked In</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                # ⏳ Pending Check-In (Yellow) - Direct Check-In Button
                st.markdown(f"""
                <div style="background: #fff3cd; border: 1px solid #ffeeba; border-radius: 10px; padding: 15px; margin: 5px 0;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <h4 style="margin:0; color: #856404;">⏳ {rsvp_name}</h4>
                            <div style="font-size:12px; color: #666;">
                                📞 {mask_phone(rsvp_phone)} | 🆔 {participant_id[:8] if participant_id else 'N/A'}...
                            </div>
                        </div>
                        <div>
                            <form action="" method="post">
                                <input type="hidden" name="action" value="mark_present">
                                <input type="hidden" name="session_id" value="{session['id']}">
                                <input type="hidden" name="name" value="{rsvp_name}">
                                <input type="hidden" name="phone" value="{rsvp_phone}">
                                <button type="submit" style="background: #28a745; color: white; border: none; padding: 8px 20px; border-radius: 5px; font-weight: bold; cursor: pointer;">
                                    ✅ Mark Present
                                </button>
                            </form>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("No residents have RSVP'd 'Attending' yet.")

    st.divider()
    
    # ─── 2. ROSTER: Maybe Residents (Grey) ────────────────────
    if maybe:
        st.subheader("⏳ Maybe (Awaiting Confirmation)")
        for rsvp in maybe:
            rsvp_name = rsvp.get('name', 'Unknown')
            rsvp_phone = rsvp.get('phone', 'No Phone')
            
            st.markdown(f"""
            <div style="background: #e2e3e5; border: 1px solid #d6d8db; border-radius: 10px; padding: 15px; margin: 5px 0;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <h4 style="margin:0; color: #383d41;">⏳ {rsvp_name}</h4>
                        <div style="font-size:12px; color: #666;">📞 {mask_phone(rsvp_phone)}</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    # ─── 3. ROSTER: Not Attending (Red) ──────────────────────
    if noshow:
        st.subheader("🚫 Not Attending")
        for rsvp in noshow:
            rsvp_name = rsvp.get('name', 'Unknown')
            st.markdown(f"""
            <div style="background: #f8d7da; border: 1px solid #f5c6cb; border-radius: 10px; padding: 10px; margin: 5px 0; opacity: 0.6;">
                <h5 style="margin:0; color: #721c24;">🚫 {rsvp_name}</h5>
            </div>
            """, unsafe_allow_html=True)

    st.divider()

    # ─── 4. Walk-in Search (Fallback) ────────────────────────
    st.subheader("📱 Search Resident (Walk-in / Not on the list)")
    search_query = st.text_input("Enter 8-digit phone or Name", placeholder="e.g., 91234567 or SEONG FATT", key="live_search")
    
    selected_resident = None
    
    if search_query:
        clean_phone = clean_phone_number(search_query)
        if len(clean_phone) >= 8:
            selected_resident = find_participant_by_phone(clean_phone)
        if not selected_resident:
            participants = st.session_state.get('participants', [])
            s = search_query.lower()
            matches = [p for p in participants if p.get('active', True) and s in p.get('name', '').lower()]
            if matches:
                match_dict = {f"{p['name']} (ID: {p['id'][:8]}...)": p for p in matches}
                selected_label = st.selectbox("Multiple found. Select one:", list(match_dict.keys()), key="live_match_select")
                if selected_label:
                    selected_resident = match_dict[selected_label]

    if selected_resident:
        status_text = '⭐ Regular' if not selected_resident.get('is_new') else '🆕 New'
        full_contact = selected_resident.get('contact', 'N/A')
        if full_contact == 'NO_PHONE':
            full_contact = '📵 No Phone'
            
        st.markdown(f"""
        <div style="background: #e8f5e9; border: 2px solid #4caf50; padding: 20px; border-radius: 15px; margin: 15px 0; box-shadow: 0 4px 8px rgba(76, 175, 80, 0.2);">
            <h3 style="margin: 0 0 5px 0; color: #1a1a1a;">👤 Walk-in: {selected_resident['name']}</h3>
            <div style="display: flex; flex-wrap: wrap; gap: 15px; font-size: 14px; color: #555;">
                <span>🆔 ID: <code>{selected_resident['id']}</code></span>
                <span>📞 Phone: <strong>{full_contact}</strong></span>
                <span>📋 Status: {status_text}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        acts = load_activities()
        act_config = next((a for a in acts if a['name'] == session['activity_name']), None)
        s1_label = act_config.get('session_1_label', 'Session 1') if act_config else 'Session 1'
        s2_label = act_config.get('session_2_label', 'Session 2') if act_config else 'Session 2'
        
        session_options = [s1_label, s2_label, "Both Sessions"]
        selected_session = st.radio("Which session?", session_options, horizontal=True, key="walkin_session_select")
        
        if selected_session == s1_label:
            s1, s2 = True, False
        elif selected_session == s2_label:
            s1, s2 = False, True
        else:
            s1, s2 = True, True

        if st.button("✅ Mark Walk-in Present", type="primary", use_container_width=True, disabled=is_closed):
            try:
                _upsert_rsvp(sup, session['id'], selected_resident['name'], selected_resident.get('contact', ''), 'attending', True, is_walk_in=True, s1=s1, s2=s2)
                
                existing_sess_att = sup.table('session_attendance').select("id") \
                    .eq('session_id', session['id']) \
                    .eq('participant_id', selected_resident['id']) \
                    .execute()
                    
                if existing_sess_att.data:
                    sup.table('session_attendance').update({
                        "status": "checked_in",
                        "marked_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
                        "marked_by": st.session_state.get('user_role', 'admin')
                    }).eq('id', existing_sess_att.data[0]['id']).execute()
                else:
                    sup.table('session_attendance').insert({
                        "session_id": session['id'],
                        "participant_id": selected_resident['id'],
                        "name": selected_resident['name'],
                        "status": "checked_in",
                        "marked_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
                        "marked_by": st.session_state.get('user_role', 'admin')
                    }).execute()

                formatted_date = session.get('session_date')
                existing_att = sup.table('attendance').select("*") \
                    .eq('participant_id', selected_resident['id']) \
                    .eq('date', formatted_date) \
                    .eq('source', session['activity_name']) \
                    .execute()
                
                if existing_att.data:
                    record = existing_att.data[0]
                    updates = {
                        "session_1": record.get('session_1', False) or s1,
                        "session_2": record.get('session_2', False) or s2,
                        "timestamp": datetime.now(timezone(timedelta(hours=8))).isoformat()
                    }
                    sup.table('attendance').update(updates).eq('id', record['id']).execute()
                else:
                    sup.table('attendance').insert({
                        "participant_id": selected_resident['id'],
                        "name": selected_resident['name'],
                        "date": formatted_date,
                        "session_1": s1,
                        "session_2": s2,
                        "timestamp": datetime.now(timezone(timedelta(hours=8))).isoformat(),
                        "self_checkin": False,
                        "source": session['activity_name']
                    }).execute()
                    
                st.success(f"✅ Walk-in {selected_resident['name']} marked Present!")
                # 🔥 Professional refresh (no balloons)
                st.rerun()
            except Exception as e:
                st.error(f"Error saving walk-in: {e}")

    st.divider()
    if not is_closed:
        if st.button("🔒 Close Session", type="primary", use_container_width=True):
            _close_session(sup, session['id'])
            st.success("Session closed and locked!")
            st.rerun()
    else:
        st.success("✅ Session Closed & Locked")

# ─── UI: Create Session ──────────────────────────────────
def _render_session_form(sup, app_url=None, form_key_suffix=""):
    st.subheader("➕ Create New Session")
    with st.form(f"create_sess_{form_key_suffix}"):
        acts = load_activities()
        act_names = [a['name'] for a in acts]
        activity = st.selectbox("Activity", act_names, index=0)
        date = st.date_input("Date", value=datetime.now(timezone(timedelta(hours=8))).date())
        time = st.text_input("Time", value="7:00 PM - 9:00 PM")
        location = st.text_input("Location", value="Woodlands Zone 6")
        
        submitted = st.form_submit_button("Create Session", type="primary", use_container_width=True)
        if submitted:
            data = {
                "id": str(uuid.uuid4()), "activity_name": activity,
                "session_date": date.strftime("%Y-%m-%d"), "session_time": time,
                "location": location, "status": "open",
                "rsvp_link_token": str(uuid.uuid4())[:8],
                "created_at": datetime.now(timezone(timedelta(hours=8))).isoformat()
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

    # 🔥 PHASE 2: Automatically close any sessions that have expired!
    _auto_close_expired_sessions(sup)

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

        # ─── Main Tab UI ──
    # 🔥 FIX: Allow BOTH Admin and Chairman to manage and create sessions
    if role in ["admin", "chairman"]:
        tab_list = ["📋 All Sessions", "➕ Create Session", "📊 Analytics"]
    elif role == "checker":
        tab_list = ["📋 Today's Sessions", "🔍 Check-In Desk"]
    else:
        st.warning("You don't have access to this tab.")
        return

    tabs = st.tabs(tab_list)

     # 🔥 FIX: Link the content rendering to BOTH Admin and Chairman
    if role in ["admin", "chairman"]:
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
                        if st.button("🔍 Open Live Check-In Desk", key=f"open_live_{s['id']}", use_container_width=True):
                            st.session_state['live_checkin_session_id'] = s['id']
                            st.rerun()
                    st.divider()

                        # ── Resend RSVP Links Feature ───────────────────────────
            st.divider()
            st.subheader("📩 Resend RSVP Links to Residents")
            st.caption("Find a session and resend RSVP links to attendees who lost the original link")

            # Re-fetch sessions for this section
            all_sessions_for_resend = _fetch_sessions(sup, status=None, activity=None, future_only=False)

            if all_sessions_for_resend:
                resend_session = st.selectbox(
                    "Select Session to Resend Links",
                    all_sessions_for_resend,
                    format_func=lambda x: f"{x['activity_name']} - {x['session_date']} ({x['status']})",
                    key="resend_session_select"
                )
                if resend_session:
                    token = resend_session.get('rsvp_link_token')
                    if token:
                        rsvp_url = f"{app_url}/?mode=rsvp&tk={token}"
                        st.code(rsvp_url, language="text", line_numbers=False)
                        c1, c2 = st.columns([1, 3])
                        with c1:
                            if st.button(" Copy Link", key=f"copy_resend_{resend_session['id']}"):
                                st.success("Link copied to clipboard!")
                        # Get all RSVPs for this session
                        rsvps = _fetch_rsvps(sup, resend_session['id'])
                        attending = [r for r in rsvps if r.get('response') == 'attending' and r.get('phone')]
                        if attending:
                            st.write(f"**{len(attending)} residents attending with phone numbers:**")
                            if st.button("📱 Generate WhatsApp Resend Links", type="primary", key=f"wa_resend_btn_{resend_session['id']}"):
                                for rsvp in attending:
                                    phone = rsvp.get('phone', '')
                                    name = rsvp.get('name', 'Resident')
                                    # Generate personalized message
                                    msg = f"Hi {name}! Here's your RSVP link for {resend_session['activity_name']} on {resend_session['session_date']}:\n\n{rsvp_url}\n\nTap to confirm your attendance!"
                                    wa_link = _generate_whatsapp_link(phone, msg)
                                    with st.expander(f"📲 {name} ({phone})", expanded=False):
                                        st.code(msg, language="text", line_numbers=False)
                                        st.link_button(" Open WhatsApp", wa_link, key=f"wa_link_{rsvp['id']}")
                        else:
                            st.info("No attending residents with phone numbers found for this session.")
                    else:
                        st.warning("This session doesn't have an RSVP link token.")
            else:
                st.info("No sessions available.")
            
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
            today = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
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