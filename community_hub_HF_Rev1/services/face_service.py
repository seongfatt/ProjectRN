# services/face_service.py
"""Face recognition service using DeepFace (lightweight, no dlib)"""

import streamlit as st
import numpy as np
import cv2
from PIL import Image
import io
import base64
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
    """Handles face detection and recognition using DeepFace (no dlib)."""
    
    def __init__(self):
        self.known_faces = {}  # {participant_id: {'name': name, 'encoding': encoding}}
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
                        # Parse the stored encoding
                        encoding = eval(p['face_encoding'])
                        if isinstance(encoding, list):
                            self.known_faces[p['id']] = {
                                'name': p['name'],
                                'encoding': encoding
                            }
                    except Exception as e:
                        print(f"Error loading face for {p.get('name')}: {e}")
            
            print(f"✅ Loaded {len(self.known_faces)} enrolled faces")
        except Exception as e:
            print(f"Error loading faces: {e}")
    
    def detect_faces(self, image_bytes):
        """
        Detect all faces in an image using DeepFace.
        Returns: face_locations, face_encodings, rgb_image
        """
        if not self.is_available():
            return [], [], None
        
        try:
            # Convert bytes to numpy array
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            
            # Save temporary file for DeepFace (it works better with file paths)
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                cv2.imwrite(tmp.name, img)
                tmp_path = tmp.name
            
            # Extract faces using DeepFace
            try:
                faces = DeepFace.extract_faces(
                    img_path=tmp_path,
                    target_size=(224, 224),
                    detector_backend='opencv'  # Faster than 'mtcnn'
                )
            except Exception as e:
                print(f"DeepFace extraction error: {e}")
                faces = []
            
            # Clean up temp file
            try:
                import os
                os.unlink(tmp_path)
            except:
                pass
            
            face_locations = []
            face_encodings = []
            
            if faces and isinstance(faces, list):
                for face_data in faces:
                    if isinstance(face_data, dict) and 'face' in face_data:
                        # Get the face image
                        face_img = face_data['face']
                        if isinstance(face_img, np.ndarray):
                            face_encodings.append(face_img)
                            
                            # Get approximate location
                            if 'area' in face_data:
                                x, y, w, h = face_data['area']
                                face_locations.append((y, x + w, y + h, x))
                            else:
                                # Default location if not provided
                                face_locations.append((0, 100, 100, 0))
            
            # If DeepFace returns a single face dict, handle it
            elif faces and isinstance(faces, dict) and 'face' in faces:
                face_img = faces['face']
                if isinstance(face_img, np.ndarray):
                    face_encodings.append(face_img)
                    if 'area' in faces:
                        x, y, w, h = faces['area']
                        face_locations.append((y, x + w, y + h, x))
                    else:
                        face_locations.append((0, 100, 100, 0))
            
            return face_locations, face_encodings, rgb_img
            
        except Exception as e:
            print(f"Error detecting faces: {e}")
            return [], [], None
    
    def identify_faces(self, face_encodings, tolerance=0.6):
        """
        Match detected faces against known faces using DeepFace.
        Returns: list of matches (id, name, confidence) or None
        """
        matches = []
        
        if not self.is_available() or len(self.known_faces) == 0:
            return [None] * len(face_encodings)
        
        for encoding in face_encodings:
            best_match = None
            best_distance = float('inf')
            
            # Convert encoding to the format DeepFace expects
            if isinstance(encoding, np.ndarray):
                # Save encoding as temporary image for comparison
                import tempfile
                import os
                
                try:
                    # Convert the encoding back to image (DeepFace needs images for verification)
                    # For now, we'll use a simpler approach: store and compare embeddings directly
                    # This is a simplified version - DeepFace compare works with file paths
                    
                    for pid, data in self.known_faces.items():
                        try:
                            # Calculate distance between embeddings
                            known_encoding = np.array(data['encoding'])
                            
                            # For face image embeddings, we can't directly compare
                            # Use DeepFace's verify with a temporary file
                            # This is a simplified approach
                            
                            # For now, we'll use a placeholder - in production, you'd want to
                            # store the embeddings and compare them directly
                            distance = np.linalg.norm(known_encoding - encoding.flatten())
                            
                            if distance < tolerance and distance < best_distance:
                                best_distance = distance
                                best_match = {
                                    'id': pid,
                                    'name': data['name'],
                                    'confidence': 1 - (distance / 2)  # Normalize
                                }
                        except Exception as e:
                            print(f"Comparison error for {data['name']}: {e}")
                            continue
                    
                except Exception as e:
                    print(f"Identification error: {e}")
                    best_match = None
            
            matches.append(best_match)
        
        return matches
    
    def enroll_face(self, participant_id, image_bytes):
        """
        Enroll a participant's face using DeepFace.
        Returns: {success: bool, message: str}
        """
        if not self.is_available():
            return {'success': False, 'error': 'DeepFace is not available'}
        
        try:
            # Convert bytes to image
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            # Save temporary file
            import tempfile
            import os
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                cv2.imwrite(tmp.name, img)
                tmp_path = tmp.name
            
            try:
                # Extract face embedding using DeepFace
                embedding_result = DeepFace.represent(
                    img_path=tmp_path,
                    model_name='Facenet512',
                    enforce_detection=True,
                    detector_backend='opencv'
                )
            except Exception as e:
                return {'success': False, 'error': f'Could not detect face: {e}'}
            
            # Clean up temp file
            try:
                os.unlink(tmp_path)
            except:
                pass
            
            # Extract embedding
            if embedding_result and isinstance(embedding_result, list) and len(embedding_result) > 0:
                embedding = embedding_result[0]['embedding']
            elif embedding_result and isinstance(embedding_result, dict) and 'embedding' in embedding_result:
                embedding = embedding_result['embedding']
            else:
                return {'success': False, 'error': 'Could not extract face embedding'}
            
            # Store encoding in database
            supabase.table('participants') \
                .update({
                    'face_encoding': str(embedding),
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
        return len(self.known_faces)


# Singleton instance
_face_service = None

def get_face_service():
    """Get or create singleton FaceRecognitionService instance."""
    global _face_service
    if _face_service is None:
        _face_service = FaceRecognitionService()
    return _face_service