import cv2
import face_recognition
import numpy as np
from PIL import Image
import requests
import io

# Download a sample face image (Lena is a classic test image)
url = "https://raw.githubusercontent.com/opencv/opencv/master/samples/data/lena.jpg"
response = requests.get(url)
img_array = np.asarray(bytearray(response.content), dtype=np.uint8)
img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

# Try face detection
face_locations = face_recognition.face_locations(rgb_img)
face_encodings = face_recognition.face_encodings(rgb_img, face_locations)

print(f"Found {len(face_locations)} face(s) in Lena image")
print(f"Face locations: {face_locations}")

if face_locations:
    print("✅ Face detection is working!")
else:
    print("❌ Face detection failed on a known good image")