# services/face_service.py
import cv2
import numpy as np
import face_recognition
from PIL import Image
import io
from config import supabase

class FaceRecognitionService:
    # ... (full implementation from previous message)
    pass

_face_service = None

def get_face_service():
    global _face_service
    if _face_service is None:
        _face_service = FaceRecognitionService(supabase)
    return _face_service