from sys import prefix
from tracemalloc import start

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from config import supabase, load_activities

def show_reports(selected_date):
    st.header("Attendance Reports")

    acts = load_activities()
    act_names = [a['name'] for a in acts]
    activity = st.selectbox("Activity Filter", ["All Activities"] + act_names)

    report_type = st.radio("Period", ["Daily", "Weekly", "Monthly", "Yearly", "Custom"], horizontal=True)

    if report_type == "Daily":
        start = end = selected_date
    elif report_type == "Weekly":
        start = selected_date - timedelta(days=selected_date.weekday())
        end = start + timedelta(days=6)
    elif report_type == "Monthly":
        start = selected_date.replace(day=1)
        nxt = (selected_date.month % 12) + 1
        yr = selected_date.year + (selected_date.month // 12)
        end = datetime(yr, nxt, 1) - timedelta(days=1)
    elif report_type == "Yearly":
        start = datetime(selected_date.year, 1, 1); end = datetime(selected_date.year, 12, 31)
    else:
        c1, c2 = st.columns(2)
        with c1: start = st.date_input("Start", value=selected_date - timedelta(days=7))
        with c2: end = st.date_input("End", value=selected_date)

    st.info(f"Period: {start.strftime('%d %b %Y')} to {end.strftime('%d %b %Y')}")
    st.divider()

    @st.cache_data(ttl=60)
    def load_data(s, e, act):
        try:
            q = supabase.table('attendance').select('*').gte('date', str(s)).lte('date', str(e))
            if act != "All Activities": q = q.eq('source', act)
            return q.execute().data
        except: return []

    data = load_data(start, end, activity)
    if not data: st.info("No records found"); return

    df = pd.DataFrame(data)
    df['date'] = pd.to_datetime(df['date']).dt.strftime('%d %b %Y')

    total = len(data)
    unique = len(set(r['participant_id'] for r in data))
    s1 = sum(1 for r in data if r.get('session_1'))
    s2 = sum(1 for r in data if r.get('session_2'))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Records", total); c2.metric("Unique", unique)
    c3.metric("Session 1", s1); c4.metric("Session 2", s2)
    st.divider()

    st.subheader("Detailed Records")
    disp = df[['date', 'name', 'session_1', 'session_2', 'source', 'timestamp']].copy()
    disp.columns = ['Date', 'Name', 'S1', 'S2', 'Activity', 'Time']
    # For display use text, for CSV use Yes/No
    disp['S1'] = disp['S1'].map({True: 'Yes', False: 'No'})
    disp['S2'] = disp['S2'].map({True: 'Yes', False: 'No'})
    st.dataframe(disp, use_container_width=True, hide_index=True)
    st.divider()

    st.subheader("Participant Frequency")
    freq = df.groupby('name').agg({'date': 'count', 'session_1': 'sum', 'session_2': 'sum'}).reset_index()
    freq.columns = ['Name', 'Days', 'Session1', 'Session2']
    freq = freq.sort_values('Days', ascending=False)
    st.dataframe(freq, use_container_width=True, hide_index=True)
    st.divider()
    st.subheader("Export")
    prefix = st.text_input("Filename", value=f"attendance_{start.strftime('%Y%m%d')}_{end.strftime('%Y%m%d')}")
    
    if st.button("Export Summary"):
        summary = pd.DataFrame({'Period': [f"{start.strftime('%d %b %Y')} to {end.strftime('%d %b %Y')}"], 'Total': [total], 'Unique': [unique], 'S1': [s1], 'S2': [s2]})
        csv = summary.to_csv(index=False).encode('utf-8')
        st.download_button("Download Summary CSV", csv, f"{prefix}_summary.csv", "text/csv")

    # 🔥 FIX: This MUST be inside the show_reports() function, NOT at the top level of the file
    if st.session_state.get('user_role') == 'admin':
        if st.button("Export Full Data (Includes PII)"):
            csv = disp.to_csv(index=False).encode('utf-8')
            st.download_button("Download Full CSV", csv, f"{prefix}_detailed.csv", "text/csv")
    else:
        st.info("🔒 Full data export is restricted to Admins for PDPA compliance.")
