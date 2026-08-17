# services/face_service.py
"""Face recognition service using DeepFace (DEBUG MODE)"""

import streamlit as st
import numpy as np
import cv2
from PIL import Image
import io
from datetime import datetime
from config import supabase, DB_CONNECTED, now_sgt

# 🔥 Try to import DeepFace
try:
    from deepface import DeepFace
    DEEPFACE_AVAILABLE = True
    print("✅ DeepFace is available")
except ImportError as e:
    DEEPFACE_AVAILABLE = False
    print(f"⚠️ DeepFace not available: {e}")

# 🔥 Check OpenCV
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    cv2 = None


class FaceRecognitionService:
    """Handles face detection and recognition using DeepFace."""
    
    def __init__(self):
        self.known_faces = {}  
        self._load_known_faces()
    
    def is_available(self):
        return DEEPFACE_AVAILABLE and CV2_AVAILABLE
    
    def _load_known_faces(self):
        if not self.is_available() or not DB_CONNECTED:
            return
        
        try:
            result = supabase.table('participants') \
                .select('id, name, face_encoding') \
                .eq('active', True) \
                .eq('face_enrolled', True) \
                .execute()
            
            print(f"🔍 DEBUG: Raw database query returned {len(result.data)} enrolled residents.")
            
            for p in result.data:
                if p.get('face_encoding'):
                    try:
                        encoding = eval(p['face_encoding'])
                        if isinstance(encoding, list):
                            self.known_faces[p['id']] = {
                                'name': p['name'],
                                'encoding': np.array(encoding)
                            }
                            print(f"✅ DEBUG: Loaded vector for {p['name']} (Length: {len(encoding)})")
                        else:
                            print(f"❌ DEBUG: {p['name']} has face_encoding, but it's not a list! Type: {type(encoding)}")
                    except Exception as e:
                        print(f"❌ DEBUG: Failed to parse face_encoding for {p.get('name')}: {e}")
                else:
                    print(f"⚠️ DEBUG: {p.get('name')} has face_enrolled=True, but face_encoding is EMPTY/NULL!")
            
            print(f"✅ Loaded {len(self.known_faces)} enrolled faces into memory.")
        except Exception as e:
            print(f"Error loading faces: {e}")
    
    def detect_faces(self, image_bytes):
        if not self.is_available():
            return [], [], None
        
        try:
            # 1. Decode image using OpenCV
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img is None:
                pil_img = Image.open(io.BytesIO(image_bytes))
                img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

            rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

            # 2. Use face_recognition to FIND the face locations
            import face_recognition
            face_locations = face_recognition.face_locations(rgb_img, model='hog')

            if not face_locations:
                return [], [], rgb_img

            # 3. Extract 512-vector embeddings 
            face_encodings = []
            
            for (top, right, bottom, left) in face_locations:
                try:
                    # Crop the face out of the image
                    face_crop = rgb_img[top:bottom, left:right]
                    
                    embedding_obj = DeepFace.represent(
                        img_path=face_crop, 
                        model_name="Facenet", 
                        enforce_detection=False,
                        detector_backend="skip" 
                    )
                    
                    if embedding_obj:
                        vec = embedding_obj[0]['embedding']
                        face_encodings.append(np.array(vec))
                    else:
                        face_encodings.append(np.zeros(512))
                            
                except Exception as e:
                    print(f"DeepFace extraction error on crop: {e}")
                    face_encodings.append(np.zeros(512))

            return face_locations, face_encodings, rgb_img

        except Exception as e:
            print(f"Error in detect_faces: {e}")
            return [], [], None
    
    def identify_faces(self, face_encodings, tolerance=0.99):
        matches = []
        
        if len(self.known_faces) == 0:
            print("🚨 CRITICAL ERROR: known_faces is EMPTY. Check the DB logs above.")
            return [None] * len(face_encodings)
        
        for encoding in face_encodings:
            best_match = None
            best_distance = float('inf')
            
            for pid, data in self.known_faces.items():
                try:
                    distance = np.linalg.norm(data['encoding'] - encoding)
                    
                    if distance < tolerance and distance < best_distance:
                        best_distance = distance
                        confidence = max(0.0, 1.0 - (distance / 1.4))
                        
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