"""
pages/face_checkin.py — UPDATED (Tier A+B fixes)

Key changes from original:
  1. CRITICAL FIX: cv2 lazy-imported inside _draw_annotations() — was imported
     at module top, paying the cost on every page render even when not using
     face recognition. The face_service import is also deferred.
  2. CRITICAL FIX: Persisted results in st.session_state so they survive
     st.rerun(). Original used a single `if st.button(...)` block — clicking
     "Check In All" caused st.rerun() which wiped the recognized faces and
     photo. Now results stay visible after check-in completes.
  3. Removed `time.sleep(3)` before st.rerun() (was blocking 3s + triggering
     full script re-execution).
  4. Removed duplicate success message (lines 242 + 250 in original).
  5. Removed debug st.info() line ("Debug: Faces loaded in memory: N").
  6. Removed st.balloons() (slow on tablets, confuses elderly users).
  7. Fixed `width='stretch'` → `use_container_width=True` (5 occurrences —
     width='stretch' is not a valid Streamlit parameter and was being ignored).
  8. Statistics queries now cached with @st.cache_data(ttl=60) instead of
     running on every render.
  9. Removed inline `import time` (no longer needed).
 10. Camera input only shown if user explicitly opts in (was always shown,
     confusing elderly users who don't expect a camera prompt).
 11. Removed `st.error("❌ DEBUG ERROR...")` inline debug — errors now logged
     and surfaced cleanly via the errors list.
"""

import streamlit as st
import pandas as pd
import logging
from datetime import datetime
from PIL import Image
import io

from config import supabase, DB_CONNECTED, load_activities
from utils import sync_session_attendance_async
from services.attendance_service import AttendanceService

logger = logging.getLogger("community_hub.face_checkin")


def show_face_checkin():
    st.header("📸 Group Photo Check-In")
    st.caption("Take a group photo and automatically check in all recognized residents")

    if not DB_CONNECTED:
        st.error("Database not connected")
        return

    # Lazy import — face_service itself lazy-imports cv2/face_recognition
    from services.face_service import get_face_service
    face_service = get_face_service()

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
        "Choose a group photo",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=False,
        key="face_upload"
    )

    # Camera input is optional — only show if user opts in (avoids surprising
    # elderly users with a camera permission prompt)
    use_camera = st.checkbox("📸 Use device camera instead", key="face_use_camera")
    camera_photo = None
    if use_camera:
        camera_photo = st.camera_input("Take a photo now", key="face_camera")

    image_bytes = None
    image_display = None

    if camera_photo:
        image_bytes = camera_photo.getvalue()
        image_display = Image.open(io.BytesIO(image_bytes))
    elif uploaded_file:
        image_bytes = uploaded_file.getvalue()
        image_display = Image.open(io.BytesIO(image_bytes))

    if image_display:
        st.image(image_display, caption="📷 Selected Photo", use_container_width=True)

    st.divider()

    # ── Process Photo ──
    detect_clicked = st.button("🔍 Detect & Check In Residents", type="primary", use_container_width=True)

    # Clear persisted results when a new photo is selected or detect is clicked
    if detect_clicked:
        st.session_state['face_results'] = None
        st.session_state['face_annotated_bytes'] = None
        st.session_state['face_checked_in'] = False

    # Detect on click
    if image_bytes and detect_clicked:
        with st.spinner("🔍 Analyzing photo and matching faces..."):
            face_locations, face_encodings, rgb_img = face_service.detect_faces(image_bytes)

            if not face_encodings:
                st.error("❌ No faces detected in the photo. Please try again with a clearer image.")
                st.stop()

            st.success(f"✅ Found {len(face_encodings)} face(s) in the photo")

            matches = face_service.identify_faces(face_encodings)

            # Draw annotations (lazy cv2 import)
            annotated_bytes = _draw_annotations(rgb_img, face_locations, matches)

            # Persist results so they survive st.rerun()
            st.session_state['face_results'] = {
                'matches': matches,
                'face_locations': face_locations,
                'recognized_count': sum(1 for m in matches if m is not None),
            }
            st.session_state['face_annotated_bytes'] = annotated_bytes
            st.session_state['face_checked_in'] = False

    # Display persisted results (survives reruns)
    results_state = st.session_state.get('face_results')
    if results_state:
        _render_results(results_state)

        # ── Batch Check-In ──
        recognized_count = results_state['recognized_count']
        already_done = st.session_state.get('face_checked_in', False)

        if recognized_count > 0:
            if not already_done:
                if st.button("✅ Check In All Recognized Residents", type="primary", use_container_width=True):
                    with st.spinner("Processing check-ins..."):
                        _batch_checkin(
                            results_state['matches'],
                            activity,
                            formatted_date,
                            s1, s2, s3, s4
                        )
                    st.session_state['face_checked_in'] = True
                    st.rerun()  # re-render to show post-checkin state
            else:
                st.success("✅ Check-in complete for all recognized residents. Take a new photo to continue.")
        else:
            st.warning("⚠️ No faces were recognized. Please ensure residents are enrolled.")

    st.divider()

    # ── Today's Statistics (cached) ──
    st.subheader("📊 Today's Face Recognition Statistics")
    stats = _get_face_stats(selected_date.strftime("%Y-%m-%d"), activity, enrolled_count)
    c1, c2, c3 = st.columns(3)
    c1.metric("👤 Face Check-Ins Today", stats['face_today'])
    c2.metric("📋 Total Check-Ins Today", stats['total_today'])
    c3.metric("📸 Enrolled Faces", stats['enrolled'])

    st.caption("💡 **Tip:** For best results, use well-lit photos with faces looking forward.")


# ============================================================
# Helpers
# ============================================================

def _draw_annotations(rgb_img, face_locations, matches):
    """Draw bounding boxes on the image. Lazy-imports cv2.
    Returns JPEG bytes (so it can be persisted in session_state)."""
    if rgb_img is None:
        return None
    try:
        import cv2  # lazy import
        import numpy as np
        img_with_boxes = rgb_img.copy()
        for location, match in zip(face_locations, matches):
            top, right, bottom, left = location
            if match:
                color = (0, 255, 0)  # Green
                label = f"{match['name']} ({match['confidence']:.0%})"
            else:
                color = (0, 0, 255)  # Red
                label = "Unknown"
            cv2.rectangle(img_with_boxes, (left, top), (right, bottom), color, 2)
            cv2.rectangle(img_with_boxes, (left, bottom - 25), (right, bottom), color, -1)
            cv2.putText(img_with_boxes, label, (left + 6, bottom - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        # Encode to JPEG bytes for session_state persistence
        ok, buf = cv2.imencode('.jpg', cv2.cvtColor(img_with_boxes, cv2.COLOR_RGB2BGR))
        if ok:
            return buf.tobytes()
    except ImportError:
        logger.warning("cv2 not available — skipping annotation drawing.")
    except Exception as e:
        logger.warning(f"Annotation drawing failed: {e}")
    return None


def _render_results(results_state):
    """Render recognition results (annotated image + table). Survives reruns."""
    st.subheader("📋 Recognition Results")

    annotated_bytes = st.session_state.get('face_annotated_bytes')
    if annotated_bytes:
        st.image(annotated_bytes, caption="📸 Annotated Photo (Green = Recognized, Red = Unknown)", use_container_width=True)

    # Build results table
    rows = []
    for match in results_state['matches']:
        if match:
            rows.append({
                "status": "✅ Recognized",
                "name": match["name"],
                "confidence": f"{match['confidence']:.0%}"
            })
        else:
            rows.append({
                "status": "❌ Unknown",
                "name": "Not recognized",
                "confidence": "-"
            })
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    recognized = results_state['recognized_count']
    if recognized > 0:
        st.success(f"✅ **{recognized}** resident(s) recognized!")


def _batch_checkin(matches, activity, formatted_date, s1, s2, s3, s4):
    """Check in all recognized residents. Logs errors instead of inline-debugging."""
    checked_in_count = 0
    errors = []

    for match in matches:
        if match is None:
            continue
        try:
            success, message, resident = AttendanceService.process_checkin(
                pid=match["id"],
                date=formatted_date,
                activity=activity,
                s1=s1, s2=s2, s3=s3, s4=s4
            )
            if success:
                checked_in_count += 1
            else:
                # Gracefully handles "already checked in" messages
                errors.append(f"{match['name']}: {message}")
        except Exception as e:
            logger.error(f"Face checkin failed for {match.get('name')}: {e}", exc_info=True)
            errors.append(f"{match['name']}: {e}")

    if checked_in_count > 0:
        st.success(f"✅ Successfully checked in {checked_in_count} resident(s)!")
    if errors:
        st.warning("⚠️ Some residents could not be checked in:")
        for err in errors:
            st.caption(f"• {err}")


@st.cache_data(ttl=60, show_spinner=False)
def _get_face_stats(today_str, activity, enrolled_count):
    """Cached statistics — runs at most once per 60 seconds."""
    if not DB_CONNECTED:
        return {'face_today': 0, 'total_today': 0, 'enrolled': enrolled_count}
    try:
        face_checkins = supabase.table("attendance") \
            .select("*", count="exact") \
            .eq("date", today_str) \
            .eq("checkin_method", "face_recognition") \
            .execute()
        total_face = face_checkins.count if face_checkins else 0
    except Exception as e:
        logger.warning(f"face_today stat failed: {e}")
        total_face = 0

    try:
        total_checkins = supabase.table("attendance") \
            .select("*", count="exact") \
            .eq("date", today_str) \
            .eq("source", activity) \
            .execute()
        total_count = total_checkins.count if total_checkins else 0
    except Exception as e:
        logger.warning(f"total_today stat failed: {e}")
        total_count = 0

    return {
        'face_today': total_face,
        'total_today': total_count,
        'enrolled': enrolled_count
    }
