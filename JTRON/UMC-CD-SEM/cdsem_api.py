#!/usr/bin/env python
# coding: utf-8
"""
CD-SEM Predict API  (RPA -> image recognition)

POST /predict   multipart/form-data
                  file       (required) full-screen snapshot (png/jpg)
                  timestamp  (optional) yyyymmdd_HHMMss, used in the saved image's name; defaults to the server clock
    Finds the Template object in the snapshot (auto-crop, magnification OCR, t1 -> m1 matching) and returns the
    point on the SEM image that corresponds to the middle of the white rectangle in the Template Monitor.

    Single-line JSON, always with the three fields found / x / y; origin (0,0) is the top-left of the uploaded
    snapshot, so (x, y) can be clicked directly:
        found    {"found":true,"x":1250,"y":680}
        not found {"found":false,"x":-1,"y":-1}
    Any failure (no Template window, anchor not found, poor match, unreadable image, internal error) is
    reported as not found; the reason is logged and sent in the X-Reason response header.

    Every call saves the uploaded snapshot as Image_Predicted_{yyyymmdd_HHMMss}.jpg, with a red cross and circle
    at the returned (x, y) when the target was found (a miss is saved unmarked). The file name is also
    returned in the X-Image response header.

GET /health     {"status":"ok"}

Download the saved pictures (read only):
GET /                        web page: newest images first, thumbnails, Download links, "Download all (zip)"
GET /images                  JSON list  (optional ?date=yyyymmdd  ?limit=N)
GET /images/{name}           show the image in the browser;  add ?download=true to save it as a file
GET /images.zip              zip of all saved images  (optional ?date=yyyymmdd for one day)

Run (from this folder, one worker only):
    uvicorn cdsem_api:app --host 0.0.0.0 --port 8000
    # or:  python cdsem_api.py

Environment variables (all optional):
    CDSEM_DATA_DIR   folder that contains template/ (align_hold.png, align_mag.png, cursor.png)
                     default: the dataset folder cdsem-crop.py resolves
    CDSEM_IMAGE_DIR  where the Image_Predicted_*.jpg files are saved (default: ./predicted)
    TESSERACT_CMD    full path of the tesseract executable, if it is not on PATH
    HOST / PORT      used by `python cdsem_api.py` (default 0.0.0.0 / 8000)

Requirements: everything cdsem-crop.py needs, plus  fastapi uvicorn python-multipart
"""
import importlib.util
import io
import json
import logging
import os
import re
import sys
import zipfile
import threading
import time
from datetime import datetime

os.environ.setdefault("MPLBACKEND", "Agg")      # cdsem-crop.py imports pyplot; never open a window

from PIL import Image, ImageDraw
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response

HERE = os.path.dirname(os.path.abspath(__file__))
log = logging.getLogger("cdsem_api")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def _load_core():
    """Import cdsem-crop.py (the file name has a hyphen, so it can't be imported normally)."""
    argv, sys.argv = sys.argv, sys.argv[:1]     # the script reads sys.argv[1] as its dataset folder
    try:
        spec = importlib.util.spec_from_file_location("cdsem_crop", os.path.join(HERE, "cdsem-crop.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        sys.argv = argv
    return mod


core = _load_core()

if os.environ.get("TESSERACT_CMD"):
    core.pytesseract.pytesseract.tesseract_cmd = os.environ["TESSERACT_CMD"]

DATA_DIR = os.path.abspath(os.environ.get("CDSEM_DATA_DIR", core.input_base))
IMAGE_DIR = os.path.abspath(os.environ.get("CDSEM_IMAGE_DIR", os.path.join(HERE, "predicted")))
_STAMP_RE = re.compile(r"^\d{8}_\d{6}$")                  # yyyymmdd_HHMMss
HOLD_BGR, MAG_BGR = core.load_anchors(DATA_DIR)          # fails fast if the template images are missing
CURSOR_RGBA = core.load_cursor(DATA_DIR)
_LOCK = threading.Lock()                                  # OCR / OpenCV pipeline runs one snapshot at a time
log.info("Template folder: %s", DATA_DIR)


def predict(snapshot: Image.Image):
    """
    Run the recognition on one full-screen snapshot.
    Returns (found, x, y, info) with x, y in the snapshot's own pixel coordinates (-1, -1 when not found).
    """
    orig_w, orig_h = snapshot.size
    ref_w, ref_h = core.REF_SIZE

    # Same preparation as process_image(): rescale to the calibration size, remove the mouse cursor
    scene = snapshot if snapshot.size == core.REF_SIZE else snapshot.resize(core.REF_SIZE, Image.LANCZOS)
    scene = core.preprocess_full(scene, CURSOR_RGBA)

    # Auto-crop and magnification (these raise RuntimeError if an anchor is not on screen)
    mag = core.ocr_magnification(scene, MAG_BGR)
    mag_x = core._mag_to_x(mag)
    high_mag = mag_x >= 20_000
    t1 = core.crop_t1(scene, HOLD_BGR, high_mag=high_mag)
    m1 = core.crop_m1(scene, MAG_BGR)
    mx, my, _, _ = core.template_match(core.pil_to_bgr(scene), MAG_BGR)
    m1_left, m1_top = max(0, mx + core.M1_L), max(0, my + core.M1_T)      # where m1 starts in the scene

    info = {"mag": mag}

    # Coarse then fine match of t1 on m1
    _, _, coarse, _, _, t1_local, t1_px, t1_py, _, _, _ = core.find_t1_in_m1(t1, m1, small_thumb=high_mag)
    info["coarse"] = round(float(coarse), 4)
    if coarse == 0.0:
        info["reason"] = "no coarse match"
        return False, -1, -1, info
    _, angle, fine, fine_x, fine_y = core.overlay_t1_on_m1(
        t1, m1, t1_local, (t1_px, t1_py), angle_range=2.5 if high_mag else 5.0,
        angle_step=0.5 if high_mag else 1.0, polarity_invariant=False, edge_match=high_mag
    )
    info["fine"] = round(float(fine), 4)

    # Middle of the white rectangle in t1 -> corresponding point on m1
    rect = core.find_t1_rect_center(t1)
    pt = core.t1_point_to_m1(t1, t1_local, m1, fine_x, fine_y, angle, (rect["cx"], rect["cy"]), coarse, fine)

    # found / not found follows the matching result (determine_match) only
    if core.determine_match(coarse, fine, mag_x) != "match":
        info["reason"] = "no match"
        return False, -1, -1, info

    # m1 pixel -> scene pixel -> original snapshot pixel (undo the rescale)
    x = (m1_left + pt["cx"]) * orig_w / ref_w
    y = (m1_top + pt["cy"]) * orig_h / ref_h
    x, y = int(round(x)), int(round(y))
    if not (0 <= x < orig_w and 0 <= y < orig_h):          # safety net: never return a point off the screen
        info["reason"] = "point outside screen"
        return False, -1, -1, info
    return True, x, y, info


def _save_predicted(snapshot: Image.Image, found: bool, x: int, y: int, timestamp):
    """
    Keep the judged snapshot for troubleshooting as Image_Predicted_{yyyymmdd_HHMMss}.jpg in IMAGE_DIR.
    A found target is marked with a red cross and circle at (x, y); a miss is saved unmarked.
    The timestamp comes from the caller (so it matches the caller's own log) or, if missing/invalid, from
    the server clock. If the name already exists, _2, _3 ... is appended. Never raises.
    Returns the file name, or "" if the image could not be saved.
    """
    try:
        stamp = timestamp if timestamp and _STAMP_RE.match(timestamp) else datetime.now().strftime("%Y%m%d_%H%M%S")
        img = snapshot.copy()
        if found:
            d = ImageDraw.Draw(img)
            r = max(20, min(img.size) // 40)
            d.line((x - r, y, x + r, y), fill=(255, 0, 0), width=4)
            d.line((x, y - r, x, y + r), fill=(255, 0, 0), width=4)
            d.ellipse((x - r, y - r, x + r, y + r), outline=(255, 0, 0), width=2)
        os.makedirs(IMAGE_DIR, exist_ok=True)
        name, n = f"Image_Predicted_{stamp}.jpg", 1
        while os.path.exists(os.path.join(IMAGE_DIR, name)):
            n += 1
            name = f"Image_Predicted_{stamp}_{n}.jpg"
        img.save(os.path.join(IMAGE_DIR, name), quality=95)
        return name
    except Exception as e:
        log.warning("could not save predicted image: %s", e)
        return ""


def _reply(found: bool, x: int, y: int, reason: str = "", image_name: str = "") -> Response:
    """Single-line JSON with exactly found (bool), x (int), y (int). Extra info goes in headers only."""
    body = json.dumps({"found": bool(found), "x": int(x), "y": int(y)}, separators=(",", ":"))
    headers = {}
    if reason:
        headers["X-Reason"] = reason.encode("ascii", "replace").decode("ascii")
    if image_name:
        headers["X-Image"] = image_name
    return Response(content=body, media_type="application/json", headers=headers or None)


app = FastAPI(title="CD-SEM Predict API")


@app.get("/health")
def health():
    return {"status": "ok"}


_NAME_RE = re.compile(r"^Image_Predicted_\d{8}_\d{6}(_\d+)?\.jpg$")   # the only names that can be listed / downloaded


def _saved_images(date=None):
    """Saved pictures as (name, size_bytes, mtime), newest first; optionally only those of one day (yyyymmdd)."""
    if not os.path.isdir(IMAGE_DIR):
        return []
    files = []
    for name in os.listdir(IMAGE_DIR):
        if _NAME_RE.match(name) and (not date or name.startswith(f"Image_Predicted_{date}_")):
            st = os.stat(os.path.join(IMAGE_DIR, name))
            files.append((name, st.st_size, st.st_mtime))
    return sorted(files, key=lambda f: f[2], reverse=True)


@app.get("/images")
def list_images(date: str = Query(None, pattern=r"^\d{8}$"), limit: int = Query(200, ge=1, le=5000)):
    files = _saved_images(date)
    return {"count": len(files), "images": [
        {"name": n, "size": sz, "modified": datetime.fromtimestamp(mt).isoformat(timespec="seconds"), "url": f"/images/{n}"}
        for n, sz, mt in files[:limit]]}


@app.get("/images/{name}")
def get_image(name: str, download: bool = False):
    path = os.path.join(IMAGE_DIR, name)
    if not _NAME_RE.match(name) or not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="image not found")
    return FileResponse(path, media_type="image/jpeg", filename=name if download else None)


@app.get("/images.zip")
def download_zip(date: str = Query(None, pattern=r"^\d{8}$")):
    files = _saved_images(date)
    if not files:
        raise HTTPException(status_code=404, detail="no images")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:           # jpg is already compressed
        for name, _, _ in files:
            z.write(os.path.join(IMAGE_DIR, name), name)
    zip_name = f"Image_Predicted_{date or 'all'}.zip"
    return Response(content=buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{zip_name}"'})


@app.get("/", response_class=HTMLResponse)
def index(date: str = Query(None, pattern=r"^\d{8}$"), limit: int = Query(200, ge=1, le=5000)):
    files = _saved_images(date)
    rows = "".join(
        f'<tr><td><a href="/images/{n}"><img src="/images/{n}" height="60" loading="lazy"></a></td>'
        f'<td>{n}</td><td>{datetime.fromtimestamp(mt).strftime("%Y-%m-%d %H:%M:%S")}</td><td>{sz // 1024} KB</td>'
        f'<td><a href="/images/{n}?download=true">Download</a></td></tr>'
        for n, sz, mt in files[:limit])
    zip_link = f'/images.zip?date={date}' if date else '/images.zip'
    shown = f"showing {min(len(files), limit)} of {len(files)}" if files else "no images yet"
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>CD-SEM predicted images</title>
<style>body{{font-family:sans-serif;margin:24px}}table{{border-collapse:collapse}}td,th{{border-bottom:1px solid #ddd;padding:6px 12px;text-align:left}}</style></head>
<body><h2>CD-SEM predicted images</h2>
<form method="get">Date (yyyymmdd): <input name="date" value="{date or ''}" pattern="\\d{{8}}" size="10">
<button>Filter</button> <a href="/">clear</a> &nbsp; <a href="{zip_link}">Download all{' for this date' if date else ''} (zip)</a>
&nbsp; <small>{shown}</small></form><br>
<table><tr><th>Preview</th><th>File</th><th>Saved at</th><th>Size</th><th></th></tr>{rows}</table></body></html>"""


@app.post("/predict")
def predict_endpoint(file: UploadFile = File(...), timestamp: str = Form(None)):
    t0 = time.perf_counter()
    try:
        snapshot = Image.open(io.BytesIO(file.file.read())).convert("RGB")
    except Exception as e:
        log.warning("predict: unreadable image (%s)", e)
        return _reply(False, -1, -1, "unreadable image")

    try:
        with _LOCK:
            found, x, y, info = predict(snapshot)
    except Exception as e:                                  # e.g. anchor not on screen = no Template window
        found, x, y, info = False, -1, -1, {"reason": str(e)}

    reason = "" if found else info.get("reason", "not found")
    log.info("predict: found=%s x=%s y=%s %s (%.2fs)", found, x, y, info, time.perf_counter() - t0)

    image_name = _save_predicted(snapshot, found, x, y, timestamp)
    return _reply(found, x, y, reason, image_name)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=os.environ.get("HOST", "0.0.0.0"), port=int(os.environ.get("PORT", "8000")))
