"""
tab_sessions.py
Session RSVP & Check-In for Woodlands Zone 6 Community Hub
Roles: Admin (full control), Checker (check-in only)
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import uuid
import urllib.parse

# ─── WhatsApp Helpers (self-contained) ─────────────────────
def _generate_rsvp_url(token, app_url):
    """Generate public RSVP link for a session."""
    base = app_url.rstrip('/') if app_url else 'https://your-app.streamlit.app'
    return f"{base}/?mode=rsvp&tk={token}"

def _generate_whatsapp_link(phone, message):
    """Generate WhatsApp click-to-chat link. Auto-prefixes +65 if missing."""
    clean_phone = str(phone).strip().replace(" ", "").replace("-", "").lstrip("+")
    if not clean_phone.startswith('65') and len(clean_phone) == 8:
        clean_phone = '65' + clean_phone
    encoded_msg = urllib.parse.quote(message, safe='')
    return f"https://wa.me/{clean_phone}?text={encoded_msg}"

def _generate_rsvp_whatsapp_message(session, rsvp_url):
    """Generate WhatsApp invitation message for a session."""
    title = session.get('activity_name', session.get('title', 'Community Session'))
    date = session.get('session_date', 'TBA')
    time = session.get('session_time', session.get('start_time', 'TBA'))
    location = session.get('location', 'Woodlands Zone 6 Community Hub')
    return (
        f"🌳 *Woodlands Zone 6 Community Hub*\n\n"
        f"📅 *{title}*\n"
        f"🗓️ Date: {date}\n"
        f"🕐 Time: {time}\n"
        f"📍 Location: {location}\n\n"
        f"Please confirm your attendance by clicking the link below:\n"
        f"{rsvp_url}\n\n"
        f"_Tap the link → Enter your name → Submit RSVP_"
    )

def _generate_reminder_message(session, attendee_name):
    """Generate session reminder WhatsApp message."""
    title = session.get('activity_name', session.get('title', 'Community Session'))
    date = session.get('session_date', 'TBA')
    time = session.get('session_time', session.get('start_time', 'TBA'))
    location = session.get('location', 'Woodlands Zone 6 Community Hub')
    return (
        f"Hi {attendee_name}! 👋\n\n"
        f"Friendly reminder: *{title}* is coming up!\n\n"
        f"🗓️ {date}\n"
        f"🕐 {time}\n"
        f"📍 {location}\n\n"
        f"See you there! 🌳"
    )

def _generate_bulk_reminder_links(session, rsvps):
    """Generate WhatsApp links for all confirmed RSVPs."""
    links = []
    for rsvp in rsvps:
        phone = rsvp.get('phone', rsvp.get('contact', ''))
        name = rsvp.get('name', 'Resident')
        if phone:
            msg = _generate_reminder_message(session, name)
            links.append({
                'name': name,
                'phone': phone,
                'link': _generate_whatsapp_link(phone, msg)
            })
    return links

# ─── DB Helpers ────────────────────────────────────────────
def _fetch_sessions(supabase, status=None, activity=None, future_only=False):
    query = supabase.table("sessions").select("*")
    if status:
        query = query.eq("status", status)
    if activity:
        query = query.eq("activity_name", activity)
    if future_only:
        query = query.gte("session_date", datetime.now().strftime("%Y-%m-%d"))
    resp = query.order("session_date", desc=False).execute()
    return resp.data or []

def _fetch_session_by_id(supabase, session_id):
    resp = supabase.table("sessions").select("*").eq("id", session_id).single().execute()
    return resp.data

def _fetch_rsvps(supabase, session_id=None, phone=None):
    query = supabase.table("session_rsvp").select("*")
    if session_id:
        query = query.eq("session_id", session_id)
    if phone:
        query = query.eq("phone", phone)
    resp = query.execute()
    return resp.data or []

def _create_session(supabase, data):
    resp = supabase.table("sessions").insert(data).execute()
    return resp.data

def _update_session(supabase, session_id, data):
    resp = supabase.table("sessions").update(data).eq("id", session_id).execute()
    return resp.data

def _check_in_rsvp(supabase, rsvp_id, method="Manual"):
    data = {
        "checked_in": True,
        "checked_in_at": datetime.now().isoformat(),
        "check_in_method": method
    }
    resp = supabase.table("session_rsvp").update(data).eq("id", rsvp_id).execute()
    return resp.data

# ─── UI Components ─────────────────────────────────────────
def _render_session_card(sup, session, role, app_url):
    col1, col2, col3 = st.columns([3, 2, 2])

    with col1:
        st.markdown(f"### {session.get('activity_name','Untitled')}")
        st.caption(f"📅 {session.get('session_date','')} | 🕐 {session.get('session_time','')}")
        st.caption(f"📍 {session.get('location','TBA')}")
        if session.get('description'):
            st.write(session['description'])

        current_rsvps = len([r for r in _fetch_rsvps(sup, session['id']) if r.get('response')=='attending'])
        capacity = session.get('max_capacity', 0)
        if capacity > 0:
            pct = min(current_rsvps / capacity, 1.0)
            st.progress(pct, text=f"Attending: {current_rsvps}/{capacity}")
        else:
            st.caption(f"Attending: {current_rsvps} (no capacity limit)")

    with col2:
        status_color = {
            "open": "green",
            "closed": "gray",
            "cancelled": "red"
        }.get(session.get('status','open'), "gray")
        st.markdown(f"<span style='color:{status_color};font-weight:bold;'>● {session.get('status','open')}</span>", 
                   unsafe_allow_html=True)

        if role == "admin":
            with st.expander("Admin Actions"):
                new_status = st.selectbox("Status", ["open", "closed", "cancelled"], 
                                         index=["open", "closed", "cancelled"].index(session.get('status','open')),
                                         key=f"status_{session['id']}")
                if new_status != session.get('status','open') and st.button("Update", key=f"upd_{session['id']}"):
                    _update_session(sup, session['id'], {"status": new_status, "updated_at": datetime.now().isoformat()})
                    st.success("Updated!")
                    st.rerun()

                if st.button("🗑️ Delete", key=f"del_{session['id']}"):
                    sup.table("sessions").delete().eq("id", session['id']).execute()
                    st.success("Deleted!")
                    st.rerun()

    with col3:
        # WhatsApp Share
        if session.get('rsvp_link_token'):
            rsvp_url = _generate_rsvp_url(session['rsvp_link_token'], app_url)
            msg = _generate_rsvp_whatsapp_message(session, rsvp_url)

            # Use a dummy phone to generate the link structure, admin forwards it
            wa_link = _generate_whatsapp_link("6500000000", msg)
            st.link_button("📤 Share RSVP", wa_link, width='stretch')

            with st.expander("Copy Message"):
                st.code(msg, language="text")
                st.caption("Copy this text and send via WhatsApp broadcast")

        if role in ["admin", "checker"]:
            if session.get('status') == 'open':
                if st.button("🔍 Check-In Desk", key=f"ck_{session['id']}", width='stretch'):
                    st.query_params["mode"] = "checkin_desk"
                    st.query_params["sid"] = session['id']
                    st.query_params["role"] = role
                    st.rerun()
        if role == "admin":
            if st.button("📋 RSVP List", key=f"rl_{session['id']}", width='stretch'):
                st.query_params["mode"] = "rsvplist"
                st.query_params["sid"] = session['id']
                st.query_params["role"] = role
                st.rerun()

    st.divider()

def _render_checkin_desk(sup, session_id, role):
    session = _fetch_session_by_id(sup, session_id)
    if not session:
        st.error("Session not found.")
        return

    st.title(f"🔍 Check-In: {session.get('activity_name','Session')}")
    st.caption(f"{session.get('session_date','')} | {session.get('location','')}")

    if st.button("⬅️ Back to Sessions", key="ck_back"):
        for k in ['mode','sid','role']:
            if k in st.query_params:
                del st.query_params[k]
        st.rerun()

    modes = ["Manual (Dropdown)", "Phone Lookup"]
    mode = st.radio("Check-In Mode", modes, horizontal=True)

    rsvps = _fetch_rsvps(sup, session_id)
    if not rsvps:
        st.info("No RSVPs found for this session.")
        return

    df = pd.DataFrame(rsvps)

    if mode == "Manual (Dropdown)":
        pending = df[df['response'].isin(['attending', 'maybe'])]
        if pending.empty:
            st.success("All attendees have been checked in!")
            return

        options = {f"{r['name']} ({r.get('phone','')})": r['id'] for _, r in pending.iterrows()}
        selected = st.selectbox("Select Attendee", list(options.keys()))
        rsvp_id = options[selected]

        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Check In", width='stretch', type="primary"):
                _check_in_rsvp(sup, rsvp_id, "Manual")
                st.success("Checked in!")
                st.rerun()
        with col2:
            if st.button("❌ Mark No-Show", width='stretch'):
                sup.table("session_rsvp").update({
                    "response": "not_attending",
                    "updated_at": datetime.now().isoformat()
                }).eq("id", rsvp_id).execute()
                st.warning("Marked as No-Show.")
                st.rerun()

    elif mode == "Phone Lookup":
        lookup = st.text_input("Enter phone number", placeholder="81234567")
        if lookup:
            match = df[df.get('phone','').astype(str).str.contains(lookup.replace(" ",""), na=False, case=False)]
            if not match.empty:
                st.dataframe(match[['name','phone','response','checked_in']], width='stretch')
                for _, r in match.iterrows():
                    if not r.get('checked_in', False):
                        if st.button(f"Check in {r['name']}", key=f"ph_{r['id']}"):
                            _check_in_rsvp(sup, r['id'], "Phone Lookup")
                            st.rerun()
            else:
                st.warning("No matching RSVP found.")

    st.divider()
    st.subheader("📊 Live Attendance")
    c1, c2, c3, c4 = st.columns(4)
    stats = df['response'].value_counts().to_dict()
    c1.metric("Attending", stats.get('attending', 0))
    c2.metric("Checked In", df['checked_in'].sum() if 'checked_in' in df.columns else 0)
    c3.metric("Maybe", stats.get('maybe', 0))
    c4.metric("Not Attending", stats.get('not_attending', 0))

    display_df = df[['name','phone','response','checked_in','checked_in_at']].copy()
    display_df['checked_in'] = display_df['checked_in'].fillna(False)
    st.dataframe(display_df.sort_values('checked_in_at', ascending=False, na_position='last'),
                width='stretch')

def _render_rsvp_list(sup, session_id, app_url):
    session = _fetch_session_by_id(sup, session_id)
    st.title(f"📋 RSVP List: {session.get('activity_name','Session')}")

    if st.button("⬅️ Back to Sessions", key="rl_back"):
        for k in ['mode','sid','role']:
            if k in st.query_params:
                del st.query_params[k]
        st.rerun()

    rsvps = _fetch_rsvps(sup, session_id)
    if not rsvps:
        st.info("No RSVPs yet.")
        return

    df = pd.DataFrame(rsvps)

    # Export
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button("⬇️ Download CSV", csv, f"rsvps_{session_id}.csv", "text/csv")

    # Send Reminders
    attending = [r for r in rsvps if r.get('response') == 'attending' and r.get('phone')]
    if attending and app_url:
        st.subheader("📨 Send Reminders")
        if st.button("Generate WhatsApp Reminder Links", width='stretch'):
            for rsvp in attending:
                msg = _generate_reminder_message(session, rsvp.get('name','Resident'))
                link = _generate_whatsapp_link(rsvp.get('phone'), msg)
                st.markdown(f"**{rsvp.get('name')}** ({rsvp.get('phone')})")
                st.link_button("Open WhatsApp", link, key=f"wa_{rsvp['id']}")
                st.caption("Opens chat with pre-filled reminder message")

    st.dataframe(df, width='stretch')

def _render_session_form(sup, edit_session=None, app_url=None, form_key_suffix=""):
    """Create or edit session form. form_key_suffix ensures unique form keys."""
    is_edit = edit_session is not None
    st.subheader("✏️ Edit Session" if is_edit else "➕ Create New Session")

    # Unique form key based on suffix
    form_key = f"session_form_{form_key_suffix}"

    with st.form(form_key):
        title = st.text_input("Activity Name *", value=edit_session.get('activity_name','') if is_edit else "")
        date = st.date_input("Date *", 
                            value=datetime.strptime(edit_session['session_date'], "%Y-%m-%d").date() if is_edit and edit_session.get('session_date') else datetime.now().date())
        time = st.text_input("Time (e.g., 9:00 AM - 11:00 AM)", 
                            value=edit_session.get('session_time','') if is_edit else "")
        location = st.text_input("Location", value=edit_session.get('location','') if is_edit else "Woodlands Zone 6")
        desc = st.text_area("Description", value=edit_session.get('description','') if is_edit else "")
        max_cap = st.number_input("Max Capacity (0 = unlimited)", min_value=0, 
                                 value=edit_session.get('max_capacity', 0) if is_edit else 0)
        status = st.selectbox("Status", ["open", "closed", "cancelled"], 
                             index=["open", "closed", "cancelled"].index(edit_session.get('status','open')) if is_edit else 0)

        submitted = st.form_submit_button("💾 Save Session", width='stretch')

        if submitted:
            if not title:
                st.error("Activity name is required.")
                return

            data = {
                "activity_name": title,
                "session_date": date.strftime("%Y-%m-%d"),
                "session_time": time,
                "location": location,
                "description": desc,
                "max_capacity": int(max_cap),
                "status": status,
                "updated_at": datetime.now().isoformat()
            }

            if is_edit:
                _update_session(sup, edit_session['id'], data)
                st.success("Session updated!")
            else:
                data["id"] = str(uuid.uuid4())
                data["rsvp_link_token"] = str(uuid.uuid4())[:8]  # Short token for WhatsApp
                data["created_at"] = datetime.now().isoformat()
                _create_session(sup, data)
                st.success("Session created!")

                # Show RSVP link
                rsvp_url = _generate_rsvp_url(data["rsvp_link_token"], app_url)
                st.info("RSVP Link generated:")
                st.code(rsvp_url, language="text")

                # Show WhatsApp share option
                msg = _generate_rsvp_whatsapp_message(data, rsvp_url)
                st.subheader("📤 Share via WhatsApp")
                st.code(msg, language="text")
                st.caption("Copy this message and send to your WhatsApp groups / broadcast list")

            st.rerun()

# ─── Main Tab Router ───────────────────────────────────────
def show(supabase, role):
    """Main entry point for tab_sessions."""
    from config import APP_URL
    app_url = APP_URL

    sup = supabase

    # URL params for deep linking
    query_params = st.query_params

    # ─── Check-In Desk Deep Link ───────────────────────────
    if query_params.get("mode") == "checkin_desk" and role in ["admin", "checker"]:
        _render_checkin_desk(sup, query_params.get("sid"), role)
        return

    # ─── RSVP List Deep Link ───────────────────────────────
    if query_params.get("mode") == "rsvplist" and role == "admin":
        _render_rsvp_list(sup, query_params.get("sid"), app_url)
        return

    # ─── Main Tab UI ───────────────────────────────────────
    st.title("📅 Session RSVP & Check-In")

    if role == "admin":
        tab_list = ["📋 All Sessions", "➕ Create Session", "📊 Analytics"]
    elif role == "checker":
        tab_list = ["📋 Today's Sessions", "🔍 Check-In Desk"]
    else:
        st.warning("You don't have access to this tab.")
        return

    tabs = st.tabs(tab_list)

    # ─── Admin: All Sessions ───────────────────────────────
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
                st.write("")
                st.write("")
                future_only = st.toggle("Future Only")

            sessions = _fetch_sessions(sup, 
                                     status=filter_status if filter_status != "All" else None,
                                     activity=filter_activity if filter_activity != "All" else None,
                                     future_only=future_only)

            if not sessions:
                st.info("No sessions found.")
            else:
                for s in sessions:
                    _render_session_card(sup, s, role, app_url)

                with st.expander("✏️ Edit a Session"):
                    edit_id = st.selectbox("Select Session", 
                                          [s['id'] for s in sessions],
                                          format_func=lambda x: next((s['activity_name'] for s in sessions if s['id']==x), x))
                    if edit_id:
                        session_to_edit = next((s for s in sessions if s['id']==edit_id), None)
                        # Use unique form key for edit form
                        _render_session_form(sup, session_to_edit, app_url, form_key_suffix="edit")

        with tabs[1]:
            # Use unique form key for create form
            _render_session_form(sup, app_url=app_url, form_key_suffix="create")

        with tabs[2]:
            st.subheader("📊 Session Analytics")
            all_sessions = _fetch_sessions(sup)
            all_rsvps = sup.table("session_rsvp").select("*").execute().data or []

            if all_sessions and all_rsvps:
                df_sess = pd.DataFrame(all_sessions)
                df_rsvp = pd.DataFrame(all_rsvps)

                merged = df_rsvp.merge(df_sess[['id','activity_name','session_date']], 
                                      left_on='session_id', right_on='id', suffixes=('','_session'))

                c1, c2, c3 = st.columns(3)
                c1.metric("Total Sessions", len(all_sessions))
                c2.metric("Total RSVPs", len(all_rsvps))
                attended = df_rsvp['checked_in'].sum() if 'checked_in' in df_rsvp.columns else 0
                c3.metric("Checked-In", int(attended))

                if 'activity_name' in merged.columns:
                    st.bar_chart(merged['activity_name'].value_counts())

                if 'session_date' in merged.columns:
                    merged['session_date'] = pd.to_datetime(merged['session_date'])
                    trend = merged.groupby(['session_date', 'response']).size().unstack(fill_value=0)
                    st.line_chart(trend)
            else:
                st.info("Not enough data for analytics.")

    # ─── Checker: Today's Sessions ─────────────────────────
    elif role == "checker":
        with tabs[0]:
            today = datetime.now().strftime("%Y-%m-%d")
            sessions = _fetch_sessions(sup)
            today_sessions = [s for s in sessions if s.get('session_date') == today]

            if not today_sessions:
                st.info("No sessions scheduled for today.")
                st.subheader("Upcoming Sessions")
                upcoming = _fetch_sessions(sup, future_only=True)[:5]
                for s in upcoming:
                    st.write(f"• **{s.get('activity_name','')}** — {s.get('session_date','')}")
            else:
                for s in today_sessions:
                    st.subheader(s.get('activity_name','Session'))
                    st.caption(f"{s.get('session_time','')} @ {s.get('location','TBA')}")
                    rsvps = _fetch_rsvps(sup, s['id'])
                    attending = len([r for r in rsvps if r.get('response')=='attending'])
                    checked_in = len([r for r in rsvps if r.get('checked_in')])

                    col1, col2, col3 = st.columns(3)
                    col1.metric("Attending", attending)
                    col2.metric("Checked In", checked_in)
                    col3.metric("Pending", attending - checked_in)

                    if st.button("🔍 Open Check-In Desk", key=f"ck_today_{s['id']}", width='stretch'):
                        st.query_params["mode"] = "checkin_desk"
                        st.query_params["sid"] = s['id']
                        st.query_params["role"] = role
                        st.rerun()
                    st.divider()

        with tabs[1]:
            sessions = _fetch_sessions(sup)
            active = [s for s in sessions if s.get('status') == 'open']
            if active:
                selected = st.selectbox("Select Session", active, 
                                       format_func=lambda x: f"{x.get('activity_name','')} ({x.get('session_date','')})")
                _render_checkin_desk(sup, selected['id'], role)
            else:
                st.info("No active sessions available for check-in.")


# Alias for backward compatibility with app.py import
show_sessions = show
