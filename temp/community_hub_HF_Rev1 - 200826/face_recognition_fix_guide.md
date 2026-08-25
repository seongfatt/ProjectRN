# Face Recognition Fix — Recovery Guide

## What went wrong (root cause)

Your app was **not** broken by a missing file or installation. It was broken by a
**model mismatch** between the two halves of your face system:

- **Enrollment** (`pages/residents.py`) was saving face encodings made by
  **DeepFace (Facenet)** — introduced by the `"THE MAGIC FIX"` edit that bypassed
  the OpenCV XML error.
- **Check-in recognition** (`services/face_service.py`) compares faces using
  **face_recognition (dlib)**.

Both libraries output 128 numbers, so nothing crashes — but the numbers come from
completely different neural networks. A dlib-vs-Facenet distance is ~1.4, far above
your 0.6 tolerance, so **every face shows "Unknown"** with no error.

This is why:
- It worked before the DeepFace edit, and broke right after.
- Supabase photo uploads kept working (photos save fine — the *encoding* was wrong).
- Streamlit Cloud and local both fail (the bad data lives in the database, so it
  follows you everywhere).

A second bug: enrolling a face never refreshed the in-memory cache, so even a
correctly-enrolled face wasn't recognised until the app restarted.

## What I fixed

| File | Change |
|---|---|
| `residents.py` | Enrollment now uses **face_recognition (dlib) only** — DeepFace removed entirely (which also removes the original OpenCV XML problem). Handles RGBA/grayscale photos, retries detection with upsampling, rejects multi-face photos, and **reloads the face cache immediately** after enrollment. |
| `face_service.py` | New public `reload()` method; skips wrong-shaped encodings with a clear warning instead of poisoning matching; **prints the best-match distance** to the console for every detected face. |
| `repair_face_encodings.py` | One-time repair script: downloads every enrolled resident's stored photo from Supabase and recomputes a correct dlib encoding in place. |

## Recovery steps (do these in order)

1. **Replace the two files in your project:**
   - `pages/residents.py` ← new `residents.py`
   - `services/face_service.py` ← new `face_service.py`

2. **Repair the existing enrollments** (on your local PC, from the project root
   where `config.py` lives):

   ```
   python repair_face_encodings.py
   ```

   It prints one line per resident: ✅ repaired, ⚠️ no photo (re-enroll manually),
   or ❌ failed (re-enroll manually with a clearer photo).

3. **Restart your Streamlit app** so the repaired encodings load into memory.

4. **Test** with a group photo on the Face Check-In page. You should see green
   boxes again.

5. **Deploy the same two fixed files to Streamlit Cloud** (push to GitHub).
   No `deepface` or `tensorflow` needed in `requirements.txt` anymore — you can
   remove them, which also makes the Streamlit build much lighter and faster.

## How to verify it's healthy (new debug output)

After the fix, every detected face prints a line to the console/terminal:

```
Best match: TAN AH KOW | distance=0.4821 | tolerance=0.6
```

Reading the distance tells you everything:

- **< 0.6** → matched (green box). Typical same-person range: 0.35–0.55.
- **0.6–0.7** → right person, borderline — re-enroll with a better-lit,
  forward-facing photo (don't loosen the tolerance beyond ~0.65 or you'll get
  false matches).
- **> 1.0 everywhere** → wrong vector space again (means a DeepFace-enrolled row
  is still in the DB — run the repair script or re-enroll that resident).

## One thing to know going forward

Your check-in page currently only reaches the recognition code when the enrolled
count is > 0, and the debug line `Faces loaded in memory` near the top tells you
the cache is populated. If that number is ever 0 while residents show "enrolled",
press reload via a fresh app start — the cache loads once at startup.

If you'd like, I can also add a small "🔄 Reload Face Cache" button on the
Face Check-In page so admins never need to restart the app.
