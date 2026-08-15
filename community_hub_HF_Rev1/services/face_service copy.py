# services/face_service.py
"""Face recognition service for group photo check-in"""

import cv2
import numpy as np
import face_recognition
from PIL import Image
import io
import base64
from datetime import datetime
import streamlit as st
from config import supabase, DB_CONNECTED, now_sgt

class FaceRecognitionService:
    """Handles face detection, enrollment, and recognition for group check-in."""
    
    def __init__(self):
        self.known_face_encodings = []
        self.known_face_names = []
        self.known_face_ids = []
        self.known_face_photos = []
        self._load_known_faces()
    
    def _load_known_faces(self):
        """Load all enrolled face encodings from database."""
        if not DB_CONNECTED:
            return
        
        try:
            # Fetch all participants with face data
            result = supabase.table('participants') \
                .select('id, name, face_encoding, face_photo_url') \
                .eq('active', True) \
                .eq('face_enrolled', True) \
                .execute()
            
            for p in result.data:
                if p.get('face_encoding'):
                    try:
                        # Convert stored string back to numpy array
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
        """
        Detect all faces in an image.
        Returns: face_locations, face_encodings, rgb_image
        """
        try:
            # Convert bytes to numpy array
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            
            # Detect face locations
            face_locations = face_recognition.face_locations(rgb_img)
            face_encodings = face_recognition.face_encodings(rgb_img, face_locations)
            
            return face_locations, face_encodings, rgb_img
        except Exception as e:
            print(f"Error detecting faces: {e}")
            return [], [], None
    
    def identify_faces(self, face_encodings, tolerance=0.6):
        """
        Match detected faces against known faces.
        Returns: list of matches (id, name, confidence) or None
        """
        matches = []
        
        if len(self.known_face_encodings) == 0:
            return [None] * len(face_encodings)
        
        for encoding in face_encodings:
            # Compare with known faces
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
        """
        Enroll a participant's face for future recognition.
        Returns: {success: bool, message: str}
        """
        try:
            # Detect face in image
            face_locations, face_encodings, _ = self.detect_faces(image_bytes)
            
            if not face_encodings:
                return {'success': False, 'error': '❌ No face detected in image'}
            
            if len(face_encodings) > 1:
                return {'success': False, 'error': '❌ Multiple faces detected. Please use a single photo.'}
            
            # Store encoding as string
            encoding_str = str(face_encodings[0].tolist())
            
            # Update participant record
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
    """Get or create singleton FaceRecognitionService instance."""
    global _face_service
    if _face_service is None:
        _face_service = FaceRecognitionService()
    return _face_service