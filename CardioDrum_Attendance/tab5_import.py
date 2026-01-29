import streamlit as st
import re
import difflib
from datetime import datetime, timezone
from config import supabase, DB_CONNECTED, refresh_data

def show_tab5(selected_date):
    st.header("📥 Import from WhatsApp Poll")
    
    st.info(f"Date: **{selected_date}** | Participants: **{len(st.session_state.participants)}**")
    
    # Test DB
    if st.button("🧪 Test DB Connection"):
        try:
            test = supabase.table('attendance').select("count", count="exact").execute()
            st.success(f"✅ DB Connected! Total records: {test.count}")
        except Exception as e:
            st.error(f"❌ DB Error: {e}")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Session 1")
        s1_text = st.text_area("Names (one per line)", height=150, key="s1", placeholder="abdul\njohn\ntan...")
    with col2:
        st.subheader("Session 2")  
        s2_text = st.text_area("Names (one per line)", height=150, key="s2", placeholder="abdul\nmary...")
    
    if st.button("🔍 Analyze & Match", type="primary", use_container_width=True):
        if not s1_text.strip() and not s2_text.strip():
            st.warning("Please paste at least one name")
        else:
            with st.spinner("Matching..."):
                results = match_names(s1_text, s2_text, st.session_state.participants)
                st.session_state.import_results = results
                st.session_state.show_debug = True
                st.rerun()
    
    # Show results
    if 'import_results' in st.session_state and st.session_state.import_results:
        display_results(selected_date)
    elif 'import_results' in st.session_state and not st.session_state.import_results:
        st.error("❌ No matches found. Check debug info below.")
        if st.session_state.get('show_debug'):
            show_debug_info(s1_text, s2_text, st.session_state.participants)

def match_names(s1_text, s2_text, participants):
    """Match names with fuzzy logic"""
    s1_names = [n.strip() for n in s1_text.split('\n') if n.strip()]
    s2_names = [n.strip() for n in s2_text.split('\n') if n.strip()]
    
    results = []
    
    def find_match(name):
        name_clean = name.lower().strip()
        best_score = 0
        best_match = None
        
        for p in participants:
            db_name = p.get('name', '').lower()
            if not db_name:
                continue
            
            # Try substring match first (e.g., "abdul" in "abdul jalil")
            if name_clean in db_name:
                return p, 0.95
            
            if db_name in name_clean:
                return p, 0.95
            
            # Fuzzy match
            score = difflib.SequenceMatcher(None, name_clean, db_name).ratio()
            
            # Word overlap bonus
            name_words = set(name_clean.split())
            db_words = set(db_name.split())
            if name_words and db_words:
                overlap = len(name_words & db_words) / max(len(name_words), len(db_words))
                score = max(score, overlap)
            
            if score > best_score and score >= 0.5:
                best_score = score
                best_match = p
        
        return best_match, best_score
    
    # Process Session 1
    for name in s1_names:
        match, score = find_match(name)
        if match:
            already_in = [r for r in results if r['id'] == match['id']]
            if not already_in:
                results.append({
                    'whatsapp': name,
                    'match': match['name'],
                    'id': match['id'],
                    's1': True,
                    's2': name in s2_names,
                    'score': score,
                    'confirmed': score >= 0.6
                })
    
    # Process Session 2
    for name in s2_names:
        match, score = find_match(name)
        if match:
            already_in = [r for r in results if r['id'] == match['id']]
            if not already_in:
                results.append({
                    'whatsapp': name,
                    'match': match['name'],
                    'id': match['id'],
                    's1': False,
                    's2': True,
                    'score': score,
                    'confirmed': score >= 0.6
                })
    
    return results

def display_results(selected_date):
    results = st.session_state.import_results
    
    st.divider()
    st.success(f"🎯 Found {len(results)} matches!")
    
    # Summary stats
    cols = st.columns(3)
    high = sum(1 for r in results if r['score'] >= 0.8)
    med = sum(1 for r in results if 0.6 <= r['score'] < 0.8)
    low = sum(1 for r in results if r['score'] < 0.6)
    cols[0].metric("High Match", high)
    cols[1].metric("Medium", med)
    cols[2].metric("Low", low)
    
    # Show matches
    for idx, r in enumerate(results):
        cols = st.columns([2, 2, 2, 1])
        
        score_emoji = "🟢" if r['score'] >= 0.8 else "🟠" if r['score'] >= 0.6 else "🔴"
        
        with cols[0]:
            st.write(f"{score_emoji} **{r['whatsapp']}**")
        with cols[1]:
            st.write(f"→ {r['match']}")
        with cols[2]:
            sessions = []
            if r['s1']: sessions.append("S1")
            if r['s2']: sessions.append("S2")
            st.write(f"{' + '.join(sessions)}")
        with cols[3]:
            r['confirmed'] = st.checkbox("Import", key=f"import_{idx}_{r['id']}", value=r['confirmed'])
    
    # Import button
    confirmed = [r for r in results if r.get('confirmed')]
    
    if confirmed:
        st.divider()
        st.write(f"**{len(confirmed)} selected for import**")
        
        if st.button(f"✅ IMPORT TO DATABASE", type="primary", use_container_width=True):
            do_import(confirmed, selected_date)

def do_import(confirmed_list, selected_date):
    st.divider()
    st.subheader("Importing...")
    
    success = 0
    skipped = 0
    errors = []
    
    progress = st.progress(0)
    
    for idx, item in enumerate(confirmed_list):
        pid = str(item['id'])
        name = item['match']
        
        progress.progress((idx + 1) / len(confirmed_list), f"Importing {name}...")
        
        try:
            # Check duplicate
            existing = supabase.table('attendance')\
                .select('id')\
                .eq('participant_id', pid)\
                .eq('date', str(selected_date))\
                .execute()
            
            if existing.data:
                st.write(f"⏭️ {name} - already exists")
                skipped += 1
                continue
            
            # Insert
            data = {
                "participant_id": pid,
                "name": str(name),
                "date": str(selected_date),
                "session_1": bool(item['s1']),
                "session_2": bool(item['s2']),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            result = supabase.table('attendance').insert(data).execute()
            
            if result.data:
                st.write(f"✅ {name}")
                success += 1
            else:
                errors.append(f"{name}: No data returned")
                
        except Exception as e:
            st.error(f"❌ {name}: {str(e)}")
            errors.append(f"{name}: {str(e)}")
    
    progress.empty()
    
    st.divider()
    st.success(f"🎉 Done! Imported: {success}, Skipped: {skipped}")
    
    if errors:
        for err in errors:
            st.error(err)
    
    # Verify
    verify = supabase.table('attendance')\
        .select('count', count="exact")\
        .eq('date', str(selected_date))\
        .execute()
    
    st.info(f"📊 Total records in DB for {selected_date}: {verify.count}")
    
    # Clear
    refresh_data()
    del st.session_state.import_results
    
    st.balloons()

def show_debug_info(s1_text, s2_text, participants):
    """Show what's happening when matches fail"""
    st.divider()
    st.subheader("Debug Info")
    
    s1_names = [n.strip() for n in s1_text.split('\n') if n.strip()]
    s2_names = [n.strip() for n in s2_text.split('\n') if n.strip()]
    
    st.write("**WhatsApp names entered:**")
    st.write(f"S1: {s1_names}")
    st.write(f"S2: {s2_names}")
    
    st.write("**Available participants in database:**")
    db_names = [p.get('name', 'NO NAME') for p in participants[:10]]
    st.write(db_names)
    
    st.write("**Trying to match 'abdul':**")
    for p in participants:
        db_name = p.get('name', '').lower()
        if 'abdul' in db_name:
            st.write(f"✓ Found: {p['name']} (ID: {p['id']})")