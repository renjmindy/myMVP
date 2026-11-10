"""AOI-API for the AH9710 Contact Monitor system — v7.5.

Config-driven: all filesystem paths, server port, and log settings come from
./config/aoi_api.json (override via the AOI_API_CONFIG env var). If the file
is missing or unreadable the service falls back to built-in defaults.

File persistence policy (changed in v7.5):
  - Every tick: the full RCM frame is saved with a YELLOW ROI rectangle
    drawn on it, routed by status:
       contact     → ./local_output/contact/<ts>.jpg
       non_contact → ./local_output/non-contact/<ts>.jpg
  - Additionally on CONTACT: the 385×420 crop is saved as
       ./local_output/contact/cropped_<ts>.jpg
  Response: `fullframe_image` is always set; `roi_image` is a URL on
  contact and null on non_contact (no crop file to point to).

Per-prediction logging:
  Every call to /api/v1/predict appends one JSON line to
  <log_dir>/aoi_api.log (rotates daily at midnight; keeps `backup_count`
  days). The file-cleanup service can read the same config file to learn
  the paths to sweep.

Log event schema (JSON Lines):
  {"ts":"<iso8601>","level":"INFO","event":"predict","filename":"...",
   "status":"contact|non_contact",
   "roi_image": "<url or null>", "fullframe_image": "<url>",
   "laplacian_score":..., "probability_contact":...,
   "features":{...}, "latency_ms":...}
  Other events: "startup", "shutdown", "predict_error".
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
}


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(path: str = CONFIG_PATH) -> dict:
    if not os.path.exists(path):
        print(f"WARN: config {path} not found — using defaults", file=sys.stderr)
        return dict(DEFAULT_CONFIG)
    try:
        with open(path) as f:
            user_cfg = json.load(f)
        return _deep_merge(DEFAULT_CONFIG, user_cfg)
    except (OSError, ValueError) as e:
        print(f"WARN: cannot read config {path}: {e} — using defaults", file=sys.stderr)
        return dict(DEFAULT_CONFIG)


CFG = load_config()

CALIBRATION_PATH = CFG["paths"]["calibration_json"]
CONTACT_DIR = CFG["paths"]["contact_dir"]
NONCONTACT_DIR = CFG["paths"]["non_contact_dir"]
LOG_DIR = CFG["paths"]["log_dir"]

for d in (CONTACT_DIR, NONCONTACT_DIR, LOG_DIR):
    os.makedirs(d, exist_ok=True)


# ---------- JSON Lines logger ----------
class JsonLineFormatter(logging.Formatter):
    """Serialize log records whose msg is a dict to a one-line JSON object.
    Plain-string messages are wrapped under {"message": ...}."""

    def format(self, record: logging.LogRecord) -> str:
        if isinstance(record.msg, dict):
            payload = dict(record.msg)
        else:
            payload = {"message": record.getMessage()}
        out = {
            "ts": datetime.now().isoformat(timespec="milliseconds"),
            "level": record.levelname,
        }
        out.update(payload)
        return json.dumps(out, ensure_ascii=False, default=str)


def _build_logger() -> logging.Logger:
    log_path = os.path.join(LOG_DIR, CFG["logging"]["filename"])
    handler = TimedRotatingFileHandler(
        log_path,
        when="midnight",
        interval=1,
        backupCount=int(CFG["logging"]["backup_count"]),
        encoding="utf-8",
        utc=False,
    )
    handler.suffix = "%Y-%m-%d"  # rotated files: aoi_api.log.2026-11-10
    handler.setFormatter(JsonLineFormatter())
    lg = logging.getLogger("aoi_api")
    # Clear any pre-existing handlers (defensive on module re-imports).
    for h in list(lg.handlers):
        lg.removeHandler(h)
    lg.addHandler(handler)
    lg.setLevel(getattr(logging, str(CFG["logging"]["level"]).upper(), logging.INFO))
    lg.propagate = False
    return lg


logger = _build_logger()


def log_event(event: str, **fields) -> None:
    """Emit one JSON line to the rotating log."""
    logger.info({"event": event, **fields})


# ---------- FastAPI app ----------
@asynccontextmanager
async def lifespan(app_: FastAPI):
    log_event(
        "startup",
        version=app_.version,
        config_path=os.path.abspath(CONFIG_PATH),
        paths={
            "calibration_json": os.path.abspath(CALIBRATION_PATH),
            "contact_dir": os.path.abspath(CONTACT_DIR),
            "non_contact_dir": os.path.abspath(NONCONTACT_DIR),
            "log_dir": os.path.abspath(LOG_DIR),
        },
    )
    try:
        yield
    finally:
        log_event("shutdown", version=app_.version)


app = FastAPI(title="AOI Contact-Detection API", version="7.5", lifespan=lifespan)

# Static mounts for saved image retrieval — URLs are fixed regardless of the
# physical directories the config points at, so the contract with the monitor
# stays stable.
app.mount("/local_output/contact",
          StaticFiles(directory=CONTACT_DIR), name="contact")
app.mount("/local_output/non-contact",
          StaticFiles(directory=NONCONTACT_DIR), name="non_contact")

# Yellow in BGR (OpenCV channel order) = (0, 255, 255). Changed from blue in v7.5.
ROI_OVERLAY_COLOR_BGR = (0, 255, 255)
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


def load_calibration() -> dict:
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


def predict_probability(feats: dict, model: dict) -> float:
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
        "calibrated": calibrated,
    }


@app.get("/api/v1/config")
def config():
    model = load_calibration()
    return {
        "reference_roi": {k: model[k] for k in ("rx1", "ry1", "rx2", "ry2")},
        "model": model.get("model", "logistic"),
        "features": model.get("features", []),
        "decision_threshold": 0.5,
        "trained_on": {
            "n_contact": model.get("n_contact"),
            "n_non_contact": model.get("n_non_contact"),
        },
    }


@app.post("/api/v1/predict")
async def predict(
    file: UploadFile = File(..., description="完整 RCM 截圖（建議 1540 × 1050）"),
):
    t0 = time.perf_counter()
    model = load_calibration()
    rx1, ry1, rx2, ry2 = model["rx1"], model["ry1"], model["rx2"], model["ry2"]

    contents = await file.read()
    img = cv2.imdecode(np.frombuffer(contents, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        log_event("predict_error", filename=file.filename, error="decode_failed")
        raise HTTPException(status_code=400, detail="無法解析上傳的影像")
    if img.size == 0:
        log_event("predict_error", filename=file.filename, error="empty_image")
        raise HTTPException(status_code=400, detail="影像為空")

    crop = crop_frame(img, rx1, ry1, rx2, ry2)
    if crop.size == 0:
        log_event("predict_error", filename=file.filename, error="roi_invalid")
        raise HTTPException(status_code=500, detail="計算出的 ROI 範圍無效")

    feats = compute_features(crop)
    prob = predict_probability(feats, model)
    is_contact = prob >= 0.5
    status = "contact" if is_contact else "non_contact"

    # v7.5 persistence:
    #   Every tick → save the overlaid fullframe into the status subfolder.
    #   On contact → additionally save the cropped ROI.
    now = datetime.now()
    stamp = now.strftime("%Y%m%d_%H%M%S_") + f"{now.microsecond // 1000:03d}"
    full_name = f"{stamp}.jpg"
    out_dir = CONTACT_DIR if is_contact else NONCONTACT_DIR
    url_prefix = "/local_output/contact" if is_contact else "/local_output/non-contact"

    cv2.imwrite(os.path.join(out_dir, full_name),
                draw_roi_overlay(img, rx1, ry1, rx2, ry2))
    fullframe_url = f"{url_prefix}/{full_name}"

    roi_url = None
    if is_contact:
        crop_name = f"cropped_{stamp}.jpg"
        cv2.imwrite(os.path.join(CONTACT_DIR, crop_name), crop)
        roi_url = f"/local_output/contact/{crop_name}"

    response = {
        "status": status,
        "roi_image": roi_url,                  # URL on contact; null on non_contact
        "fullframe_image": fullframe_url,      # always set
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
