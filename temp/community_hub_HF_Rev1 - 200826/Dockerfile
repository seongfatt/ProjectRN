# Dockerfile for Woodlands Zone 6 Community Hub
# Based on official Python slim image for small footprint
FROM python:3.11-slim

# ─── Environment Variables ──────────────────────────────
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    STREAMLIT_SERVER_PORT=7860 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# ─── Create Non-Root User ──────────────────────────────
# Hugging Face Spaces runs containers as uid 1000 [citation:3][citation:4]
RUN useradd -m -u 1000 user

# ─── Set Working Directory ──────────────────────────────
WORKDIR /home/user/app

# ─── Install System Dependencies ─────────────────────────
# Required for OpenCV, face_recognition, and other packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    gcc \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgtk2.0-dev \
    freeglut3-dev \
    && rm -rf /var/lib/apt/lists/*

# ─── Copy Requirements First (Better Caching) ──────────
COPY --chown=user requirements.txt ./

# ─── Install Python Dependencies ─────────────────────────
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ─── Copy Application Code ──────────────────────────────
COPY --chown=user . .

# ─── Create .streamlit Directory for Config ─────────────
RUN mkdir -p /home/user/.streamlit && \
    echo '[browser]\nserverAddress = "localhost"\n[client]\nshowErrorDetails = true\n[logger]\nlevel = "info"' > /home/user/.streamlit/config.toml

# ─── Expose Port ──────────────────────────────────────────
# Hugging Face expects port 7860 [citation:2][citation:3]
EXPOSE 7860

# ─── Health Check ────────────────────────────────────────
HEALTHCHECK CMD curl --fail http://localhost:7860/_stcore/health || exit 1

# ─── Run Streamlit App ───────────────────────────────────
CMD ["streamlit", "run", "app.py", "--server.port=7860", "--server.address=0.0.0.0"]