"""
pages/face_enrollment.py — UPDATED (Tier A fixes)

Key changes from original:
  1. CRITICAL FIX: face_recognition imported lazily inside the function (not
     at module top). Original imported it at top — every page that imported
     this module paid the 5-15s ML cold-start cost. Now ML only loads when
     someone actually opens the face enrollment page.
  2. Replaced st.stop() with early return — st.stop() halts the entire Streamlit
     script (including other pages); return() only exits this function.
  3. Added un-enroll / delete face option (was missing entirely).
  4. Added image size validation — rejects photos > 5MB or smaller than 200px
     to prevent slow uploads and unrecognizable faces.
  5. Storage upload + DB update now wrapped so a failed DB update after a
     successful Storage upload logs a warning about the orphan file.
  6. Uses face_service.remove_face() for in-memory cache invalidation after
     un-enroll (cheaper than full reload).
  7. Increased matches shown from 5 to 20 (was hiding the right resident).
  8. Added image preview dimension hint (resize on upload for speed).
  9. Removed duplicate "Face enrolled (encoding only)" branch — if photo_url
     is missing, treat it as needing re-enroll.
"""

import streamlit as st
from config import supabase
import io
import json
import logging
import numpy as np
from PIL import Image
from datetime import datetime

logger = logging.getLogger("community_hub.face_enroll")

# 🔥 LAZY IMPORT: face_recognition is now imported inside the function below,
# not at module top. This keeps the page-import cost near-zero.
# The face_service.is_available() check is the only thing that runs at import.


def show_face_enrollment():
    st.subheader("📸 Face Enrollment for Group Check-In")
    st.caption("Enroll residents' faces for group photo check-in.")

    # Lazy import face_service (which itself lazy-imports cv2/face_recognition)
    from services.face_service import get_face_service, _check_deps
    face_service = get_face_service()

    if not face_service.is_available():
        st.error("⚠️ Face recognition library is not installed on this server.")
        st.info("Add these to `requirements.txt` and rebuild: `dlib-bin==19.24.2`, `face-recognition==1.3.0`, `opencv-python-headless==4.8.1.78`.")
        return

    search_face = st.text_input("Search resident by Name or ID", key="face_enroll_search")
    if not search_face:
        st.info("🔍 Type a name or ID above to search for a resident.")
        return

    s = search_face.lower().strip()
    participants = st.session_state.get('participants', [])
    matches = [
        p for p in participants
        if p.get('active', True) and (
            s in p['name'].lower() or s in str(p.get('id', '')).lower()
        )
    ]

    if not matches:
        st.info("No residents found matching your search.")
        return

    # Show up to 20 matches (was 5 — hid the right resident if more than 5)
    for p in matches[:20]:
        with st.container():
            st.markdown(f"**{p['name']}** — ID: {p['id'][:12]}... · Room/Block: {p.get('block_no', '—')}")

            face_enrolled = bool(p.get('face_enrolled', False))
            face_photo_url = p.get('face_photo_url')

            if face_enrolled and face_photo_url:
                st.success("✅ Face enrolled and photo saved")
                # Show existing photo
                try:
                    st.image(face_photo_url, caption="Current enrolled photo", width=150)
                except Exception:
                    st.caption("(Photo preview unavailable)")
            elif face_enrolled and not face_photo_url:
                st.warning("⚠️ Face encoding exists but photo is missing — please re-enroll.")
            else:
                st.warning("⚠️ Face not enrolled")

            col_enroll, col_unenroll = st.columns([3, 1])

            with col_enroll:
                with st.expander("📷 Upload Face Photo", expanded=False):
                    st.caption("Upload a clear photo of the resident's face.")
                    st.caption("💡 **Tips:** Well-lit, face looking forward, single face only. Max 5MB.")

                    face_photo = st.file_uploader(
                        "Upload Face Photo",
                        type=['jpg', 'jpeg', 'png'],
                        key=f"face_enroll_{p['id']}"
                    )
                    if face_photo:
                        # 🔥 Validate size BEFORE processing
                        size_mb = len(face_photo.getvalue()) / (1024 * 1024)
                        if size_mb > 5:
                            st.error(f"❌ Photo is {size_mb:.1f}MB — please upload a photo under 5MB.")
                            continue  # expander context — use return instead

                        # Preview
                        try:
                            preview_img = Image.open(io.BytesIO(face_photo.getvalue())).convert("RGB")
                            st.image(preview_img, caption=f"📸 Preview ({preview_img.size[0]}×{preview_img.size[1]})", width=150)
                            if preview_img.size[0] < 200 or preview_img.size[1] < 200:
                                st.error("❌ Photo is too small (under 200px). Use a clearer, larger photo.")
                                continue
                        except Exception as e:
                            st.error(f"❌ Could not read image: {e}")
                            continue

                        if st.button("✅ Enroll Face", key=f"enroll_btn_{p['id']}", use_container_width=True):
                            _enroll_face(p, face_photo, face_service)

            with col_unenroll:
                if face_enrolled:
                    if st.button("🗑 Un-enroll", key=f"unenroll_btn_{p['id']}", use_container_width=True):
                        _unenroll_face(p, face_service)

            st.divider()


def _enroll_face(participant, face_photo, face_service):
    """Encapsulated enrollment logic. Uses early-return instead of st.stop()."""
    # Lazy import — only loads ML when actually enrolling
    try:
        import face_recognition
    except ImportError:
        st.error("❌ face_recognition library not available. Contact admin.")
        return

    try:
        # Open + resize for faster processing (cap at 800px on the long side)
        image = Image.open(io.BytesIO(face_photo.getvalue())).convert("RGB")
        max_dim = 800
        if max(image.size) > max_dim:
            image.thumbnail((max_dim, max_dim), Image.LANCZOS)
        image_np = np.array(image)

        # Detect faces
        face_locations = face_recognition.face_locations(image_np, model='hog')
        if not face_locations:
            face_locations = face_recognition.face_locations(image_np, number_of_times_to_upsample=2, model='hog')
        if not face_locations:
            st.error("❌ No face detected. Ensure the face is clearly visible and forward-facing.")
            return
        if len(face_locations) > 1:
            st.error("❌ Multiple faces detected. Upload a photo with only this resident.")
            return

        encodings = face_recognition.face_encodings(image_np, face_locations)
        if not encodings:
            st.error("❌ Could not generate a face encoding. Try a clearer, better-lit photo.")
            return
        encoding_str = json.dumps(encodings[0].tolist())

        # Upload to Supabase Storage
        file_ext = face_photo.name.split('.')[-1].lower()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_storage_path = f"resident_faces/{participant['id']}_{timestamp}.{file_ext}"

        try:
            supabase.storage.from_('face_photos').upload(
                path=unique_storage_path,
                file=face_photo.getvalue(),
                file_options={"content-type": face_photo.type}
            )
        except Exception as e:
            st.error(f"❌ Failed to upload photo to storage: {e}")
            return

        public_url = supabase.storage.from_('face_photos').get_public_url(unique_storage_path)

        # Update DB
        try:
            supabase.table('participants').update({
                'face_encoding': encoding_str,
                'face_enrolled': True,
                'face_photo_url': public_url,
                'face_updated_at': datetime.now().isoformat()
            }).eq('id', participant['id']).execute()
        except Exception as e:
            logger.error(
                f"Storage upload succeeded but DB update failed for {participant['id']}. "
                f"ORPHAN FILE at {unique_storage_path}. Manual cleanup needed. Error: {e}"
            )
            st.error(f"❌ Photo uploaded but DB update failed. Orphan file at: {unique_storage_path}")
            return

        # Invalidate in-memory cache
        try:
            face_service.reload()
        except Exception as e:
            logger.warning(f"face_service.reload() failed: {e}")

        st.success(f"✅ Face enrolled and photo saved for {participant['name']}!")
        st.info("💡 The new face is active immediately — no restart needed.")
        st.cache_data.clear()  # bust participants cache so list refreshes

    except Exception as e:
        logger.error(f"Enrollment error for {participant['id']}: {e}", exc_info=True)
        st.error(f"❌ Error during enrollment: {e}")


def _unenroll_face(participant, face_service):
    """Remove face enrollment from DB + in-memory cache."""
    try:
        supabase.table('participants').update({
            'face_encoding': None,
            'face_enrolled': False,
            'face_photo_url': None,
            'face_updated_at': datetime.now().isoformat()
        }).eq('id', participant['id']).execute()

        # Remove from in-memory cache (cheaper than full reload)
        try:
            face_service.remove_face(participant['id'])
        except Exception as e:
            logger.warning(f"face_service.remove_face() failed, doing full reload: {e}")
            face_service.reload()

        st.success(f"🗑 Face enrollment removed for {participant['name']}.")
        st.cache_data.clear()
    except Exception as e:
        logger.error(f"Un-enroll error for {participant['id']}: {e}", exc_info=True)
        st.error(f"❌ Error removing face enrollment: {e}")
