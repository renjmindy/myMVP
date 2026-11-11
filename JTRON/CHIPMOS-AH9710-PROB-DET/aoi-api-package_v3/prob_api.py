"""AOI-API v9.0 (overlay-removal + central ROI) — AH9710 Contact Monitor.

Differences vs. v7.6:
  1. Input images resized to 1280 × 1024 (same as v7.6).
  2. BEFORE cropping, the AOI machine's native UI overlay is removed:
       - Blue / cyan rectangles (detected by `B - R > 25` with 2-px dilation)
       - White cross lines (detected by brightness > 180 + long run)
     Missing pixels are filled with cv2.inpaint (TELEA).
  3. The ROI is in the CENTRAL region of the cleaned frame
     (default (0.30, 0.35, 0.75, 0.80) — covers where the probe/pad action
     used to sit inside the native blue UI box).
  4. Calibration refit on 24 labeled images with overlay removal + central
     ROI at 1280 × 1024.

File persistence policy (same as v7.6):
  - Every tick → <ts>.jpg (the CLEANED 1280×1024 frame + yellow ROI box)
    routed to ./local_output/<status>/
  - Contact additionally → cropped_<ts>.jpg (the central ROI from the
    cleaned frame)
"""
import json
import logging
import math
import os
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler

import cv2
import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
import uvicorn


# ---------- Config ----------
CONFIG_PATH = os.environ.get("AOI_API_CONFIG", "./config/aoi_api.json")

DEFAULT_CONFIG = {
    "server": {"host": "0.0.0.0", "port": 8000},
    "paths": {
        "calibration_json": "./local_output/calibration.json",
        "contact_dir": "./local_output/contact",
        "non_contact_dir": "./local_output/non-contact",
        "log_dir": "./logs",
    },
    "logging": {
        "level": "INFO",
        "filename": "aoi_api.log",
        "rotation": "daily",
        "backup_count": 7,
    },
    "input_resize": {"width": 1280, "height": 1024},
    "overlay_removal": {
        "enabled": True,
        "blue_delta": 25,
        "cross_brightness": 180,
        "cross_min_run": 20,
        "inpaint_radius": 3,
    },
}


def _deep_merge(base, override):
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(path=CONFIG_PATH):
    if not os.path.exists(path):
        print(f"WARN: config {path} not found — using defaults", file=sys.stderr)
        return dict(DEFAULT_CONFIG)
    try:
        with open(path) as f:
            return _deep_merge(DEFAULT_CONFIG, json.load(f))
    except (OSError, ValueError) as e:
        print(f"WARN: cannot read config {path}: {e} — using defaults", file=sys.stderr)
        return dict(DEFAULT_CONFIG)


CFG = load_config()
CALIBRATION_PATH = CFG["paths"]["calibration_json"]
CONTACT_DIR = CFG["paths"]["contact_dir"]
NONCONTACT_DIR = CFG["paths"]["non_contact_dir"]
LOG_DIR = CFG["paths"]["log_dir"]
TARGET_W = int(CFG["input_resize"]["width"])
TARGET_H = int(CFG["input_resize"]["height"])
OV = CFG["overlay_removal"]
OV_ENABLED = bool(OV.get("enabled", True))
OV_BLUE_DELTA = int(OV.get("blue_delta", 25))
OV_CROSS_BRIGHT = int(OV.get("cross_brightness", 180))
OV_CROSS_RUN = int(OV.get("cross_min_run", 20))
OV_INPAINT_R = int(OV.get("inpaint_radius", 3))

for d in (CONTACT_DIR, NONCONTACT_DIR, LOG_DIR):
    os.makedirs(d, exist_ok=True)


# ---------- Logger ----------
class JsonLineFormatter(logging.Formatter):
    def format(self, record):
        payload = dict(record.msg) if isinstance(record.msg, dict) \
                  else {"message": record.getMessage()}
        out = {
            "ts": datetime.now().isoformat(timespec="milliseconds"),
            "level": record.levelname,
        }
        out.update(payload)
        return json.dumps(out, ensure_ascii=False, default=str)


def _build_logger():
    log_path = os.path.join(LOG_DIR, CFG["logging"]["filename"])
    handler = TimedRotatingFileHandler(
        log_path, when="midnight", interval=1,
        backupCount=int(CFG["logging"]["backup_count"]),
        encoding="utf-8", utc=False,
    )
    handler.suffix = "%Y-%m-%d"
    handler.setFormatter(JsonLineFormatter())
    lg = logging.getLogger("aoi_api")
    for h in list(lg.handlers):
        lg.removeHandler(h)
    lg.addHandler(handler)
    lg.setLevel(getattr(logging, str(CFG["logging"]["level"]).upper(), logging.INFO))
    lg.propagate = False
    return lg


logger = _build_logger()


def log_event(event, **fields):
    logger.info({"event": event, **fields})


# ---------- FastAPI ----------
@asynccontextmanager
async def lifespan(app_):
    log_event("startup", version=app_.version, variant="central-roi-overlay-removed",
              input_resize={"width": TARGET_W, "height": TARGET_H},
              overlay_removal={"enabled": OV_ENABLED, "blue_delta": OV_BLUE_DELTA,
                               "cross_brightness": OV_CROSS_BRIGHT,
                               "cross_min_run": OV_CROSS_RUN,
                               "inpaint_radius": OV_INPAINT_R},
              config_path=os.path.abspath(CONFIG_PATH),
              paths={k: os.path.abspath(v) for k, v in
                     {"calibration_json": CALIBRATION_PATH,
                      "contact_dir": CONTACT_DIR,
                      "non_contact_dir": NONCONTACT_DIR,
                      "log_dir": LOG_DIR}.items()})
    try:
        yield
    finally:
        log_event("shutdown", version=app_.version)


app = FastAPI(title="AOI Contact-Detection API (central-ROI, overlay-removed)",
              version="9.0", lifespan=lifespan)

app.mount("/local_output/contact",
          StaticFiles(directory=CONTACT_DIR), name="contact")
app.mount("/local_output/non-contact",
          StaticFiles(directory=NONCONTACT_DIR), name="non_contact")

ROI_OVERLAY_COLOR_BGR = (0, 255, 255)  # yellow
ROI_OVERLAY_THICKNESS = 3


# ---------- Overlay removal ----------
def _box1d(a, k, axis):
    pad = [(k // 2 + 1, k - k // 2 - 1) if i == axis else (0, 0) for i in range(a.ndim)]
    c = np.cumsum(np.pad(a, pad, mode="edge"), axis=axis, dtype=np.float32)
    hi = np.take(c, np.arange(k, c.shape[axis]), axis=axis)
    lo = np.take(c, np.arange(0, c.shape[axis] - k), axis=axis)
    return (hi - lo) / k


def _blue_mask(img_bgr, delta):
    """Detect non-gray pixels where blue >> red (catches blue + cyan/teal
    overlays). Dilated by 2 px for anti-aliased edges."""
    b = img_bgr[..., 0].astype(np.int32)
    r = img_bgr[..., 2].astype(np.int32)
    mask = (b - r) > delta
    for _ in range(2):
        mask = mask | np.roll(mask, 1, 0) | np.roll(mask, -1, 0) \
                   | np.roll(mask, 1, 1) | np.roll(mask, -1, 1)
    return mask


def _white_cross_mask(gray, brightness, run):
    """Detect long horizontal/vertical runs of bright pixels (the white
    cross drawn by the AOI machine's UI). Does not catch probe-tip
    stripes because those are dimmer."""
    bright = gray > brightness
    horiz = _box1d(bright.astype(np.float32), run, 1) > 0.9
    vert = _box1d(bright.astype(np.float32), run, 0) > 0.9
    mask = horiz | vert
    mask = mask | np.roll(mask, 1, 0) | np.roll(mask, -1, 0) \
                | np.roll(mask, 1, 1) | np.roll(mask, -1, 1)
    return mask


def remove_overlay(img_bgr):
    if not OV_ENABLED:
        return img_bgr
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    b = _blue_mask(img_bgr, OV_BLUE_DELTA)
    c = _white_cross_mask(gray, OV_CROSS_BRIGHT, OV_CROSS_RUN)
    combined = b | c
    if not combined.any():
        return img_bgr.copy()
    return cv2.inpaint(img_bgr, combined.astype(np.uint8) * 255,
                       OV_INPAINT_R, cv2.INPAINT_TELEA)


# ---------- Features / model ----------
def compute_features(roi_bgr):
    gray = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2GRAY)
    g = cv2.GaussianBlur(gray, (5, 5), 0)
    lap_var = float(cv2.Laplacian(g, cv2.CV_64F).var())
    mean = float(gray.mean())
    std = float(gray.std())
    edges = cv2.Canny(g, 50, 150)
    edge_den = float(edges.sum() / 255.0 / edges.size)
    gx = cv2.Sobel(g, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(g, cv2.CV_64F, 0, 1, ksize=3)
    grad_mag = float(np.sqrt(gx * gx + gy * gy).mean())
    return {"lap_var": lap_var, "mean": mean, "std": std,
            "edge_den": edge_den, "grad_mag": grad_mag}


def load_calibration():
    if not os.path.exists(CALIBRATION_PATH):
        raise HTTPException(status_code=500, detail=f"calibration not found at {CALIBRATION_PATH}")
    try:
        m = json.load(open(CALIBRATION_PATH))
    except (OSError, ValueError) as e:
        raise HTTPException(status_code=500, detail=f"Unreadable calibration: {e}")
    for k in ("features", "feature_means", "feature_stds", "weights", "intercept",
              "rx1", "ry1", "rx2", "ry2"):
        if k not in m:
            raise HTTPException(status_code=500,
                detail=f"calibration missing '{k}' — recalibrate.")
    return m


def predict_probability(feats, model):
    x = np.array([feats[n] for n in model["features"]], dtype=float)
    mu = np.array(model["feature_means"], dtype=float)
    sd = np.array(model["feature_stds"], dtype=float)
    sd = np.where(sd == 0, 1.0, sd)
    xn = (x - mu) / sd
    z = float(xn @ np.array(model["weights"], dtype=float) + model["intercept"])
    return 1.0 / (1.0 + math.exp(-z))


def roi_pixels(img_bgr, rx1, ry1, rx2, ry2):
    h, w = img_bgr.shape[:2]
    return int(w * rx1), int(h * ry1), int(w * rx2), int(h * ry2)


def crop_frame(img_bgr, rx1, ry1, rx2, ry2):
    x1, y1, x2, y2 = roi_pixels(img_bgr, rx1, ry1, rx2, ry2)
    return img_bgr[y1:y2, x1:x2]


def draw_roi_overlay(img_bgr, rx1, ry1, rx2, ry2):
    out = img_bgr.copy()
    x1, y1, x2, y2 = roi_pixels(img_bgr, rx1, ry1, rx2, ry2)
    cv2.rectangle(out, (x1, y1), (x2, y2),
                  ROI_OVERLAY_COLOR_BGR, ROI_OVERLAY_THICKNESS)
    return out


def resize_to_target(img_bgr):
    h, w = img_bgr.shape[:2]
    if (w, h) == (TARGET_W, TARGET_H):
        return img_bgr
    interp = cv2.INTER_AREA if (w > TARGET_W or h > TARGET_H) else cv2.INTER_CUBIC
    return cv2.resize(img_bgr, (TARGET_W, TARGET_H), interpolation=interp)


# ---------- Endpoints ----------
@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")


@app.get("/api/v1/health")
def health():
    calibrated = False
    try:
        load_calibration()
        calibrated = True
    except HTTPException:
        pass
    return {
        "status": "ok",
        "service": "aoi-api",
        "version": app.version,
        "variant": "central-roi-overlay-removed",
        "calibrated": calibrated,
    }


@app.get("/api/v1/config")
def config():
    model = load_calibration()
    return {
        "variant": "central-roi-overlay-removed",
        "input_resize": {"width": TARGET_W, "height": TARGET_H},
        "overlay_removal": {
            "enabled": OV_ENABLED,
            "blue_delta": OV_BLUE_DELTA,
            "cross_brightness": OV_CROSS_BRIGHT,
            "cross_min_run": OV_CROSS_RUN,
            "inpaint_radius": OV_INPAINT_R,
        },
        "reference_roi": {k: model[k] for k in ("rx1", "ry1", "rx2", "ry2")},
        "model": model.get("model", "logistic"),
        "features": model.get("features", []),
        "decision_threshold": 0.5,
        "trained_on": {
            "n_contact": model.get("n_contact"),
            "n_non_contact": model.get("n_non_contact"),
            "resolution": model.get("input_resize"),
            "overlay_removal": model.get("overlay_removal"),
        },
    }


@app.post("/api/v1/predict")
async def predict(
    file: UploadFile = File(..., description="RCM 截圖（任意解析度；API 內部 resize + 去除 overlay）"),
):
    t0 = time.perf_counter()
    model = load_calibration()
    rx1, ry1, rx2, ry2 = model["rx1"], model["ry1"], model["rx2"], model["ry2"]

    contents = await file.read()
    img_raw = cv2.imdecode(np.frombuffer(contents, np.uint8), cv2.IMREAD_COLOR)
    if img_raw is None:
        log_event("predict_error", filename=file.filename, error="decode_failed")
        raise HTTPException(status_code=400, detail="無法解析上傳的影像")
    if img_raw.size == 0:
        log_event("predict_error", filename=file.filename, error="empty_image")
        raise HTTPException(status_code=400, detail="影像為空")

    # 1. Resize to target
    img = resize_to_target(img_raw)
    # 2. Remove AOI UI overlay (blue/cyan boxes + white cross)
    img_cleaned = remove_overlay(img)
    # 3. Crop central ROI from the cleaned frame
    crop = crop_frame(img_cleaned, rx1, ry1, rx2, ry2)
    if crop.size == 0:
        log_event("predict_error", filename=file.filename, error="roi_invalid")
        raise HTTPException(status_code=500, detail="計算出的 ROI 範圍無效")

    # 4. Compute features + classify
    feats = compute_features(crop)
    prob = predict_probability(feats, model)
    is_contact = prob >= 0.5
    status = "contact" if is_contact else "non_contact"

    # 5. Persist: always save the cleaned fullframe (with yellow ROI).
    now = datetime.now()
    stamp = now.strftime("%Y%m%d_%H%M%S_") + f"{now.microsecond // 1000:03d}"
    full_name = f"{stamp}.jpg"
    out_dir = CONTACT_DIR if is_contact else NONCONTACT_DIR
    url_prefix = "/local_output/contact" if is_contact else "/local_output/non-contact"

    cv2.imwrite(os.path.join(out_dir, full_name),
                draw_roi_overlay(img_cleaned, rx1, ry1, rx2, ry2))
    fullframe_url = f"{url_prefix}/{full_name}"

    roi_url = None
    if is_contact:
        crop_name = f"cropped_{stamp}.jpg"
        cv2.imwrite(os.path.join(CONTACT_DIR, crop_name), crop)
        roi_url = f"/local_output/contact/{crop_name}"

    response = {
        "status": status,
        "roi_image": roi_url,
        "fullframe_image": fullframe_url,
        "laplacian_score": round(feats["lap_var"], 2),
        "probability_contact": round(prob, 4),
        "features": {k: round(v, 4) for k, v in feats.items()},
    }

    log_event(
        "predict",
        filename=file.filename,
        **response,
        latency_ms=round((time.perf_counter() - t0) * 1000.0, 2),
    )

    return response


if __name__ == "__main__":
    uvicorn.run(
        "prob_api:app",
        host=CFG["server"]["host"],
        port=int(CFG["server"]["port"]),
        reload=False,
    )
