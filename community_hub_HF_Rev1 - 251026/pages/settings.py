import streamlit as st
from datetime import datetime, timedelta
from config import supabase, DB_CONNECTED, load_activities
from utils import clean_phone_number

# ─── HELPER FUNCTIONS FOR PERSISTENCE ─────────────────────
def get_setting(key, default="Never"):
    """Fetch setting from database. Remembers it after restart."""
    if not DB_CONNECTED: return default
    try:
        r = supabase.table('system_settings').select('setting_value').eq('setting_key', key).single().execute()
        return r.data['setting_value'] if r.data else default
    except:
        return default

def save_setting(key, value):
    """Save setting to database. Survives system restarts."""
    if not DB_CONNECTED: return False
    try:
        #  FIX: Added on_conflict='setting_key' to handle updates correctly
        supabase.table('system_settings').upsert({
            'setting_key': key, 
            'setting_value': value, 
            'updated_at': datetime.now().isoformat()
        }, on_conflict='setting_key').execute()
        return True
    except Exception as e:
        st.error(f"Error saving setting: {e}")
        return False

def show_settings():
    st.header("⚙️ System Settings & Data Cleanup")
    st.caption("Manage data retention. Settings are saved to the database and survive system restarts.")
    
    if not DB_CONNECTED:
        st.error("Database not connected")
        return

    st.divider()

    # ══════════════════════════════════════════════════════
    # PART 1: PERSISTENT DATA RETENTION POLICIES
    # ══════════════════════════════════════════════════════
    st.subheader("📅 Data Retention Policies")
    st.info("💡 These settings are saved. When you restart the system, it will remember these choices.")
    
    # Load current saved settings (Default to "Never" if no setting exists)
    current_token = get_setting('token_retention', 'Never')
    current_session = get_setting('session_retention', 'Never')
    current_attendance = get_setting('attendance_retention', 'Never')
    
    options = ["Never", "7 days", "14 days", "30 days", "60 days", "90 days", "1 year"]
    
    c1, c2, c3 = st.columns(3)
    with c1:
        token_ret = st.selectbox("🔗 Volunteer Links", options, index=options.index(current_token) if current_token in options else 0, key="set_token")
    with c2:
        sess_ret = st.selectbox("📅 Sessions & RSVPs", options, index=options.index(current_session) if current_session in options else 0, key="set_sess")
    with c3:
        att_ret = st.selectbox("📊 Attendance Records", options, index=options.index(current_attendance) if current_attendance in options else 0, key="set_att")
        
    # Save Button
    if st.button("💾 Save Retention Policies", type="primary", use_container_width=True):
        if save_setting('token_retention', token_ret):
            st.success("✅ Token retention saved!")
        if save_setting('session_retention', sess_ret):
            st.success("✅ Session retention saved!")
        if save_setting('attendance_retention', att_ret):
            st.success("✅ Attendance retention saved!")
        st.rerun()

    st.divider()

    # Quick Cleanup Buttons
    st.subheader("⚡ Quick Cleanup Actions")
    st.caption("Run cleanup immediately based on the policies saved above.")
    
    # ─── Helper to safely parse days ───
    def get_days_from_setting(setting_val):
        if setting_val == "Never" or setting_val == "1 year":
            return 0
        try:
            return int(setting_val.split()[0])
        except:
            return 0

    qc1, qc2, qc3 = st.columns(3)
    with qc1:
        days_token = get_days_from_setting(token_ret)
        if st.button(f"🗑️ Clean Links ({token_ret})", use_container_width=True, disabled=(token_ret == "Never")):
            cutoff = (datetime.now() - timedelta(days=days_token)).isoformat()
            supabase.table('volunteer_tokens').delete().lte('expires_at', cutoff).execute()
            st.success(f"Cleaned links older than {token_ret}!"); st.rerun()
            
    with qc2:
        days_sess = get_days_from_setting(sess_ret)
        if st.button(f"🗑️ Clean Sessions ({sess_ret})", use_container_width=True, disabled=(sess_ret == "Never")):
            cutoff = (datetime.now() - timedelta(days=days_sess)).strftime('%Y-%m-%d')
            supabase.table('sessions').delete().lte('session_date', cutoff).execute()
            st.success(f"Cleaned sessions older than {sess_ret}!"); st.rerun()
            
    with qc3:
        days_att = get_days_from_setting(att_ret)
        if st.button(f"🗑️ Clean Attendance ({att_ret})", use_container_width=True, disabled=(att_ret == "Never")):
            if st.checkbox("Confirm delete attendance", key="qc_att_confirm"):
                cutoff = (datetime.now() - timedelta(days=days_att)).strftime('%Y-%m-%d')
                supabase.table('attendance').delete().lte('date', cutoff).execute()
                st.success(f"Cleaned attendance older than {att_ret}!"); st.rerun()

    st.divider()

    # ═══════════════════════════════════════════════════════
    # PART 2: INDIVIDUAL ATTENDANCE MANAGEMENT
    # ═══════════════════════════════════════════════════════
    st.subheader("👤 Individual Attendance Management")
    st.caption("Edit or delete specific attendance records for participants.")
    
    # Search for participant
    search_p = st.text_input("🔍 Search Participant", placeholder="Type name or ID...", key="ind_att_search")
    
    if search_p:
        participants = st.session_state.get('participants', []) or []
        s = search_p.lower()
        
        # Filter participants safely
        matches = []
        for p in participants:
            try:
                if p and isinstance(p, dict) and p.get('active', True):
                    name = str(p.get('name', '')).lower()
                    pid = str(p.get('id', '')).lower()
                    if s in name or s in pid:
                        matches.append(p)
            except:
                continue
        
        if matches:
            # Create display labels safely
            display_labels = []
            for p in matches:
                try:
                    p_id = str(p.get('id', 'N/A'))
                    p_name = str(p.get('name', 'Unknown'))
                    display_labels.append(f"{p_name} (ID: {p_id[:8]}...)")
                except:
                    display_labels.append("Unknown Participant")
            
            selected_label = st.selectbox("Select Resident", display_labels, key="ind_att_select_p")
            
            # Find the selected participant safely
            try:
                selected_index = display_labels.index(selected_label)
                selected_p = matches[selected_index]
                selected_p_id = str(selected_p.get('id', ''))
                selected_p_name = str(selected_p.get('name', 'Unknown'))
            except:
                st.error("Error selecting participant. Please try again.")
                st.stop()
            
            # Fetch attendance records for this participant
            try:
                att_records = supabase.table('attendance').select("*").eq('participant_id', selected_p_id).order('date', desc=True).limit(50).execute().data
                
                if att_records and len(att_records) > 0:
                    st.write(f"**Found {len(att_records)} attendance record(s) for {selected_p_name}:**")
                    
                    # Display each record
                    for i, rec in enumerate(att_records):
                        try:
                            # Safely extract record data
                            rec_id = rec.get('id', '')
                            rec_date = rec.get('date', 'N/A')
                            rec_source = rec.get('source', 'N/A')
                            rec_session_1 = rec.get('session_1', False)
                            rec_session_2 = rec.get('session_2', False)
                            rec_timestamp = rec.get('timestamp', '')
                            
                            # Determine session display
                            if rec_session_1 and rec_session_2:
                                session_display = "Both"
                            elif rec_session_1:
                                session_display = "S1"
                            elif rec_session_2:
                                session_display = "S2"
                            else:
                                session_display = "None"
                            
                            with st.expander(f"📅 {rec_date} - {rec_source} | Sessions: {session_display}"):
                                c1, c2, c3 = st.columns(3)
                                
                                # Edit Date
                                with c1:
                                    try:
                                        current_date = datetime.strptime(str(rec_date), '%Y-%m-%d').date()
                                    except:
                                        current_date = datetime.now().date()
                                    
                                    new_date = st.date_input("New Date", value=current_date, key=f"edit_date_{rec_id}")
                                    if st.button("💾 Update Date", key=f"btn_update_{rec_id}", use_container_width=True):
                                        try:
                                            supabase.table('attendance').update({
                                                'date': new_date.strftime('%Y-%m-%d'),
                                                'updated_at': datetime.now().isoformat()
                                            }).eq('id', rec_id).execute()
                                            st.success("✅ Date updated!")
                                            st.rerun()
                                        except Exception as e:
                                            st.error(f"Error updating: {e}")
                                
                                # Delete Record
                                with c2:
                                    if st.button("🗑️ Delete Record", key=f"btn_del_{rec_id}", use_container_width=True, type="secondary"):
                                        try:
                                            supabase.table('attendance').delete().eq('id', rec_id).execute()
                                            st.success("✅ Record deleted!")
                                            st.rerun()
                                        except Exception as e:
                                            st.error(f"Error deleting: {e}")
                                
                                # Show Details
                                with c3:
                                    try:
                                        ts_display = str(rec_timestamp)[:10] if rec_timestamp else 'N/A'
                                    except:
                                        ts_display = 'N/A'
                                    
                                    st.caption(f"ID: {str(rec_id)[:8]}...\nSource: {rec_source}\nTimestamp: {ts_display}")
                                    
                        except Exception as e:
                            st.error(f"Error displaying record {i+1}: {e}")
                            continue
                else:
                    st.info("ℹ️ No attendance records found for this participant.")
                    
            except Exception as e:
                st.error(f"Error fetching attendance: {e}")
        else:
            st.info("ℹ️ No participants found matching your search.")

    st.divider()

    # ══════════════════════════════════════════════════════
    # PART 3: ADVANCED UNIFIED CLEANUP
    # ═══════════════════════════════════════════════════════
    st.subheader("🔍 Advanced Unified Cleanup")
    st.caption("Precise control: Filter by date range, activity, session, or specific participant.")
    
    # 1. Select Mode
    cleanup_mode = st.radio("Select Data to Clean:", 
        ["📊 Attendance Records", "📅 Session RSVPs", "🔗 Volunteer Tokens"], 
        horizontal=True, key="adv_mode")
    
    st.markdown("---")
    
    # 2. Filters
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("From Date", value=None, key="adv_start")
    with col2:
        end_date = st.date_input("To Date", value=None, key="adv_end")
        
    acts = load_activities()
    act_names = ["All Activities"] + [a['name'] for a in acts]
    selected_act = st.selectbox("Activity Filter", act_names, key="adv_act")
    
    # Participant Search (Only for Attendance)
    participant_id = None
    if cleanup_mode == "📊 Attendance Records":
        p_search = st.text_input("👤 Participant (Optional - leave blank for all)", placeholder="Search name or ID...", key="adv_p_search")
        if p_search:
            participants = st.session_state.get('participants', []) or []
            s = p_search.lower()
            matches = [p for p in participants if p and isinstance(p, dict) and p.get('active', True) and (s in p.get('name', '').lower() or s in str(p.get('id', '')).lower())]
            if matches:
                selected_p = st.selectbox("Select Resident", [f"{p['name']} (ID: {p['id'][:8]}...)" for p in matches], key="adv_p_select")
                participant_id = matches[[f"{p['name']} (ID: {p['id'][:8]}...)" for p in matches].index(selected_p)]['id']

    st.markdown("---")
    
    # 3. Preview Logic
    preview_clicked = st.button("🔍 Preview Records to Delete", use_container_width=True)
    
    if preview_clicked:
        if not start_date or not end_date:
            st.error("Please select both a Start Date and End Date.")
            st.stop()
        if start_date > end_date:
            st.error("Start date cannot be after end date.")
            st.stop()
            
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')
        
        st.session_state['adv_preview_data'] = None
        
        try:
            if cleanup_mode == "📊 Attendance Records":
                query = supabase.table('attendance').select('*', count='exact')
                query = query.gte('date', start_str).lte('date', end_str)
                if selected_act != "All Activities": query = query.eq('source', selected_act)
                if participant_id: query = query.eq('participant_id', participant_id)
                res = query.execute()
                st.session_state['adv_preview_data'] = res.data
                st.session_state['adv_preview_table'] = 'attendance'
                
            elif cleanup_mode == "📅 Session RSVPs":
                query = supabase.table('session_rsvp').select('*', count='exact')
                query = query.gte('created_at', f"{start_str}T00:00:00").lte('created_at', f"{end_str}T23:59:59")
                res = query.execute()
                st.session_state['adv_preview_data'] = res.data
                st.session_state['adv_preview_table'] = 'session_rsvp'
                
            elif cleanup_mode == "🔗 Volunteer Tokens":
                query = supabase.table('volunteer_tokens').select('*', count='exact')
                query = query.gte('created_at', f"{start_str}T00:00:00").lte('created_at', f"{end_str}T23:59:59")
                res = query.execute()
                st.session_state['adv_preview_data'] = res.data
                st.session_state['adv_preview_table'] = 'volunteer_tokens'
                
        except Exception as e:
            st.error(f"Error fetching preview: {e}")

    # 4. Show Preview & Delete
    if st.session_state.get('adv_preview_data') is not None:
        data = st.session_state['adv_preview_data']
        count = len(data)
        table = st.session_state['adv_preview_table']
        
        st.warning(f"️ Found **{count}** records matching your criteria.")
        
        if count > 0:
            with st.expander("👁️ View Sample Data (First 5 records)"):
                st.write(data[:5])
                
            st.markdown("---")
            confirm = st.checkbox("I understand this will permanently delete these records.", key="adv_confirm")
            
            if confirm and st.button(f"🗑️ DELETE {count} RECORDS NOW", type="primary", use_container_width=True):
                with st.spinner("Deleting..."):
                    try:
                        if table == 'attendance':
                            ids = [d['id'] for d in data]
                            supabase.table('attendance').delete().in_('id', ids).execute()
                        elif table == 'session_rsvp':
                            ids = [d['id'] for d in data]
                            supabase.table('session_rsvp').delete().in_('id', ids).execute()
                        elif table == 'volunteer_tokens':
                            tokens = [d['token'] for d in data]
                            supabase.table('volunteer_tokens').delete().in_('token', tokens).execute()
                            
                        st.success(f"✅ Successfully deleted {count} records!")
                        st.session_state['adv_preview_data'] = None
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error deleting: {e}")
        else:
            st.info("No records found. Nothing to delete.")