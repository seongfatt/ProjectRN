import streamlit as st
import difflib
from datetime import datetime, timezone
from config import supabase, DB_CONNECTED, refresh_data, load_activities

def show_import(selected_date):
    st.header("📥 Import from WhatsApp Poll")

    acts = load_activities()
    act_names = [a['name'] for a in acts]
    activity = st.selectbox("🎯 Activity", act_names, index=0)

    st.info(f"Date: **{selected_date}** | Participants: **{len(st.session_state.participants)}**")

    if st.button("🧪 Test DB"):
        try:
            t = supabase.table('attendance').select("count", count="exact").execute()
            st.success(f"✅ DB OK! Total: {t.count}")
        except Exception as e: st.error(f"❌ {e}")

    c1, c2 = st.columns(2)
    with c1: s1_text = st.text_area("Session 1 Names", height=150, key="s1_imp", placeholder="abdul\njohn\ntan...")
    with c2: s2_text = st.text_area("Session 2 Names", height=150, key="s2_imp", placeholder="abdul\nmary...")

    if st.button("🔍 Analyze & Match", type="primary", use_container_width=True):
        if not s1_text.strip() and not s2_text.strip():
            st.warning("Please paste names")
        else:
            results = match_names(s1_text, s2_text, st.session_state.participants)
            st.session_state.import_results = results
            st.rerun()

    if 'import_results' in st.session_state and st.session_state.import_results:
        display_results(selected_date, activity)

def match_names(s1_text, s2_text, participants):
    s1_names = [n.strip() for n in s1_text.split('\n') if n.strip()]
    s2_names = [n.strip() for n in s2_text.split('\n') if n.strip()]
    results = []

    def find_match(name):
        name_clean = name.lower().strip()
        best_score, best_match = 0, None
        for p in participants:
            db_name = p.get('name', '').lower()
            if not db_name: continue
            if name_clean in db_name or db_name in name_clean: return p, 0.95
            score = difflib.SequenceMatcher(None, name_clean, db_name).ratio()
            nw, dw = set(name_clean.split()), set(db_name.split())
            if nw and dw:
                overlap = len(nw & dw) / max(len(nw), len(dw))
                score = max(score, overlap)
            if score > best_score and score >= 0.5:
                best_score, best_match = score, p
        return best_match, best_score

    for name in s1_names:
        m, s = find_match(name)
        if m and not any(r['id'] == m['id'] for r in results):
            results.append({'whatsapp': name, 'match': m['name'], 'id': m['id'], 's1': True, 's2': name in s2_names, 'score': s, 'confirmed': s >= 0.6})
    for name in s2_names:
        m, s = find_match(name)
        if m and not any(r['id'] == m['id'] for r in results):
            results.append({'whatsapp': name, 'match': m['name'], 'id': m['id'], 's1': False, 's2': True, 'score': s, 'confirmed': s >= 0.6})
    return results

def display_results(selected_date, activity):
    results = st.session_state.import_results
    st.divider(); st.success(f"🎯 {len(results)} matches!")

    c1, c2, c3 = st.columns(3)
    c1.metric("High", sum(1 for r in results if r['score'] >= 0.8))
    c2.metric("Med", sum(1 for r in results if 0.6 <= r['score'] < 0.8))
    c3.metric("Low", sum(1 for r in results if r['score'] < 0.6))

    for idx, r in enumerate(results):
        c1, c2, c3, c4 = st.columns([2, 2, 2, 1])
        emoji = "🟢" if r['score'] >= 0.8 else "🟠" if r['score'] >= 0.6 else "🔴"
        c1.write(f"{emoji} **{r['whatsapp']}**")
        c2.write(f"→ {r['match']}")
        sessions = []
        if r['s1']: sessions.append("S1")
        if r['s2']: sessions.append("S2")
        c3.write(f"{' + '.join(sessions)}")
        r['confirmed'] = c4.checkbox("Import", key=f"imp_{idx}_{r['id']}", value=r['confirmed'])

    confirmed = [r for r in results if r.get('confirmed')]
    if confirmed:
        st.write(f"**{len(confirmed)} selected**")
        if st.button(f"✅ IMPORT TO DB", type="primary", use_container_width=True):
            do_import(confirmed, selected_date, activity)

def do_import(confirmed_list, selected_date, activity):
    st.divider(); st.subheader("Importing...")
    success, skipped = 0, 0
    prog = st.progress(0)
    for idx, item in enumerate(confirmed_list):
        pid, name = str(item['id']), item['match']
        prog.progress((idx + 1) / len(confirmed_list), f"Importing {name}...")
        try:
            existing = supabase.table('attendance').select('id').eq('participant_id', pid).eq('date', str(selected_date)).eq('source', activity).execute()
            if existing.data:
                st.write(f"⏭️ {name} - exists"); skipped += 1; continue
            supabase.table('attendance').insert({
                "participant_id": pid, "name": name, "date": str(selected_date),
                "session_1": bool(item['s1']), "session_2": bool(item['s2']),
                "timestamp": datetime.now(timezone.utc).isoformat(), "source": activity
            }).execute()
            st.write(f"✅ {name}"); success += 1
        except Exception as e:
            st.error(f"❌ {name}: {e}")
    prog.empty()
    st.success(f"🎉 Done! Imported: {success}, Skipped: {skipped}")
    verify = supabase.table('attendance').select('count', count="exact").eq('date', str(selected_date)).eq('source', activity).execute()
    st.info(f"📊 Total for {selected_date}: {verify.count}")
    refresh_data()
    del st.session_state.import_results
    st.balloons()
