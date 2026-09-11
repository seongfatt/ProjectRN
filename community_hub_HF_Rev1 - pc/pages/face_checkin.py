# pages/face_checkin.py
"""Group Photo Check-In using Face Recognition"""

import streamlit as st
import pandas as pd
from datetime import datetime
from PIL import Image
import io
import numpy as np
from config import supabase, DB_CONNECTED, load_activities, now_sgt
from services.face_service import get_face_service
from utils import sync_session_attendance_async
from services.attendance_service import AttendanceService

# 🔥 SAFE IMPORT: cv2 is optional — app works without it
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    cv2 = None


def show_face_checkin():
    st.header("📸 Group Photo Check-In")
    st.caption("Take a group photo and automatically check in all recognized residents")

    if not DB_CONNECTED:
        st.error("Database not connected")
        return

    # Initialize face service
    face_service = get_face_service()
    # 🔥 ADD THESE TWO DEBUG LINES RIGHT HERE 🔥
    st.info(f"🔍 Debug: Faces loaded in memory: {face_service.get_enrolled_count()}")
    # 🔥 END OF DEBUG LINES 🔥

    # Check if face recognition is available
    if not face_service.is_available():
        st.error("⚠️ Face recognition is not available on this server.")
        st.info("Please contact the administrator to install: opencv-python-headless, dlib-bin, and face-recognition.")
        st.markdown("""
        <div style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; border-radius: 8px; color: #1a1a1a;">
            <strong>💡 To enable face recognition:</strong><br>
            Add these to requirements.txt:<br>
            <code>opencv-python-headless==4.8.1.78</code><br>
            <code>dlib-bin==19.24.2</code><br>
            <code>face-recognition==1.3.0</code>
        </div>
        """, unsafe_allow_html=True)
        return

    enrolled_count = face_service.get_enrolled_count()

    # ── Status Banner ──
    if enrolled_count == 0:
        st.warning("⚠️ No faces enrolled yet. Please enroll residents first in the Residents tab.")
        st.info("Go to **Residents → Edit Resident → Enroll Face Photo**")
        return

    col1, col2 = st.columns(2)
    with col1:
        st.success(f"✅ **{enrolled_count}** residents enrolled for face recognition")
    with col2:
        st.info("📷 **Tip:** Best results with good lighting and forward-facing faces")

    st.divider()

    # ── Activity & Session Selection ──
    st.subheader("📅 Step 1: Select Activity & Session")

    acts = load_activities()
    act_names = [a["name"] for a in acts] if acts else ["Cardio Drumming"]
    activity = st.selectbox("Select Activity", act_names, key="face_activity")

    act_config = next((a for a in acts if a["name"] == activity), None)

    session_labels = []
    if act_config:
        for i in range(1, 5):
            lbl = (act_config.get(f"session_{i}_label") or "").strip()
            if lbl:
                session_labels.append(lbl)
    if not session_labels:
        session_labels = ["Session 1"]

    if len(session_labels) == 1:
        st.info(f"ℹ️ This activity has only one session: {session_labels[0]}")
        s1, s2, s3, s4 = True, False, False, False
        session_display = session_labels[0]
    else:
        session_options = ["All Sessions"] + session_labels
        session_choice = st.radio("Which session(s)?", session_options, horizontal=True, key="face_session")
        flags = [(session_choice == "All Sessions") or (session_choice == lbl) for lbl in session_labels]
        flags = (flags + [False, False, False, False])[:4]
        s1, s2, s3, s4 = flags
        session_display = session_choice

    selected_date = st.date_input("Date", value=datetime.now().date(), key="face_date")
    formatted_date = selected_date.strftime("%Y-%m-%d")

    st.divider()

    # ── Photo Upload ──
    st.subheader("📷 Step 2: Upload or Take Photo")

    uploaded_file = st.file_uploader(
        "Choose a group photo or take a photo with your camera",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=False,
        key="face_upload"
    )

    camera_photo = st.camera_input("📸 Or take a photo now", key="face_camera")

    image_bytes = None
    image_display = None

    if camera_photo:
        image_bytes = camera_photo.getvalue()
        image_display = Image.open(io.BytesIO(image_bytes))
    elif uploaded_file:
        image_bytes = uploaded_file.getvalue()
        image_display = Image.open(io.BytesIO(image_bytes))

    if image_display:
        st.image(image_display, caption="📷 Uploaded Photo", width='stretch')

    st.divider()

    # ── Process Photo ──
    if image_bytes and st.button("🔍 Detect & Check In Residents", type="primary", width='stretch'):
        with st.spinner("🔍 Analyzing photo and matching faces..."):
            # Detect faces
            face_locations, face_encodings, rgb_img = face_service.detect_faces(image_bytes)

            if not face_encodings:
                st.error("❌ No faces detected in the photo. Please try again with a clearer image.")
                st.stop()

            st.success(f"✅ Found {len(face_encodings)} face(s) in the photo")

            # Identify faces
            matches = face_service.identify_faces(face_encodings)

            # ── Display Results ──
            st.subheader("📋 Recognition Results")

            # Draw bounding boxes on image
            if rgb_img is not None and CV2_AVAILABLE and cv2 is not None:
                img_with_boxes = rgb_img.copy()
                results = []
                recognized_count = 0

                for i, (location, match) in enumerate(zip(face_locations, matches)):
                    top, right, bottom, left = location

                    if match:
                        color = (0, 255, 0)  # Green
                        # ✅ FIXED: Use single quotes inside f-string
                        label = f"{match['name']} ({match['confidence']:.0%})"
                        recognized_count += 1
                        results.append({
                            "status": "✅ Recognized",
                            "name": match["name"],
                            "confidence": f"{match['confidence']:.0%}"
                        })
                    else:
                        color = (0, 0, 255)  # Red
                        label = "Unknown"
                        results.append({
                            "status": "❌ Unknown",
                            "name": "Not recognized",
                            "confidence": "-"
                        })

                    # Draw rectangle and label
                    cv2.rectangle(img_with_boxes, (left, top), (right, bottom), color, 2)
                    cv2.rectangle(img_with_boxes, (left, bottom - 25), (right, bottom), color, -1)
                    cv2.putText(img_with_boxes, label, (left + 6, bottom - 6),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

                # Display annotated image
                st.image(img_with_boxes, caption="📸 Annotated Photo (Green = Recognized, Red = Unknown)", width='stretch')

            else:
                # Fallback: show results without bounding boxes
                results = []
                recognized_count = 0
                for match in matches:
                    if match:
                        recognized_count += 1
                        # ✅ FIXED: Use single quotes inside f-string
                        results.append({
                            "status": "✅ Recognized",
                            "name": match["name"],
                            "confidence": f"{match['confidence']:.0%}"
                        })
                    else:
                        results.append({
                            "status": "❌ Unknown",
                            "name": "Not recognized",
                            "confidence": "-"
                        })

            # ── Results Table ──
            if results:
                df = pd.DataFrame(results)
                st.dataframe(df, use_container_width=True, hide_index=True)

            # ── Batch Check-In ──
            if recognized_count > 0:
                st.success(f"✅ **{recognized_count}** resident(s) recognized!")

                if st.button("✅ Check In All Recognized Residents", type="primary", width='stretch'):
                    with st.spinner("Processing check-ins..."):
                        checked_in_count = 0
                        errors = []

                        for match in matches:
                            if match is not None:
                                try:
                                    # 🚀 Use your unified AttendanceService instead of manual Supabase calls!
                                    success, message, resident = AttendanceService.process_checkin(
                                        pid=match["id"],
                                        date=formatted_date,
                                        activity=activity,
                                        s1=s1, s2=s2, s3=s3, s4=s4
                                    )
                                    
                                    if success:
                                        checked_in_count += 1
                                    else:
                                        # This gracefully handles "already checked in" messages
                                        errors.append(f"{match['name']}: {message}")
                                        
                                except Exception as e:
                                    st.error(f"❌ DEBUG ERROR: {e}")   # <-- ADD THIS LINE
                                    errors.append(f"{match['name']}: {e}")

                        if checked_in_count > 0:
                            st.success(f"✅ Successfully checked in {checked_in_count} resident(s)!")
                            st.balloons()
                        
                        if errors:
                            st.warning("⚠️ Some residents could not be checked in:")
                            for err in errors:
                                st.caption(f"• {err}")

                        st.success(f"✅ Successfully checked in {checked_in_count} residents!")
                        
                        # 🔥 Keep the message visible for 3 seconds before refreshing
                        import time
                        time.sleep(3)
                        st.rerun()
            else:
                st.warning("⚠️ No faces were recognized. Please ensure residents are enrolled.")

    st.divider()

    # ── Today's Statistics ──
    st.subheader("📊 Today's Face Recognition Statistics")

    try:
        today_str = selected_date.strftime("%Y-%m-%d")

        # Count face check-ins today
        face_checkins = supabase.table("attendance") \
            .select("*", count="exact") \
            .eq("date", today_str) \
            .eq("checkin_method", "face_recognition") \
            .execute()

        total_face_checkins = face_checkins.count if face_checkins else 0

        # Count total check-ins today for this activity
        total_checkins = supabase.table("attendance") \
            .select("*", count="exact") \
            .eq("date", today_str) \
            .eq("source", activity) \
            .execute()

        total_checkins_count = total_checkins.count if total_checkins else 0

        col1, col2, col3 = st.columns(3)
        col1.metric("👤 Face Check-Ins Today", total_face_checkins)
        col2.metric("📋 Total Check-Ins Today", total_checkins_count)
        col3.metric("📸 Enrolled Faces", enrolled_count)

    except Exception as e:
        st.info("No statistics available yet.")

    st.caption("💡 **Tip:** For best results, use well-lit photos with faces looking forward.")