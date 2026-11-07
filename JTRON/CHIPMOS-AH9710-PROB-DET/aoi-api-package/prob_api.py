"""AOI-API for the AH9710 Contact Monitor system — universal build.

Classifies whether the probe needle has contacted the probe card:
  contact     = ROI is in focus
  non_contact = ROI is defocused

Contract (v7.2):
  - Caller uploads the FULL RCM snapshot (recommended camera: 1540 × 1050).
  - This API crops the uploaded frame using the fixed reference_roi from
    calibration.json, runs the logistic model on the crop, and saves BOTH:
      * the original frame with a blue ROI rectangle drawn on it
         → ./local_output/<status>/<timestamp>.jpg
      * the cropped ROI itself
         → ./local_output/<status>/cropped_<timestamp>.jpg
    where <status> ∈ {contact, non-contact}.
  - Returns a JSON with `status`, `probability_contact`, `features`,
    `laplacian_score`, and URL paths to both saved files.

Reference_roi (fractions of the full frame) is fixed for all probe-card types:
    rx1 = 0.25, ry1 = 0.45, rx2 = 0.50, ry2 = 0.85
"""
import cv2
import json
import math
import os
from datetime import datetime

import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

app = FastAPI(title="AOI Contact-Detection API", version="7.2")

OUTPUT_DIR = "./local_output"
CONTACT_DIR = os.path.join(OUTPUT_DIR, "contact")
NONCONTACT_DIR = os.path.join(OUTPUT_DIR, "non-contact")
CALIBRATION_PATH = os.path.join(OUTPUT_DIR, "calibration.json")
os.makedirs(CONTACT_DIR, exist_ok=True)
os.makedirs(NONCONTACT_DIR, exist_ok=True)

# Only the two class subfolders are exposed as static routes — calibration.json
# sitting beside them is NOT served.
app.mount("/local_output/contact",
          StaticFiles(directory=CONTACT_DIR), name="contact")
app.mount("/local_output/non-contact",
          StaticFiles(directory=NONCONTACT_DIR), name="non_contact")

# Blue overlay (BGR) for the ROI rectangle drawn on the saved full frame.
ROI_OVERLAY_COLOR_BGR = (255, 0, 0)
ROI_OVERLAY_THICKNESS = 3


def compute_features(roi_bgr):
    """Path C — 5 features on the grayscale ROI (post 5×5 Gaussian blur)."""
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
        raise HTTPException(status_code=500, detail="calibration.json not found")
    try:
        m = json.load(open(CALIBRATION_PATH))
    except (OSError, ValueError) as e:
        raise HTTPException(status_code=500, detail=f"Unreadable calibration.json: {e}")
    for k in ("features", "feature_means", "feature_stds", "weights", "intercept",
              "rx1", "ry1", "rx2", "ry2"):
        if k not in m:
            raise HTTPException(status_code=500,
                detail=f"calibration.json missing '{k}' — recalibrate.")
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
    """Return a copy of img_bgr with a blue ROI rectangle drawn on it."""
    out = img_bgr.copy()
    x1, y1, x2, y2 = roi_pixels(img_bgr, rx1, ry1, rx2, ry2)
    cv2.rectangle(out, (x1, y1), (x2, y2),
                  ROI_OVERLAY_COLOR_BGR, ROI_OVERLAY_THICKNESS)
    return out


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")


@app.get("/api/v1/health")
def health():
    """Readiness probe used by contact-monitor-service during STARTING."""
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
    """Expose the universal reference ROI + model metadata.
    Monitor uses `reference_roi` to confirm its RCM framing matches the
    training geometry (recommended: camera at 1540 × 1050 so the native
    crop is 385 × 420)."""
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
    file: UploadFile = File(..., description="RCM snapshot (recommended 1540 × 1050)"),
):
    """Receive a full RCM snapshot, crop it with reference_roi, classify the
    crop, and save both the overlaid full frame and the raw crop to
    ./local_output/<contact|non-contact>/.
    """
    model = load_calibration()
    rx1, ry1, rx2, ry2 = model["rx1"], model["ry1"], model["rx2"], model["ry2"]

    contents = await file.read()
    img = cv2.imdecode(np.frombuffer(contents, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=400, detail="無法解析上傳的影像")
    if img.size == 0:
        raise HTTPException(status_code=400, detail="影像為空")

    crop = crop_frame(img, rx1, ry1, rx2, ry2)
    if crop.size == 0:
        raise HTTPException(status_code=500, detail="計算出的 ROI 範圍無效")

    feats = compute_features(crop)
    prob = predict_probability(feats, model)
    is_contact = prob >= 0.5
    status = "contact" if is_contact else "non_contact"

    out_dir = CONTACT_DIR if is_contact else NONCONTACT_DIR
    url_prefix = "/local_output/contact" if is_contact else "/local_output/non-contact"

    now = datetime.now()
    stamp = now.strftime("%Y%m%d_%H%M%S_") + f"{now.microsecond // 1000:03d}"
    full_name = f"{stamp}.jpg"
    crop_name = f"cropped_{stamp}.jpg"

    cv2.imwrite(os.path.join(out_dir, full_name),
                draw_roi_overlay(img, rx1, ry1, rx2, ry2))
    cv2.imwrite(os.path.join(out_dir, crop_name), crop)

    return {
        "status": status,                                  # design-doc required
        "roi_image": f"{url_prefix}/{crop_name}",          # cropped 385×420 for web display
        "fullframe_image": f"{url_prefix}/{full_name}",    # full frame + blue ROI overlay for review
        "laplacian_score": round(feats["lap_var"], 2),     # design-doc compat field
        "probability_contact": round(prob, 4),
        "features": {k: round(v, 4) for k, v in feats.items()},
    }


if __name__ == "__main__":
    uvicorn.run("prob_api:app", host="0.0.0.0", port=8000, reload=False)
