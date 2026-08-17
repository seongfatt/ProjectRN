# services/face_service.py
"""Face recognition service using DeepFace (MTCNN Detector)"""

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
            
            for p in result.data:
                if p.get('face_encoding'):
                    try:
                        encoding = eval(p['face_encoding'])
                        if isinstance(encoding, list):
                            self.known_faces[p['id']] = {
                                'name': p['name'],
                                'encoding': np.array(encoding)
                            }
                    except Exception as e:
                        print(f"Error loading face for {p.get('name')}: {e}")
            
            print(f"✅ Loaded {len(self.known_faces)} enrolled faces (DeepFace 512-dim)")
        except Exception as e:
            print(f"Error loading faces: {e}")
    
    def detect_faces(self, image_bytes):
        """
        Detect faces using DeepFace's MTCNN detector (handles glasses).
        Returns: face_locations, face_encodings, rgb_image
        """
        if not self.is_available():
            return [], [], None
        
        try:
            # 1. Decode image for DeepFace
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img is None:
                pil_img = Image.open(io.BytesIO(image_bytes))
                img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

            rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

            # 2. DETECT FACES USING DEEPFACE'S MTCNN (Highly reliable for glasses)
            # We run a small represent call with MTCNN just to find bounding boxes, 
            # but we don't keep the vectors yet.
            try:
                # We use MTCNN to locate faces, but don't force DeepFace to compute vectors here.
                # We just want the coordinates.
                detection_objs = DeepFace.represent(
                    img_path=rgb_img, 
                    model_name="Facenet", 
                    enforce_detection=True, 
                    detector_backend="mtcnn"
                )
            except ValueError:
                # No faces detected
                return [], [], rgb_img
            
            if not detection_objs:
                return [], [], rgb_img

            # Convert MTCNN coordinates to (top, right, bottom, left)
            face_locations = []
            for obj in detection_objs:
                if 'facial_area' in obj:
                    area = obj['facial_area']
                    face_locations.append((area['y'], area['x'] + area['w'], area['y'] + area['h'], area['x']))
                else:
                    # Fallback if coordinates are missing
                    face_locations.append((0, 0, 100, 100))

            # 3. EXTRACT 512-VECTOR EMBEDDINGS (Using "skip" to avoid re-detection)
            face_encodings = []
            
            for (top, right, bottom, left) in face_locations:
                try:
                    # Crop the face out of the image
                    face_crop = rgb_img[top:bottom, left:right]
                    
                    # Use "skip" backend because the face is already cropped/detected
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
        """
        Match detected faces against known faces using Euclidean distance.
        """
        matches = []
        
        if len(self.known_faces) == 0:
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