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

# 🔥 SAFE IMPORT: cv2 is optional
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

    # Check if face recognition is available
    if not face_service.is_available():
        st.error("⚠️ Face recognition is not available on this server.")
        st.info("Please contact the administrator to install: deepface, opencv-python-headless, and tensorflow.")
        return

    enrolled_count = face_service.get_enrolled_count()

    if enrolled_count == 0:
        st.warning("⚠️ No faces enrolled yet. Please enroll residents first.")
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
    else:
        session_options = ["All Sessions"] + session_labels
        session_choice = st.radio("Which session(s)?", session_options, horizontal=True, key="face_session")
        flags = [(session_choice == "All Sessions") or (session_choice == lbl) for lbl in session_labels]
        flags = (flags + [False, False, False, False])[:4]
        s1, s2, s3, s4 = flags

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
    if image_bytes and st.button("🔍 Detect & Check In Residents", type="primary", use_container_width=True):
        with st.spinner("🔍 Analyzing photo and matching faces... (This may take 10-15 seconds)"):
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

                st.image(img_with_boxes, caption="📸 Annotated Photo (Green = Recognized, Red = Unknown)", width='stretch')
            else:
                # Fallback
                results = []
                recognized_count = 0
                for match in matches:
                    if match:
                        recognized_count += 1
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

                if st.button("✅ Check In All Recognized Residents", type="primary", use_container_width=True):
                    with st.spinner("Processing check-ins..."):
                        checked_in_count = 0
                        errors = []

                        for match in matches:
                            if match is not None:
                                try:
                                    # Check if already checked in today
                                    existing = supabase.table("attendance") \
                                        .select("id, session_1, session_2, session_3, session_4") \
                                        .eq("participant_id", match["id"]) \
                                        .eq("date", formatted_date) \
                                        .eq("source", activity) \
                                        .execute()

                                    if existing.data:
                                        # Update existing record
                                        record = existing.data[0]
                                        updates = {
                                            "session_1": record.get("session_1", False) or s1,
                                            "session_2": record.get("session_2", False) or s2,
                                            "session_3": record.get("session_3", False) or s3,
                                            "session_4": record.get("session_4", False) or s4,
                                            "timestamp": now_sgt().isoformat()
                                        }
                                        supabase.table("attendance").update(updates).eq("id", record["id"]).execute()
                                    else:
                                        # Get resident name
                                        res = supabase.table("participants").select("name").eq("id", match["id"]).execute()
                                        resident_name = res.data[0]["name"] if res.data else match["name"]

                                        # Create new attendance record
                                        supabase.table("attendance").insert({
                                            "participant_id": match["id"],
                                            "name": resident_name,
                                            "date": formatted_date,
                                            "session_1": s1,
                                            "session_2": s2,
                                            "session_3": s3,
                                            "session_4": s4,
                                            "timestamp": now_sgt().isoformat(),
                                            "self_checkin": False,
                                            "source": activity,
                                            "activities": [activity],
                                            "checkin_method": "face_recognition"
                                        }).execute()

                                    # Sync to session attendance
                                    sync_session_attendance_async(
                                        match["id"], match["name"], activity, formatted_date, "face_checkin"
                                    )

                                    checked_in_count += 1

                                except Exception as e:
                                    errors.append(f"{match['name']}: {e}")

                        if checked_in_count > 0:
                            st.success(f"✅ Successfully checked in {checked_in_count} residents!")
                            st.balloons()
                        if errors:
                            for err in errors:
                                st.error(f"❌ Error: {err}")

                        st.rerun()
            else:
                st.warning("⚠️ No faces were recognized. Please ensure residents are enrolled.")