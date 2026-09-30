import streamlit as st
from config import supabase
import io
import json
import numpy as np
from PIL import Image
from datetime import datetime

# 🔥 SAFE IMPORT: face_recognition is optional — app works without it
try:
    import face_recognition
    FACE_REC_AVAILABLE = True
except ImportError:
    FACE_REC_AVAILABLE = False
    face_recognition = None

def show_face_enrollment():
    st.subheader("📸 Face Enrollment for Group Check-In")
    st.caption("Enroll residents' faces for group photo check-in.")

    if not FACE_REC_AVAILABLE:
        st.error("⚠️ Face recognition library (`face_recognition`) is not installed on this server.")
        st.info("Please ensure `dlib-bin==19.24.2` and `face-recognition==1.3.0` are in your `requirements.txt` and rebuild your deployment.")
        return

    # --- rest of your existing enrollment code follows here ---
    search_face = st.text_input("Search resident by Name or ID", key="face_enroll_search")
    if search_face:
        s = search_face.lower()
        matches = [p for p in st.session_state.participants if p.get('active', True) and (s in p['name'].lower() or s in str(p.get('id', '')).lower())]
        if matches:
            for p in matches[:5]:
                with st.container():
                    st.markdown(f"**{p['name']}** — ID: {p['id'][:12]}...")

                    if p.get('face_enrolled', False) and p.get('face_photo_url'):
                        st.success("✅ Face enrolled and photo saved")
                    elif p.get('face_enrolled', False) and not p.get('face_photo_url'):
                        st.warning("⚠️ Face enrolled (encoding only) - Please re-upload photo")
                    else:
                        st.warning("⚠️ Face not enrolled")

                    with st.expander("📷 Upload Face Photo", expanded=False):
                        st.caption("Upload a clear photo of the resident's face.")
                        st.caption("💡 **Tips:** Well-lit, face looking forward, single face only.")
                        face_photo = st.file_uploader(
                            "Upload Face Photo",
                            type=['jpg', 'jpeg', 'png'],
                            key=f"face_enroll_{p['id']}"
                        )
                        if face_photo:
                            st.image(face_photo, caption="📸 Preview", width=150)
                            if st.button("✅ Enroll Face", key=f"enroll_btn_{p['id']}", use_container_width=True):
                                try:
                                    image = Image.open(io.BytesIO(face_photo.getvalue())).convert("RGB")
                                    image_np = np.array(image)

                                    face_locations = face_recognition.face_locations(image_np, model='hog')
                                    if not face_locations:
                                        face_locations = face_recognition.face_locations(image_np, number_of_times_to_upsample=2, model='hog')
                                    if not face_locations:
                                        st.error("❌ No face detected. Please ensure the face is clearly visible and forward-facing.")
                                        st.stop()
                                    if len(face_locations) > 1:
                                        st.error("❌ Multiple faces detected. Please upload a photo with only this resident.")
                                        st.stop()

                                    encodings = face_recognition.face_encodings(image_np, face_locations)
                                    if not encodings:
                                        st.error("❌ Could not generate a face encoding. Try a clearer, better-lit photo.")
                                        st.stop()
                                    encoding_str = json.dumps(encodings[0].tolist())

                                    file_ext = face_photo.name.split('.')[-1]
                                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                    unique_storage_path = f"resident_faces/{p['id']}_{timestamp}.{file_ext}"
                                    supabase.storage.from_('face_photos').upload(
                                        path=unique_storage_path,
                                        file=face_photo.getvalue(),
                                        file_options={"content-type": face_photo.type}
                                    )

                                    public_url = supabase.storage.from_('face_photos').get_public_url(unique_storage_path)
                                    supabase.table('participants').update({
                                        'face_encoding': encoding_str,
                                        'face_enrolled': True,
                                        'face_photo_url': public_url,
                                        'face_updated_at': datetime.now().isoformat()
                                    }).eq('id', p['id']).execute()

                                    try:
                                        from services.face_service import get_face_service
                                        get_face_service().reload()
                                    except Exception:
                                        pass

                                    st.success(f"✅ Face enrolled and photo saved successfully for {p['name']}!")
                                    st.info("💡 The new face is active immediately — no restart needed.")
                                except Exception as e:
                                    st.error(f"❌ Error during enrollment: {str(e)}")
                    st.divider()
        else:
            st.info("No residents found matching your search.")
    else:
        st.info("🔍 Type a name or ID above to search for a resident.")