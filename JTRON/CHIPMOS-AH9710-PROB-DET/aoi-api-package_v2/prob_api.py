"""AOI-API v8.0 (dual-ROI, per-ROI OR) — AH9710 Contact Monitor.

Differences vs. v7.5:
  1. Input images are resized to 1280 × 1024 at ingest (from config).
  2. Two ROIs: the LEFT ROI from calibration + its horizontal mirror on
     the RIGHT. Five features are computed on EACH crop.
  3. The logistic classifier is run INDEPENDENTLY on left and right crops.
     Final status = `contact` iff EITHER side says contact (OR aggregation).
     (Empirically on the 24-image labeled set, OR hits 95.8% vs AND's 83.3%
     because the LEFT ROI is the primary signal and the RIGHT mirror lags
     on several real-contact frames.)
  4. Response includes `per_roi` with each side's own status / probability /
     features so the operator can see which side triggered.

File persistence (same shape as v7.5):
  every tick → <ts>.jpg (1280 × 1024 + yellow rectangles on BOTH ROIs)
               routed to ./local_output/<status>/
  contact    → additionally cropped_<ts>.jpg containing LEFT|RIGHT crops
               concatenated horizontally into one JPG

Response schema:
  {
    "status":              "contact" | "non_contact",   # OR aggregation
    "probability_contact": <max of per-ROI probs>,
    "aggregation":         "OR",
    "roi_image":           <url or null>,
    "fullframe_image":     <url>,
    "per_roi": {
      "left":  { "status": ..., "probability_contact": ..., "laplacian_score": ...,
                 "features": {lap_var, mean, std, edge_den, grad_mag} },
      "right": { same shape }
    }
  }
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


# ---------- Config loading ----------
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
for d in (CONTACT_DIR, NONCONTACT_DIR, LOG_DIR):
    os.makedirs(d, exist_ok=True)


# ---------- JSON Lines logger ----------
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


# ---------- FastAPI app ----------
@asynccontextmanager
async def lifespan(app_):
    log_event("startup", version=app_.version, variant="dual-roi-or",
              input_resize={"width": TARGET_W, "height": TARGET_H},
              config_path=os.path.abspath(CONFIG_PATH),
              paths={
                  "calibration_json": os.path.abspath(CALIBRATION_PATH),
                  "contact_dir": os.path.abspath(CONTACT_DIR),
                  "non_contact_dir": os.path.abspath(NONCONTACT_DIR),
                  "log_dir": os.path.abspath(LOG_DIR),
              })
    try:
        yield
    finally:
        log_event("shutdown", version=app_.version)


app = FastAPI(title="AOI Contact-Detection API (dual-ROI OR)",
              version="8.0", lifespan=lifespan)

app.mount("/local_output/contact",
          StaticFiles(directory=CONTACT_DIR), name="contact")
app.mount("/local_output/non-contact",
          StaticFiles(directory=NONCONTACT_DIR), name="non_contact")

ROI_OVERLAY_COLOR_BGR = (0, 255, 255)  # yellow in BGR
ROI_OVERLAY_THICKNESS = 3


# ---------- Feature pipeline ----------
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
        raise HTTPException(status_code=500,
            detail=f"calibration not found at {CALIBRATION_PATH}")
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


def mirror_roi_horizontal(rx1, ry1, rx2, ry2):
    """Mirror the ROI about the vertical centre line (x = 0.5)."""
    return (1.0 - rx2, ry1, 1.0 - rx1, ry2)


def roi_pixels(img_bgr, rx1, ry1, rx2, ry2):
    h, w = img_bgr.shape[:2]
    return int(w * rx1), int(h * ry1), int(w * rx2), int(h * ry2)


def crop_frame(img_bgr, rx1, ry1, rx2, ry2):
    x1, y1, x2, y2 = roi_pixels(img_bgr, rx1, ry1, rx2, ry2)
    return img_bgr[y1:y2, x1:x2]


def draw_rois_overlay(img_bgr, rois):
    out = img_bgr.copy()
    for rx1, ry1, rx2, ry2 in rois:
        x1, y1, x2, y2 = roi_pixels(img_bgr, rx1, ry1, rx2, ry2)
        cv2.rectangle(out, (x1, y1), (x2, y2),
                      ROI_OVERLAY_COLOR_BGR, ROI_OVERLAY_THICKNESS)
    return out


def resize_to_target(img_bgr):
    """Resize to configured TARGET_W × TARGET_H. Skips if already that size."""
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
        "variant": "dual-roi-or",
        "calibrated": calibrated,
    }


@app.get("/api/v1/config")
def config():
    model = load_calibration()
    left = {k: model[k] for k in ("rx1", "ry1", "rx2", "ry2")}
    rx1_r, ry1_r, rx2_r, ry2_r = mirror_roi_horizontal(
        left["rx1"], left["ry1"], left["rx2"], left["ry2"])
    right = {"rx1": rx1_r, "ry1": ry1_r, "rx2": rx2_r, "ry2": ry2_r}
    return {
        "variant": "dual-roi-or",
        "input_resize": {"width": TARGET_W, "height": TARGET_H},
        "reference_roi": left,                 # kept for monitor compatibility
        "reference_roi_left": left,
        "reference_roi_right": right,
        "aggregation": "OR",
        "model": model.get("model", "logistic"),
        "features": model.get("features", []),
        "decision_threshold": 0.5,
        "trained_on": {
            "n_contact": model.get("n_contact"),
            "n_non_contact": model.get("n_non_contact"),
            "resolution": model.get("input_resize"),
        },
    }


def _classify_roi(img_resized, roi, model):
    """Compute features, predict probability, produce a per-ROI summary."""
    crop = crop_frame(img_resized, *roi)
    feats = compute_features(crop)
    prob = predict_probability(feats, model)
    return {
        "status": "contact" if prob >= 0.5 else "non_contact",
        "probability_contact": round(prob, 4),
        "laplacian_score": round(feats["lap_var"], 2),
        "features": {k: round(v, 4) for k, v in feats.items()},
    }, crop


@app.post("/api/v1/predict")
async def predict(
    file: UploadFile = File(..., description="RCM 截圖（任意解析度；API 內部 resize）"),
):
    t0 = time.perf_counter()
    model = load_calibration()
    left_roi = (model["rx1"], model["ry1"], model["rx2"], model["ry2"])
    right_roi = mirror_roi_horizontal(*left_roi)

    contents = await file.read()
    img_raw = cv2.imdecode(np.frombuffer(contents, np.uint8), cv2.IMREAD_COLOR)
    if img_raw is None:
        log_event("predict_error", filename=file.filename, error="decode_failed")
        raise HTTPException(status_code=400, detail="無法解析上傳的影像")
    if img_raw.size == 0:
        log_event("predict_error", filename=file.filename, error="empty_image")
        raise HTTPException(status_code=400, detail="影像為空")

    img = resize_to_target(img_raw)

    left_summary, left_crop = _classify_roi(img, left_roi, model)
    right_summary, right_crop = _classify_roi(img, right_roi, model)
    if left_crop.size == 0 or right_crop.size == 0:
        log_event("predict_error", filename=file.filename, error="roi_invalid")
        raise HTTPException(status_code=500, detail="計算出的 ROI 範圍無效")

    # OR aggregation: contact iff EITHER per-ROI verdict says contact.
    either_contact = (left_summary["status"] == "contact" or right_summary["status"] == "contact")
    status = "contact" if either_contact else "non_contact"
    # For the overall probability report the STRONGER signal (the max),
    # since OR is driven by whichever side fires.
    overall_prob = max(left_summary["probability_contact"],
                       right_summary["probability_contact"])

    # Persist: always save the fullframe with both yellow boxes.
    now = datetime.now()
    stamp = now.strftime("%Y%m%d_%H%M%S_") + f"{now.microsecond // 1000:03d}"
    full_name = f"{stamp}.jpg"
    out_dir = CONTACT_DIR if either_contact else NONCONTACT_DIR
    url_prefix = "/local_output/contact" if either_contact else "/local_output/non-contact"

    cv2.imwrite(os.path.join(out_dir, full_name),
                draw_rois_overlay(img, [left_roi, right_roi]))
    fullframe_url = f"{url_prefix}/{full_name}"

    # On overall contact, also save the concatenated crop (left | right).
    roi_url = None
    if either_contact:
        h = max(left_crop.shape[0], right_crop.shape[0])
        l_pad = cv2.copyMakeBorder(left_crop, 0, h - left_crop.shape[0], 0, 0,
                                   cv2.BORDER_CONSTANT, value=(0, 0, 0))
        r_pad = cv2.copyMakeBorder(right_crop, 0, h - right_crop.shape[0], 0, 0,
                                   cv2.BORDER_CONSTANT, value=(0, 0, 0))
        combined = np.hstack([l_pad, r_pad])
        crop_name = f"cropped_{stamp}.jpg"
        cv2.imwrite(os.path.join(CONTACT_DIR, crop_name), combined)
        roi_url = f"/local_output/contact/{crop_name}"

    response = {
        "status": status,                           # OR aggregation
        "aggregation": "OR",
        "probability_contact": round(overall_prob, 4),
        "roi_image": roi_url,                       # URL on overall contact; null otherwise
        "fullframe_image": fullframe_url,
        "per_roi": {
            "left": left_summary,
            "right": right_summary,
        },
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
