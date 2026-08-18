import face_recognition
import cv2
import numpy as np
from PIL import Image
import os

# Ask for image path
image_path = input("Enter the path to your image: ")

# Check if file exists
if not os.path.exists(image_path):
    print(f"❌ File not found: {image_path}")
    exit()

# Load the image
print(f"📷 Loading: {image_path}")
image = face_recognition.load_image_file(image_path)

# Try different detection models
print("🔍 Trying HOG model...")
face_locations_hog = face_recognition.face_locations(image, model='hog')
print(f"   HOG found {len(face_locations_hog)} face(s)")

if not face_locations_hog:
    print("🔍 Trying CNN model (slower but more accurate)...")
    face_locations_cnn = face_recognition.face_locations(image, model='cnn')
    print(f"   CNN found {len(face_locations_cnn)} face(s)")

print("\n📸 Tips for better results:")
print("   - Use a front-facing photo")
print("   - Good lighting (not too dark, not too bright)")
print("   - Face should be clearly visible")
print("   - At least 100x100 pixels")
print("   - No glasses or hats if possible")