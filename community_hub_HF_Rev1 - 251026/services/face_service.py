# services/face_service.py
"""Face recognition service using JSON-safe parsing and dictionaries."""

import streamlit as st
import numpy as np
import json
import os
from PIL import Image
import io
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
    """Handles face detection, enrollment, and recognition using dictionaries."""
    
    def __init__(self):
        # 🔥 Initialize the dictionary that face_checkin.py is looking for
        self.known_faces = {}  
        self._load_known_faces()
    
    def is_available(self):
        return FACE_RECOGNITION_AVAILABLE and CV2_AVAILABLE

    def reload(self):
        self._load_known_faces()

    def _load_known_faces(self):
        """Load all enrolled face encodings from database."""
        self.known_faces = {}  # Reset dictionary

        if not self.is_available() or not DB_CONNECTED:
            return
        
        try:
            result = supabase.table('participants') \
                .select('id, name, face_encoding') \
                .eq('active', True) \
                .eq('face_enrolled', True) \
                .execute()
            
            loaded_count = 0
            for p in result.data:
                if p.get('face_encoding'):
                    try:
                        # Use json.loads for safety
                        encoding_list = json.loads(p['face_encoding'])
                        encoding = np.array(encoding_list, dtype=np.float64)

                        # 🔥 CRITICAL: Only accept 128-vectors
                        if encoding.shape != (128,):
                            print(f"⚠️ Skipping {p.get('name')}: Encoding shape {encoding.shape}. Must be (128,). Re-enroll with correct system.")
                            continue

                        # Store in the dictionary
                        self.known_faces[p['id']] = {
                            'name': p['name'],
                            'encoding': encoding
                        }
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
            print(f"Error detecting faces: {e}")
            return [], [], None

    def identify_faces(self, face_encodings, tolerance=0.6):
        """
        Match detected faces against known faces using Euclidean distance.
        """
        # 🔥 SMART TOLERANCE: 15.0 on your local PC, 0.6 on the cloud
        if os.environ.get('STREAMLIT_SHARING') or os.environ.get('STREAMLIT_CLOUD'):
            effective_tolerance = 0.6
        else:
            effective_tolerance = 0.5  # Your local PC needs 0.5 for glasses

        matches = []
        
        if len(self.known_faces) == 0:
            return [None] * len(face_encodings)
        
        for encoding in face_encodings:
            best_match = None
            best_distance = float('inf')
            
            for pid, data in self.known_faces.items():
                try:
                    distance = np.linalg.norm(data['encoding'] - encoding)
                    
                    if distance < effective_tolerance and distance < best_distance:
                        best_distance = distance
                        confidence = max(0.0, 1.0 - (distance / 1.0))
                        
                        best_match = {
                            'id': pid,
                            'name': data['name'],
                            'confidence': confidence
                        }
                except Exception as e:
                    continue
            
            matches.append(best_match)
        
        return matches

    def get_enrolled_count(self):
        return len(self.known_faces)


# Singleton instance
_face_service = None

def get_face_service():
    global _face_service
    if _face_service is None:
        _face_service = FaceRecognitionService()
    return _face_service