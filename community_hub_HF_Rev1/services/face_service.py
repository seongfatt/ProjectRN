# services/face_service.py
"""Face recognition service — gracefully handles missing dependencies"""

import streamlit as st
import cv2
import numpy as np
from PIL import Image
import io
from config import supabase, DB_CONNECTED, now_sgt

# 🔥 Try to import face_recognition, but don't crash if missing
try:
    import face_recognition
    FACE_RECOGNITION_AVAILABLE = True
except ImportError:
    FACE_RECOGNITION_AVAILABLE = False
    face_recognition = None

class FaceRecognitionService:
    """Handles face detection, enrollment, and recognition."""
    
    def __init__(self):
        self.known_face_encodings = []
        self.known_face_names = []
        self.known_face_ids = []
        self.known_face_photos = []
        if FACE_RECOGNITION_AVAILABLE:
            self._load_known_faces()
    
    def is_available(self):
        """Check if face recognition is available."""
        return FACE_RECOGNITION_AVAILABLE
    
    def _load_known_faces(self):
        """Load all enrolled face encodings from database."""
        if not FACE_RECOGNITION_AVAILABLE:
            return
        
        if not DB_CONNECTED:
            return
        
        try:
            result = supabase.table('participants') \
                .select('id, name, face_encoding, face_photo_url') \
                .eq('active', True) \
                .eq('face_enrolled', True) \
                .execute()
            
            for p in result.data:
                if p.get('face_encoding'):
                    try:
                        encoding = np.array(eval(p['face_encoding']))
                        self.known_face_encodings.append(encoding)
                        self.known_face_names.append(p['name'])
                        self.known_face_ids.append(p['id'])
                        self.known_face_photos.append(p.get('face_photo_url', ''))
                    except Exception as e:
                        print(f"Error loading face for {p.get('name')}: {e}")
            
            print(f"✅ Loaded {len(self.known_face_encodings)} enrolled faces")
        except Exception as e:
            print(f"Error loading faces: {e}")
    
    def detect_faces(self, image_bytes):
        """Detect all faces in an image."""
        if not FACE_RECOGNITION_AVAILABLE:
            return [], [], None
        
        try:
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            
            face_locations = face_recognition.face_locations(rgb_img)
            face_encodings = face_recognition.face_encodings(rgb_img, face_locations)
            
            return face_locations, face_encodings, rgb_img
        except Exception as e:
            print(f"Error detecting faces: {e}")
            return [], [], None
    
    def identify_faces(self, face_encodings, tolerance=0.6):
        """Match detected faces against known faces."""
        if not FACE_RECOGNITION_AVAILABLE or len(self.known_face_encodings) == 0:
            return [None] * len(face_encodings)
        
        matches = []
        for encoding in face_encodings:
            face_distances = face_recognition.face_distance(
                self.known_face_encodings, encoding
            )
            best_match_index = np.argmin(face_distances)
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
        """Enroll a participant's face."""
        if not FACE_RECOGNITION_AVAILABLE:
            return {'success': False, 'error': 'Face recognition is not available'}
        
        try:
            face_locations, face_encodings, _ = self.detect_faces(image_bytes)
            
            if not face_encodings:
                return {'success': False, 'error': '❌ No face detected in image'}
            
            if len(face_encodings) > 1:
                return {'success': False, 'error': '❌ Multiple faces detected. Please use a single photo.'}
            
            encoding_str = str(face_encodings[0].tolist())
            
            supabase.table('participants') \
                .update({
                    'face_encoding': encoding_str,
                    'face_enrolled': True,
                    'face_updated_at': now_sgt().isoformat()
                }) \
                .eq('id', participant_id) \
                .execute()
            
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
    """Get or create singleton FaceRecognitionService instance."""
    global _face_service
    if _face_service is None:
        _face_service = FaceRecognitionService()
    return _face_service
