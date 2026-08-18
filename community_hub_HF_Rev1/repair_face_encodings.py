# repair_face_encodings.py
"""
ONE-TIME REPAIR SCRIPT — fixes face encodings broken by the DeepFace enrollment bug.

WHAT IT DOES:
    For every resident marked face_enrolled=True who has a face_photo_url,
    it downloads the stored photo from Supabase, recomputes the encoding with
    face_recognition (dlib) — the SAME library used at check-in — and writes
    the corrected encoding back to the participants table.

HOW TO RUN (on your local PC, from the project root folder — where config.py is):
    python repair_face_encodings.py

REQUIREMENTS (same as your app):
    pip install face_recognition opencv-python-headless pillow requests numpy

It does NOT touch photos, names, or any other column. Only face_encoding is rewritten.
"""

import io
import json

import numpy as np
import requests
from PIL import Image

import face_recognition

from config import supabase, DB_CONNECTED  # uses your existing project config


def compute_dlib_encoding(image_bytes: bytes):
    """Return a 128-d dlib encoding (as list) from image bytes, or None."""
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    image_np = np.array(image)

    locations = face_recognition.face_locations(image_np, model="hog")
    if not locations:
        # Retry with upsampling for smaller / lower-res faces
        locations = face_recognition.face_locations(
            image_np, number_of_times_to_upsample=2, model="hog"
        )
    if not locations:
        return None, "no face detected in stored photo"

    encodings = face_recognition.face_encodings(image_np, locations)
    if not encodings:
        return None, "face found but encoding failed"
    return encodings[0].tolist(), None


def main():
    if not DB_CONNECTED:
        print("❌ Database not connected. Check config.py / your .env / secrets.")
        return

    print("=" * 60)
    print("FACE ENCODING REPAIR TOOL")
    print("=" * 60)

    # Pull every enrolled resident
    result = (
        supabase.table("participants")
        .select("id, name, face_encoding, face_photo_url")
        .eq("active", True)
        .eq("face_enrolled", True)
        .execute()
    )
    rows = result.data or []
    print(f"Found {len(rows)} enrolled resident(s).\n")

    fixed, skipped, failed = 0, 0, 0

    for p in rows:
        name = p.get("name", "?")
        pid = p.get("id")
        url = p.get("face_photo_url")
        enc = p.get("face_encoding")

        # Quick check: is the current encoding even a valid 128-d dlib vector?
        needs_fix = True
        if enc:
            try:
                arr = np.array(json.loads(enc), dtype=np.float64)
                if arr.shape == (128,):
                    # Right shape — but it could STILL be a 128-d FaceNet vector.
                    # We can't tell from shape alone, so we recompute anyway to be safe.
                    pass
            except Exception:
                pass  # unparseable -> definitely needs fix

        if not url:
            print(f"⚠️  {name}: no face_photo_url — cannot auto-repair.")
            print(f"    → Re-enroll manually in the app (Manage → Face Enrollment).")
            skipped += 1
            continue

        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
        except Exception as e:
            print(f"❌ {name}: could not download photo ({e})")
            failed += 1
            continue

        encoding_list, err = compute_dlib_encoding(resp.content)
        if encoding_list is None:
            print(f"❌ {name}: {err}. Re-enroll manually with a clearer photo.")
            failed += 1
            continue

        try:
            supabase.table("participants").update(
                {"face_encoding": json.dumps(encoding_list)}
            ).eq("id", pid).execute()
            print(f"✅ {name}: encoding repaired (128-d dlib).")
            fixed += 1
        except Exception as e:
            print(f"❌ {name}: database update failed ({e})")
            failed += 1

    print("\n" + "=" * 60)
    print(f"DONE — Repaired: {fixed} | Needs manual re-enroll: {skipped} | Failed: {failed}")
    print("=" * 60)
    if fixed > 0:
        print("\nNext step: restart your Streamlit app (or use the reload button)")
        print("so the repaired encodings load into memory, then test a group photo.")


if __name__ == "__main__":
    main()
