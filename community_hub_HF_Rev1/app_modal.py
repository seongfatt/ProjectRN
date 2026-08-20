# app_modal.py
import modal
import os

# Define the image that your app will run on
image = modal.Image.debian_slim().pip_install(
    "streamlit",
    "pandas",
    "numpy",
    "supabase",
    "pillow",
    "requests",
    "face_recognition",
    "opencv-python",
    "deepface",
    "tensorflow"
)

app = modal.App("woodlands-community-hub")

@app.function(
    image=image,
    gpu="T4",  
    timeout=600,
)
@modal.concurrent(max_inputs=100)  # <-- Corrected line
@modal.wsgi_app()
def streamlit_app():
    import sys
    sys.path.append("/root")
    import app  
    return app.app