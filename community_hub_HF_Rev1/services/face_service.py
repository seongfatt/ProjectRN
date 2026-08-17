# services/face_service.py
"""Face recognition service using DeepFace (lightweight, no dlib)"""

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
        self.known_faces = {}  # {participant_id: {'name': name, 'encoding': encoding_array}}
        self._load_known_faces()
    
    def is_available(self):
        """Check if DeepFace is available."""
        return DEEPFACE_AVAILABLE and CV2_AVAILABLE
    
    def _load_known_faces(self):
        """Load enrolled faces from database."""
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
                        # Parse the stored encoding (DeepFace saves as 512 vector)
                        encoding = eval(p['face_encoding'])
                        if isinstance(encoding, list):
                            # Convert to numpy array for faster math
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
        Detect all faces in an image using DeepFace's backend.
        Returns: face_locations, face_encodings, rgb_image
        """
        if not self.is_available():
            return [], [], None
        
        try:
            # Decode image
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img is None:
                # Fallback to PIL
                pil_img = Image.open(io.BytesIO(image_bytes))
                img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
            
            rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            
            # 🔥 Use DeepFace to extract embeddings
            # We switch to "retinaface" (most robust) and disable enforce_detection to avoid strict crashes
            try:
                objs = DeepFace.represent(
                    img_path=rgb_img, 
                    model_name="Facenet", 
                    enforce_detection=False,  # <-- CRUCIAL FIX: Allows processing even if detection is faint
                    detector_backend="retinaface" # <-- CRUCIAL FIX: Best detector for glares/angles
                )
                
                if not objs:
                    # Even with enforce_detection=False, if nothing is found, return empty
                    return [], [], rgb_img

                # Prepare face_locations 
                face_locations = []
                face_encodings = []
                
                for obj in objs:
                    # Extract the 512-dim encoding
                    face_encodings.append(np.array(obj['embedding']))
                    # Get facial area coordinates if available
                    if 'facial_area' in obj:
                        area = obj['facial_area']
                        face_locations.append((area['y'], area['x'] + area['w'], area['y'] + area['h'], area['x']))
                    else:
                        # If coords missing, use dummy coords to prevent UI crash
                        face_locations.append((0, 0, 100, 100))
                
                return face_locations, face_encodings, rgb_img

            except ValueError:
                # No faces detected
                return [], [], rgb_img
            except Exception as e:
                print(f"DeepFace detection error: {e}")
                return [], [], rgb_img
            
        except Exception as e:
            print(f"Error in detect_faces: {e}")
            return [], [], None
    
    def identify_faces(self, face_encodings, tolerance=0.6):
        """
        Match detected faces against known faces using Euclidean distance on 512-vectors.
        Returns: list of matches (id, name, confidence) or None
        """
        matches = []
        
        if not self.is_available() or len(self.known_faces) == 0:
            return [None] * len(face_encodings)
        
        for encoding in face_encodings:
            best_match = None
            best_distance = float('inf')
            
            # Iterate through all known faces
            for pid, data in self.known_faces.items():
                try:
                    # Calculate Euclidean distance between the two 512 vectors
                    distance = np.linalg.norm(data['encoding'] - encoding)
                    
                    # If distance is less than tolerance and better than previous best
                    if distance < tolerance and distance < best_distance:
                        best_distance = distance
                        # Calculate confidence (1 is perfect, 0 is far away)
                        # DeepFace distances usually range 0.0 - 1.4. 
                        # A distance of 0.4 is roughly 80% confidence.
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
        """Get number of enrolled faces."""
        return len(self.known_faces)


# Singleton instance
_face_service = None

def get_face_service():
    """Get or create singleton FaceRecognitionService instance."""
    global _face_service
    if _face_service is None:
        _face_service = FaceRecognitionService()
    return _face_service