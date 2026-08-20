# services/face_service.py
"""Face recognition service for group photo check-in"""
import streamlit as st
import numpy as np
import json  # 🔥 CRITICAL: Safe JSON parsing
from PIL import Image
import io
import base64
from datetime import datetime
from config import supabase, DB_CONNECTED, now_sgt

# 🔥 Try to import optional dependencies
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    cv2 = None

try:
    import face_recognition
    FACE_RECOGNITION_AVAILABLE = True
except ImportError:
    FACE_RECOGNITION_AVAILABLE = False
    face_recognition = None

class FaceRecognitionService:
    """Handles face detection, enrollment, and recognition for group check-in."""

    def __init__(self):
        self.known_face_encodings = []
        self.known_face_names = []
        self.known_face_ids = []
        self.known_face_photos = []
        if FACE_RECOGNITION_AVAILABLE:
            self._load_known_faces()

    def is_available(self):
        """Check if face recognition is available."""
        return FACE_RECOGNITION_AVAILABLE and CV2_AVAILABLE

    def reload(self):
        """Force-refresh the in-memory face cache. Call after enrolling/
        re-enrolling a face so check-in sees it immediately (no restart)."""
        self._load_known_faces()

    def _load_known_faces(self):
        """Load all enrolled face encodings from database."""
        # 🔥 FIX 1: Clear lists first to prevent duplicates
        self.known_face_encodings = []
        self.known_face_names = []
        self.known_face_ids = []
        self.known_face_photos = []

        if not self.is_available() or not DB_CONNECTED:
            return
        
        try:
            result = supabase.table('participants') \
                .select('id, name, face_encoding, face_photo_url') \
                .eq('active', True) \
                .eq('face_enrolled', True) \
                .execute()
            
            loaded_count = 0
            for p in result.data:
                if p.get('face_encoding'):
                    try:
                        # 🔥 FIX 2: Use json.loads instead of eval
                        encoding_list = json.loads(p['face_encoding'])
                        encoding = np.array(encoding_list, dtype=np.float64)

                        # SAFETY: dlib encodings are exactly 128 numbers. Anything else
                        # (e.g. rows enrolled with DeepFace/Facenet) silently poisons
                        # face_distance -> every face shows "Unknown". Skip with warning.
                        if encoding.shape != (128,):
                            print(f"WARNING: Skipping {p.get('name')}: encoding shape "
                                  f"{encoding.shape} != (128,) - enrolled with DeepFace. "
                                  f"Re-enroll this resident.")
                            continue

                        self.known_face_encodings.append(encoding)
                        self.known_face_names.append(p['name'])
                        self.known_face_ids.append(p['id'])
                        self.known_face_photos.append(p.get('face_photo_url', ''))
                        loaded_count += 1
                    except Exception as e:
                        print(f"❌ Error parsing face for {p.get('name')}: {e}")
            
            print(f"✅ Loaded {loaded_count} enrolled faces into memory.")
        except Exception as e:
            print(f"❌ Error loading faces from DB: {e}")

    def detect_faces(self, image_bytes):
        """Detect all faces in an image."""
        if not self.is_available():
            return [], [], None
        try:
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            
            face_locations = face_recognition.face_locations(rgb_img)
            face_encodings = face_recognition.face_encodings(rgb_img, face_locations)
            return face_locations, face_encodings, rgb_img
        except Exception as e:
            print(f" Error detecting faces: {e}")
            return [], [], None

    def identify_faces(self, face_encodings, tolerance=0.6):
        """Match detected faces against known faces."""
        if not self.is_available() or len(self.known_face_encodings) == 0:
            return [None] * len(face_encodings)
        
        matches = []
        for encoding in face_encodings:
            face_distances = face_recognition.face_distance(
                self.known_face_encodings, encoding
            )
            best_match_index = np.argmin(face_distances)
            # Diagnostic: distances < 0.6 match. If everything is "Unknown",
            # read these in the console:
            #   ~0.4-0.6 = same person, borderline -> photo quality issue
            #   ~1.0-1.5 = wrong vector space -> encoding library mismatch
            print(f"Best match: {self.known_face_names[best_match_index]} "
                  f"| distance={face_distances[best_match_index]:.4f} "
                  f"| tolerance={tolerance}")
            if face_distances[best_match_index] < tolerance:
                matches.append({
                    'id': self.known_face_ids[best_match_index],
                    'name': self.known_face_names[best_match_index],
                    'confidence': 1 - face_distances[best_match_index]
                })
            else:
                matches.append(None)
        return matches

    def enroll_face(self, participant_id, image_bytes):
        """Enroll a participant's face for future recognition."""
        if not self.is_available():
            return {'success': False, 'error': 'Face recognition is not available'}
        try:
            face_locations, face_encodings, _ = self.detect_faces(image_bytes)
            if not face_encodings:
                return {'success': False, 'error': '❌ No face detected in image'}
            if len(face_encodings) > 1:
                return {'success': False, 'error': '❌ Multiple faces detected'}
            
            # 🔥 FIX 3: Use json.dumps for consistent formatting
            encoding_str = json.dumps(face_encodings[0].tolist())
            
            supabase.table('participants') \
                .update({
                    'face_encoding': encoding_str,
                    'face_enrolled': True,
                    'face_updated_at': now_sgt().isoformat()
                }) \
                .eq('id', participant_id) \
                .execute()
            
            # Reload known faces
            self._load_known_faces()
            return {'success': True, 'message': '✅ Face enrolled successfully!'}
        except Exception as e:
            return {'success': False, 'error': f'Error: {e}'}

    def get_enrolled_count(self):
        """Get number of enrolled faces."""
        return len(self.known_face_encodings)

# Singleton instance
_face_service = None

def get_face_service():
    global _face_service
    if _face_service is None:
        _face_service = FaceRecognitionService()
    return _face_service