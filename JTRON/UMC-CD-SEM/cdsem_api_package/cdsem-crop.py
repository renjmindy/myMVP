#!/usr/bin/env python
# coding: utf-8

# In[1]:


import os
import numpy as np


# In[2]:


# Dataset folder (must contain template/ and input/). Override with: python cdsem-crop.py <folder>
# Default: this script's folder, else the UMCCDSEM_09302026_2 subfolder next to it.
import sys
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if len(sys.argv) > 1:
    input_base = os.path.abspath(sys.argv[1])
elif os.path.isdir(os.path.join(SCRIPT_DIR, "template")):
    input_base = SCRIPT_DIR
else:
    input_base = os.path.join(SCRIPT_DIR, "UMCCDSEM_09302026_1")

if os.path.exists(input_base):
    print("Dataset found:", input_base)
    print("Contents:", os.listdir(input_base))
else:
    print("Dataset not found:", input_base)


# # Requirements
# Python packages: numpy pillow opencv-python matplotlib pytesseract (optional: easyocr).
# The Tesseract OCR binary must be on PATH (e.g. `sudo apt-get install tesseract-ocr`).


# ### CD-SEM image cropper
# 
# - t1 : template monitor preview image  (anchored on align_hold.png)
# - m1 : main SEM imaging window         (anchored on align_mag.png)
# - mag: magnification value via OCR     (anchored on align_mag.png)
# 
# Directory layout:
# *  template/   align_hold.png, align_mag.png, cursor.png
# *  samples/    cdsem*.png  (input screenshots)
# *  output/     generated results
# 
# * <dataset>/template/   align_hold.png, align_mag.png, cursor.png
# * <dataset>/input/      cdsem*.png / cdsem*.jpg  (input screenshots)
# * <dataset>/output/     generated results
# 
# Anchor offsets were calibrated against cdsem1.png / sample_t1.png / sample_m1.png.

# # Imports, Constants & Configurations
# 
# Imports, environment-detection, and global configuration constants. `PY`

# In[4]:


import os
import re
import sys
import glob
import time
import atexit
import subprocess
import tempfile
import numpy as np
from PIL import Image
import cv2
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec


# In[5]:


# OCR Engine Imports
import pytesseract

try:
    import easyocr
    EASYOCR_READER = easyocr.Reader(['en'], gpu=False, verbose=False)
except Exception:
    EASYOCR_READER = None


# * Fixed offsets (pixels) relative to each anchor's top-left corner
# * Calibrated so that cdsem1 crops match sample_t1.png / sample_m1.png exactly.

# In[6]:


# t1  =  (hold_x + T1_L,  hold_y + T1_T)  →  (hold_x + T1_R,  hold_y + T1_B)
# Low-mag  (< 20k): 284×167 px

T1_L, T1_T = -300, -56
T1_R, T1_B = -16,  111

# High-mag (≥ 20k): 258×152 px  (right/top edge unchanged, left/bottom trimmed)

T1_L_HI, T1_T_HI = -274, -56
T1_R_HI, T1_B_HI = -16,   96

# m1  =  (mag_x + M1_L,  mag_y + M1_T)  →  (mag_x + M1_R,  mag_y + M1_B)
#   All four edges are anchored to mag_x/mag_y → consistent crop size across images.

# The anchors/offsets were calibrated on a 1920x1080 remote-desktop capture whose SEM screen
# (without the window title bar / taskbar) is ~1920x1000. 1680x1050 inputs are rescaled to match.
REF_SIZE = (1920, 1000)

# White rectangle inside the t1 preview: search ranges (px), edge thickness and minimum score
T1_RECT_W_RANGE = (40, 70)
T1_RECT_H_RANGE = (8, 22)
T1_RECT_EDGE_PX = 2
T1_RECT_MIN_SCORE = 8.0

# A mapped m1 point is flagged reliable only if the image matched, the fine score is at least this, and the point lies inside m1
M1_POINT_MIN_FINE = 0.22

# Minimum normalised cross-correlation for an anchor match
ANCHOR_MIN_SCORE = 0.75

# Fraction of upper-left glyph area that must be inked for a glyph to count as an "8" (not a "3")
MIN_8_LEFT_INK = 0.45

M1_L, M1_T =  200, -139
M1_R, M1_B =  967,  312


# # General Helper Functions
# 
# Helper utilities for image array conversion, template matching, and magnification score validation. `PY`

# In[7]:


def pil_to_bgr(img: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.array(img.convert("RGB")), cv2.COLOR_RGB2BGR)


# In[8]:


def template_match(scene_bgr: np.ndarray, tmpl_bgr: np.ndarray) -> tuple[int, int, int, int]:
    """
    Find tmpl inside scene using normalised cross-correlation.
    Returns (x, y, w, h) of the best match (top-left corner).
    Raises RuntimeError if score < ANCHOR_MIN_SCORE.
    """
    scene_g = cv2.cvtColor(scene_bgr, cv2.COLOR_BGR2GRAY)
    tmpl_g  = cv2.cvtColor(tmpl_bgr,  cv2.COLOR_BGR2GRAY)
    res = cv2.matchTemplate(scene_g, tmpl_g, cv2.TM_CCOEFF_NORMED)
    _, score, _, loc = cv2.minMaxLoc(res)
    if score < ANCHOR_MIN_SCORE:
        raise RuntimeError(f"Template match score too low ({score:.3f}); anchor not found.")
    return loc[0], loc[1], tmpl_bgr.shape[1], tmpl_bgr.shape[0]


# # Cropping Functions
# 
# Functions for cropping the `t1` monitor preview and `m1` SEM window regions. `PY` 

# In[9]:


def _mag_to_x(mag_str: str) -> float:
    mag_str = mag_str.lower().replace(" ", "").replace("o", "0")

    # Handle 'k' multiplier
    if "k" in mag_str:
        num_part = mag_str.replace("k", "")
        try:
            val = float(num_part)
            # Fix decimal offset misreads (e.g., "700k" or "200k" when it should be "7.00k" or "20.0k")
            if val >= 100:
                val /= 100.0
            return val * 1000.0
        except ValueError:
            return 0.0

    # Handle plain numbers / PM values (e.g., "104" or optical mode)
    try:
        val = float(mag_str)
        return val
    except ValueError:
        return 0.0


# In[10]:


#def _mag_to_x(mag: str) -> float:
#    """Parse mag string (e.g. '8.00k', '100k', '104') to a numeric x value."""
#    if mag == "unknown": return 0.0
#    m = re.match(r"([\d.]+)\s*([kKmMuU])?", mag.strip())
#    if not m: return 0.0
#    val = float(m.group(1))
#    unit = (m.group(2) or "").lower()
#    return val * {"k": 1000, "m": 1_000_000, "u": 1}.get(unit, 1)


# In[11]:


def is_optical_mode(img_crop) -> bool:
    # Use OCR or text matching on the header crop where "Image OM" / "Image SEM" appears
    header_text = ocr_header_region(img_crop).upper()
    return "OM" in header_text


# In[12]:


def determine_match(coarse_score: float, fine_score: float, mag_x: float, is_om: bool = False) -> str:
    # Handle Optical Mode separately due to lower high-frequency contrast
    if is_om:
        if fine_score >= 0.10 or coarse_score >= 0.25:
            return "match"
        return "no_match"

    # High magnification SEM (>= 20k)
    if mag_x >= 20000.0:
        if coarse_score >= 0.40 and fine_score >= 0.25:
            return "match"
        return "no_match"

    # Low/Medium magnification SEM (< 20k)
    else:
        if coarse_score >= 0.40 or fine_score >= 0.25:
            return "match"
        return "no_match"


# In[13]:


#def determine_match(mag: str, coarse_score: float, fine_score: float) -> bool:
#    """
#    Determine if t1 template is found in m1 based on magnification and scores.

#    Rules:
#      mag < 20k  : matched if fine_score >= 0.2
#      mag >= 20k : matched if coarse_score >= 0.2  (fine search not required)
#    """
#    mag_x = _mag_to_x(mag)
#    if mag_x < 20_000: return fine_score >= 0.2
#    else: return coarse_score >= 0.4


# In[14]:


def crop_t1(img: Image.Image, hold_bgr: np.ndarray, high_mag: bool = False) -> Image.Image:
    """
    Locate the Hold button, then crop t1 using fixed offsets.
    Uses high-mag offsets (250×147) when high_mag=True, else standard (284×167).
    """
    scene = pil_to_bgr(img)
    hx, hy, _, _ = template_match(scene, hold_bgr)

    if high_mag: l, t, r, b = T1_L_HI, T1_T_HI, T1_R_HI, T1_B_HI
    else: l, t, r, b = T1_L, T1_T, T1_R, T1_B

    left   = max(0,         hx + l)
    top    = max(0,         hy + t)
    right  = min(img.width, hx + r)
    bottom = min(img.height,hy + b)

    return img.crop((left, top, right, bottom))


# In[15]:


def find_t1_rect_center(t1: Image.Image, min_score: float = T1_RECT_MIN_SCORE) -> dict:
    """
    Return the centre of the thin white rectangle drawn inside a t1 (template monitor) crop,
    measured from the crop's top-right corner pixel. If no rectangle is visible (e.g. high-mag
    previews that only show crosshair lines), the middle point of the t1 crop is returned instead.

    Returned dict:
        cx, cy          centre in crop pixel coordinates (x right, y down, origin top-left)
        from_right      pixels LEFT of the top-right corner   (= (W-1) - cx)
        from_top        pixels DOWN from the top-right corner (= cy)
        source          "rectangle" or "center" (fallback: middle of the crop)
        x, y, w, h      rectangle box (None when source == "center")
        score           mean high-pass brightness of the weakest side (higher = clearer rectangle)

    All four sides must be bright, so single crosshair lines or stripes do not score as a rectangle.
    """
    g = np.array(t1.convert("L"), dtype=np.float32)
    H, W = g.shape
    hp = cv2.GaussianBlur(g, (0, 0), 0.8) - cv2.GaussianBlur(g, (0, 0), 3.0)   # thin bright lines stand out

    # Integral image so any strip sum is O(1)
    ii = np.pad(hp, ((1, 0), (1, 0))).cumsum(0).cumsum(1)

    def box(y0, y1, x0, x1):      # sum of hp[y0:y1, x0:x1] for arrays of offsets
        return ii[y1, x1] - ii[y0, x1] - ii[y1, x0] + ii[y0, x0]

    t = T1_RECT_EDGE_PX
    best = None
    for h in range(T1_RECT_H_RANGE[0], T1_RECT_H_RANGE[1] + 1):
        for w in range(T1_RECT_W_RANGE[0], T1_RECT_W_RANGE[1] + 1):
            ny, nx = H - h + 1, W - w + 1
            if ny <= 0 or nx <= 0:
                continue
            ys = np.arange(ny)[:, None]
            xs = np.arange(nx)[None, :]
            top    = box(ys,         ys + t,     xs,         xs + w) / (t * w)
            bottom = box(ys + h - t, ys + h,     xs,         xs + w) / (t * w)
            left   = box(ys,         ys + h,     xs,         xs + t) / (t * h)
            right  = box(ys,         ys + h,     xs + w - t, xs + w) / (t * h)
            score = np.minimum(np.minimum(top, bottom), np.minimum(left, right))
            iy, ix = np.unravel_index(np.argmax(score), score.shape)
            if best is None or score[iy, ix] > best[0]:
                best = (float(score[iy, ix]), int(ix), int(iy), w, h)

    if best is not None and best[0] >= min_score:
        score, x, y, w, h = best
        cx, cy = x + (w - 1) / 2.0, y + (h - 1) / 2.0
        source = "rectangle"
    else:
        score = best[0] if best is not None else 0.0
        x = y = w = h = None
        cx, cy = (W - 1) / 2.0, (H - 1) / 2.0
        source = "center"

    return {"cx": cx, "cy": cy, "from_right": (W - 1) - cx, "from_top": cy,
            "source": source, "x": x, "y": y, "w": w, "h": h, "score": score}


def draw_t1_rect(t1: Image.Image, res: dict) -> Image.Image:
    """Return a copy of t1 with the found centre marked (red cross) and the rectangle outlined (green)."""
    arr = np.array(t1.convert("RGB"))
    cv2.drawMarker(arr, (int(round(res["cx"])), int(round(res["cy"]))), (255, 0, 0), cv2.MARKER_CROSS, 9, 1)
    if res["source"] == "rectangle":
        cv2.rectangle(arr, (res["x"], res["y"]), (res["x"] + res["w"] - 1, res["y"] + res["h"] - 1), (0, 255, 0), 1)
    return Image.fromarray(arr)


def crop_m1(img: Image.Image, mag_bgr: np.ndarray) -> Image.Image:
    """
    Locate the Magnification label, then crop m1 using fixed offsets.
    """
    scene = pil_to_bgr(img)
    mx, my, _, _ = template_match(scene, mag_bgr)

    left   = max(0,          mx + M1_L)
    top    = max(0,          my + M1_T)
    right  = min(img.width,  mx + M1_R)
    bottom = min(img.height, my + M1_B)

    return img.crop((left, top, right, bottom))


# #  Linux / Tesseract OCR Functions
# Replacing Windows WinRT with Linux-compatible `pytesseract` and `easyocr` engines. `PY` 

# In[16]:


def _linux_ocr(img_pil: Image.Image) -> str:
    """Run OCR on a PIL image using PyTesseract with fallback to EasyOCR."""
    # 1. Primary engine: PyTesseract
    try:
        config = "--psm 7 -c tessedit_char_whitelist=0123456789.kKmMuUsSbBgGqQaAzZ"
        text = pytesseract.image_to_string(img_pil, config=config).strip()
        if text:
            return text
    except Exception:
        pass

    # 2. Fallback engine: EasyOCR
    if EASYOCR_READER is not None:
        try:
            arr = np.array(img_pil.convert("RGB"))
            results = EASYOCR_READER.readtext(arr, detail=0)
            return " ".join(results).strip()
        except Exception:
            pass

    return ""


# In[17]:


def _extract_mag_value(raw: str) -> str | None:
    cleaned = (raw
               .replace("O", "0").replace("o", "0")
               .replace("I", "1").replace("l", "1")
               .replace("S", "5"))

    letter_to_digit = {
        "s": "8", "S": "8",
        "b": "6", "B": "8",
        "g": "6", "G": "6",
        "q": "9", "Q": "9",
        "a": "4", "A": "4",
        "z": "2", "Z": "2",
    }
    cleaned = re.sub(
        r"([a-zA-Z])(\.\d)",
        lambda m: letter_to_digit.get(m.group(1), m.group(1)) + m.group(2),
        cleaned,
    )

    m = re.search(r"(\d+[.,]\d+)\s*([kKmMuU])", cleaned)
    if m:
        val = m.group(1).replace(",", ".") + m.group(2).lower()
        val = re.sub(r"(\d+\.\d{2})\d+", r"\1", val)
        return val

    m = re.search(r"(\d{2,})\s*([kKmMuU])", cleaned)
    if m:
        return m.group(1) + m.group(2).lower()

    m = re.search(r"\b(\d{2,4})\b", cleaned)
    if m:
        return m.group(1)

    return None


# In[18]:


def _glyph_masks(region: Image.Image) -> list:
    """Split the magnification value text (right of the 'PM' label) into per-character binary masks."""
    g = np.array(region.convert("L"))[4:38, 67:217]
    g = cv2.normalize(g, None, 0, 255, cv2.NORM_MINMAX)
    _, b = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    cols = list((b > 0).sum(axis=0) > 0) + [False]
    masks, start = [], None
    for i, on in enumerate(cols):
        if on and start is None:
            start = i
        elif not on and start is not None:
            masks.append(b[:, start:i] > 0)
            start = None
    return masks


def _closed_left_side(mask: np.ndarray) -> bool:
    """True if the glyph has ink along its left edge in the upper part (an '8'), False if open there (a '3')."""
    rows = np.where(mask.any(axis=1))[0]
    glyph = mask[rows.min():rows.max() + 1]
    h, w = glyph.shape
    band = glyph[int(h * 0.20):int(h * 0.45), :max(2, int(w * 0.30))]
    return band.mean() > MIN_8_LEFT_INK


def _refine_3_vs_8(region: Image.Image, val: str) -> str:
    """Tesseract often confuses 3 and 8 in the SEM font; re-decide each from glyph shape."""
    if "3" not in val and "8" not in val:
        return val
    masks = _glyph_masks(region)
    if len(masks) < len(val):
        return val
    out = []
    for ch, mask in zip(val, masks):
        if ch in "38":
            ch = "8" if _closed_left_side(mask) else "3"
        out.append(ch)
    return "".join(out)


def ocr_magnification(img: Image.Image, mag_bgr: np.ndarray) -> str:
    scene = pil_to_bgr(img)
    mx, my, mw, mh = template_match(scene, mag_bgr)

    cx1 = max(0,          mx - 5)
    cy1 = my + mh
    cx2 = min(img.width,  mx + mw + 50)
    cy2 = min(img.height, cy1 + 42)

    region = img.crop((cx1, cy1, cx2, cy2))

    best_val = None
    for scale in (4, 6):
        up = region.resize((region.width * scale, region.height * scale), Image.NEAREST)
        raw = _linux_ocr(up)

        raw_dec = re.sub(r'(\d+)\s+(\d+)([kKmMuU])', r'\1.\2\3', raw)
        val = _extract_mag_value(raw_dec)
        if val and "." in val:
            return _refine_3_vs_8(region, val)

        val = _extract_mag_value(raw.replace(" ", ""))
        if val:
            if best_val is None:
                best_val = val
            if "." in val:
                return _refine_3_vs_8(region, val)

    return _refine_3_vs_8(region, best_val) if best_val else "unknown"


# # Image Preprocessing (Cursor Removal)
# Inpainting and removing UI elements or cursor overlays before processing. `PY` 

# In[19]:


def load_cursor(folder: str):
    """Load cursor.png from folder/template/ as RGBA numpy array, or return None if not found."""
    path = os.path.join(folder, "template", "cursor.png")
    if not os.path.isfile(path):
        return None
    return np.array(Image.open(path).convert("RGBA"))


# In[20]:


def remove_cursor(img: Image.Image, cursor_rgba: np.ndarray, threshold: float = 0.65) -> Image.Image:
    scene_bgr = pil_to_bgr(img)
    scene_g   = cv2.cvtColor(scene_bgr, cv2.COLOR_BGR2GRAY)
    alpha = cursor_rgba[:, :, 3]
    rgb   = cursor_rgba[:, :, :3]

    if alpha.min() > 200:
        cursor_g = cv2.cvtColor(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), cv2.COLOR_BGR2GRAY)
    else:
        gray_bg = np.full_like(rgb, 128, dtype=np.float32)
        a = alpha[:, :, np.newaxis] / 255.0
        comp = (rgb.astype(np.float32) * a + gray_bg * (1 - a)).astype(np.uint8)
        cursor_g = cv2.cvtColor(comp, cv2.COLOR_RGB2GRAY)

    ch, cw = cursor_rgba.shape[:2]
    if ch >= scene_g.shape[0] or cw >= scene_g.shape[1]:
        return img

    res = cv2.matchTemplate(scene_g, cursor_g, cv2.TM_CCOEFF_NORMED)
    _, score, _, loc = cv2.minMaxLoc(res)
    if score < threshold:
        return img

    x, y = loc

    if alpha.min() > 200:
        tmask = (cursor_g < 240).astype(np.uint8) * 255
    else:
        tmask = (alpha > 20).astype(np.uint8) * 255

    tmask = cv2.dilate(tmask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))

    mask = np.zeros(scene_bgr.shape[:2], dtype=np.uint8)
    y2, x2 = min(y + ch, mask.shape[0]), min(x + cw, mask.shape[1])
    mask[y:y2, x:x2] = tmask[: y2 - y, : x2 - x]

    result = cv2.inpaint(scene_bgr, mask, inpaintRadius=7, flags=cv2.INPAINT_TELEA)
    return Image.fromarray(cv2.cvtColor(result, cv2.COLOR_BGR2RGB))


# In[21]:


def preprocess_full(img: Image.Image, cursor_rgba) -> Image.Image:
    if cursor_rgba is not None:
        img = remove_cursor(img, cursor_rgba)
    return img


# # Feature Matching & Overlay Visualization
# Coarse and fine matching calculations to map `t1` onto `m1`. `PY`

# In[22]:


def _normalize(arr: np.ndarray) -> np.ndarray:
    lo, hi = arr.min(), arr.max()
    if hi == lo:
        return np.zeros_like(arr)
    return (arr - lo) / (hi - lo) * 255.0


# In[23]:


def _ncc(a: np.ndarray, b: np.ndarray) -> float:
    a = a - a.mean()
    b = b - b.mean()
    denom = np.sqrt((a ** 2).sum() * (b ** 2).sum())
    return float(np.sum(a * b) / denom) if denom > 0 else 0.0


# In[24]:


def fine_match_t1_on_m1(
    t1_local_scaled: Image.Image,
    m1: Image.Image,
    coarse_x: int,
    coarse_y: int,
    angle_min: float = -5.0,
    angle_max: float =  5.0,
    angle_step: float = 1.0,
    polarity_invariant: bool = False,
    edge_match: bool = False,
) -> tuple[float, float, float, float]:
    m1w, m1h = m1.size
    rx, ry = m1w // 20, m1h // 20

    t1lw, t1lh = t1_local_scaled.size
    t1_g = np.array(t1_local_scaled.convert("L"), dtype=np.float32)
    m1_g = np.array(m1.convert("L"), dtype=np.float32)

    lft = max(0, rx - coarse_x)
    top = max(0, ry - coarse_y)
    rgt = max(0, coarse_x + rx + t1lw - m1w)
    bot = max(0, coarse_y + ry + t1lh - m1h)
    if lft or top or rgt or bot:
        m1_g = cv2.copyMakeBorder(m1_g, top, bot, lft, rgt, cv2.BORDER_REPLICATE)
    coarse_x_p = coarse_x + lft
    coarse_y_p = coarse_y + top

    if edge_match:
        _m1u = np.clip(m1_g, 0, 255).astype(np.uint8)
        m1_match = cv2.Canny(cv2.GaussianBlur(_m1u, (19, 19), 3.0), 20, 80).astype(np.float32)
    else:
        m1_match = m1_g

    rot_center = (t1lw / 2.0, t1lh / 2.0)
    n_steps = round((angle_max - angle_min) / angle_step) + 1
    angles = [angle_min + i * angle_step for i in range(n_steps)]

    best_score = -np.inf
    best_c_sub, best_r_sub, best_angle = float(coarse_x), float(coarse_y), 0.0

    for angle in angles:
        M = cv2.getRotationMatrix2D(rot_center, angle, 1.0)
        t1_rot = cv2.warpAffine(t1_g, M, (t1lw, t1lh), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        if edge_match:
            _t1u = np.clip(t1_rot, 0, 255).astype(np.uint8)
            t1_for_match = cv2.Canny(cv2.GaussianBlur(_t1u, (13, 13), 2.0), 20, 80).astype(np.float32)
        else:
            t1_for_match = t1_rot

        res = cv2.matchTemplate(m1_match, t1_for_match, cv2.TM_CCOEFF_NORMED)
        if res.size == 0:
            continue

        c_lo = max(0,              coarse_x_p - rx)
        c_hi = min(res.shape[1]-1, coarse_x_p + rx)
        r_lo = max(0,              coarse_y_p - ry)
        r_hi = min(res.shape[0]-1, coarse_y_p + ry)

        if c_lo > c_hi or r_lo > r_hi:
            _, _, _, (c, r) = cv2.minMaxLoc(res)
        else:
            sub = res[r_lo:r_hi+1, c_lo:c_hi+1]
            idx = np.unravel_index(np.argmax(sub), sub.shape)
            r, c = r_lo + idx[0], c_lo + idx[1]

        score = float(res[r, c])

        dc = -0.5 * float(res[r, c+1] - res[r, c-1]) / float(res[r, c-1] - 2*res[r, c] + res[r, c+1]) if 0 < c < res.shape[1]-1 and abs(res[r, c-1] - 2*res[r, c] + res[r, c+1]) > 1e-9 else 0.0
        dr = -0.5 * float(res[r+1, c] - res[r-1, c]) / float(res[r-1, c] - 2*res[r, c] + res[r+1, c]) if 0 < r < res.shape[0]-1 and abs(res[r-1, c] - 2*res[r, c] + res[r+1, c]) > 1e-9 else 0.0

        if score > best_score:
            best_score = score
            best_c_sub = (c + np.clip(dc, -0.5, 0.5)) - lft
            best_r_sub = (r + np.clip(dr, -0.5, 0.5)) - top
            best_angle = angle

    return best_c_sub, best_r_sub, best_angle, best_score


# In[25]:


def _score_map_to_img(score_map: np.ndarray, best_dx: int, best_dy: int, scale: int = 8) -> Image.Image:
    lo, hi = score_map.min(), score_map.max()
    norm = ((score_map - lo) / (hi - lo + 1e-9) * 255).astype(np.uint8)
    colored = cv2.applyColorMap(norm, cv2.COLORMAP_JET)
    h, w = colored.shape[:2]
    colored = cv2.resize(colored, (w * scale, h * scale), interpolation=cv2.INTER_NEAREST)
    cv2.drawMarker(colored, (best_dx * scale + scale // 2, best_dy * scale + scale // 2), (255, 255, 255), cv2.MARKER_CROSS, scale * 3, 2)
    return Image.fromarray(cv2.cvtColor(colored, cv2.COLOR_BGR2RGB))


# In[26]:


def find_t1_in_m1(t1: Image.Image, m1: Image.Image, small_thumb: bool = False):
    m1w, m1h = m1.size
    t1w, t1h = t1.size
    THUMB = 20

    if small_thumb:
        C0_X, C1_X, C0_Y, C1_Y, PAD_X, PAD_Y = 0, 20, 0, 20, 10, 10
    else:
        C0_X, C1_X, C0_Y, C1_Y, PAD_X, PAD_Y = 3, 17, 3, 17, 7, 7

    M1S_W, M1S_H = THUMB + 2 * PAD_X, THUMB + 2 * PAD_Y

    t1_thumb = t1.resize((THUMB, THUMB), Image.LANCZOS).convert("L")
    t1s_img  = t1_thumb.crop((C0_X, C0_Y, C1_X, C1_Y))
    t1s      = _normalize(np.array(t1s_img, dtype=float))

    lx1, ly1 = int(C0_X / THUMB * t1w), int(C0_Y / THUMB * t1h)
    lx2, ly2 = int(C1_X / THUMB * t1w), int(C1_Y / THUMB * t1h)
    t1_local = t1.crop((lx1, ly1, lx2, ly2))

    m1_thumb = m1.resize((THUMB, THUMB), Image.LANCZOS).convert("L")
    m1s_img  = Image.new("L", (M1S_W, M1S_H), 0)
    m1s_img.paste(Image.fromarray(_normalize(np.array(m1_thumb, dtype=float)).astype(np.uint8)), (PAD_X, PAD_Y))
    m1s     = np.array(m1s_img, dtype=float)

    t1s_h, t1s_w = t1s.shape
    n_dy, n_dx = m1s.shape[0] - t1s_h + 1, m1s.shape[1] - t1s_w + 1
    score_map = np.zeros((n_dy, n_dx), dtype=np.float32)
    best_score_c = -np.inf
    best_dx, best_dy = n_dx // 2, n_dy // 2

    for dy in range(n_dy):
        for dx in range(n_dx):
            score = _ncc(t1s, m1s[dy : dy + t1s_h, dx : dx + t1s_w])
            score_map[dy, dx] = score
            if score > best_score_c:
                best_score_c, best_dx, best_dy = score, dx, dy

    score_map_img = _score_map_to_img(score_map, best_dx, best_dy)
    scale_x, scale_y = m1w / float(THUMB), m1h / float(THUMB)
    coarse_t1_x = best_dx * scale_x - t1w / 2.0
    coarse_t1_y = best_dy * scale_y - t1h / 2.0
    coarse_x, coarse_y = int(coarse_t1_x + lx1), int(coarse_t1_y + ly1)

    return coarse_x, coarse_y, best_score_c, t1s_img, m1s_img, t1_local, int(coarse_t1_x), int(coarse_t1_y), best_dx, best_dy, score_map_img


# In[27]:


def overlay_t1s_on_m1s(t1s_img, m1s_img, best_dx, best_dy, scale=10, box_color=(255, 0, 0)):
    m1s_up = m1s_img.resize((m1s_img.width * scale, m1s_img.height * scale), Image.NEAREST).convert("RGB")
    t1s_up = t1s_img.resize((t1s_img.width * scale, t1s_img.height * scale), Image.NEAREST).convert("RGBA")

    px, py = best_dx * scale, best_dy * scale
    pw, ph = t1s_img.width * scale, t1s_img.height * scale

    r, g, b, a = t1s_up.split()
    t1s_up = Image.merge("RGBA", (r, g, b, a.point(lambda v: 160)))

    result = m1s_up.convert("RGBA")
    overlay = Image.new("RGBA", result.size, (0, 0, 0, 0))
    overlay.paste(t1s_up, (px, py))
    result = Image.alpha_composite(result, overlay).convert("RGB")

    arr = np.array(result)
    y0, y1 = max(0, py), min(result.height - 1, py + ph)
    x0, x1 = max(0, px), min(result.width - 1, px + pw)
    arr[y0, px:px+pw] = box_color; arr[y1, px:px+pw] = box_color
    arr[py:py+ph, x0] = box_color; arr[py:py+ph, x1] = box_color

    return Image.fromarray(arr)


# In[28]:


def overlay_t1_on_m1(t1, m1, t1_local, t1_paste, alpha=0.65, box_color=(255, 0, 0), box_width=3, angle_range=5.0, angle_step=1.0, polarity_invariant=False, edge_match=False):
    m1w, m1h = m1.size
    t1w, t1h = t1.size
    t1lw, t1lh = t1_local.size
    px, py = t1_paste

    k = max(m1w / t1w, m1h / t1h)
    new_w, new_h = int(t1w * k), int(t1h * k)
    t1_scaled = t1.resize((new_w, new_h), Image.LANCZOS)
    t1_local_scaled = t1_local.resize((int(t1lw * k), int(t1lh * k)), Image.LANCZOS)
    t1ls_w, t1ls_h = t1_local_scaled.size

    cx, cy = px + t1w // 2, py + t1h // 2
    coarse_t1_px, coarse_t1_py = cx - new_w // 2, cy - new_h // 2
    lx1_s, ly1_s = int(round((t1w - t1lw) / 2.0 * k)), int(round((t1h - t1lh) / 2.0 * k))
    coarse_local_x, coarse_local_y = coarse_t1_px + lx1_s, coarse_t1_py + ly1_s

    fine_local_x, fine_local_y, best_angle, fine_score = fine_match_t1_on_m1(
        t1_local_scaled, m1, coarse_local_x, coarse_local_y,
        angle_min=-angle_range, angle_max=angle_range, angle_step=angle_step,
        polarity_invariant=polarity_invariant, edge_match=edge_match,
    )

    fine_px, fine_py = fine_local_x - lx1_s, fine_local_y - ly1_s

    t1_rot = t1_scaled
    if best_angle != 0.0:
        t1_arr = np.array(t1_scaled.convert("RGB"), dtype=np.uint8)
        M = cv2.getRotationMatrix2D((new_w / 2.0, new_h / 2.0), best_angle, 1.0)
        t1_arr = cv2.warpAffine(t1_arr, M, (new_w, new_h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        t1_rot = Image.fromarray(cv2.cvtColor(t1_arr, cv2.COLOR_BGR2RGB))

    result = m1.convert("RGBA")
    overlay = Image.new("RGBA", result.size, (0, 0, 0, 0))
    t1_rgba = t1_rot.convert("RGBA")
    r, g, b, a = t1_rgba.split()
    t1_rgba = Image.merge("RGBA", (r, g, b, a.point(lambda v: int(v * alpha))))
    overlay.paste(t1_rgba, (int(round(fine_px)), int(round(fine_py))))
    result = Image.alpha_composite(result, overlay).convert("RGB")

    bx, by = int(round(fine_local_x)), int(round(fine_local_y))
    result_arr = np.array(result)
    h_x0, h_x1 = max(0, bx), min(m1w, bx + t1ls_w)
    v_y0, v_y1 = max(0, by), min(m1h, by + t1ls_h)

    for w in range(box_width):
        y_top, y_bottom = max(0, by - w), min(m1h - 1, by + t1ls_h + w)
        x_left, x_right = max(0, bx - w), min(m1w - 1, bx + t1ls_w + w)
        if h_x0 < h_x1:
            if 0 <= y_top < m1h: result_arr[y_top, h_x0:h_x1] = box_color
            if 0 <= y_bottom < m1h: result_arr[y_bottom, h_x0:h_x1] = box_color
        if v_y0 < v_y1:
            if 0 <= x_left < m1w: result_arr[v_y0:v_y1, x_left] = box_color
            if 0 <= x_right < m1w: result_arr[v_y0:v_y1, x_right] = box_color

    return Image.fromarray(result_arr), best_angle, fine_score, fine_local_x, fine_local_y


# # Output & File Handling
# Functions responsible for reading templates and writing results to the output folder. `PY`  

# In[29]:


def load_anchors(folder: str) -> tuple[np.ndarray, np.ndarray]:
    tmpl_dir  = os.path.join(folder, "template")
    hold_path = os.path.join(tmpl_dir, "align_hold.png")
    mag_path  = os.path.join(tmpl_dir, "align_mag.png")
    for p in (hold_path, mag_path):
        if not os.path.isfile(p):
            raise FileNotFoundError(f"Anchor image not found: {p}")
    hold_bgr = pil_to_bgr(Image.open(hold_path))
    mag_bgr  = pil_to_bgr(Image.open(mag_path))
    return hold_bgr, mag_bgr


# In[30]:


def process_image(img_path: str, hold_bgr: np.ndarray, mag_bgr: np.ndarray, cursor_rgba=None):
    img = Image.open(img_path).convert("RGB")
    if img.size != REF_SIZE:
        img = img.resize(REF_SIZE, Image.LANCZOS)
    img = preprocess_full(img, cursor_rgba)
    mag = ocr_magnification(img, mag_bgr)
    t1  = crop_t1(img, hold_bgr, high_mag=(_mag_to_x(mag) >= 20_000))
    m1  = crop_m1(img, mag_bgr)
    high_mag = _mag_to_x(mag) >= 20_000
    fx, fy, coarse_score, t1s_img, m1s_img, t1_local, t1_px, t1_py, best_dx, best_dy, score_map_img = find_t1_in_m1(t1, m1, small_thumb=high_mag)
    thumb_match_img = overlay_t1s_on_m1s(t1s_img, m1s_img, best_dx, best_dy)

    if coarse_score == 0.0:
        m1w, m1h = m1.size
        match_img = Image.new("RGB", (m1w, m1h), (40, 40, 40))
        best_angle, fine_score, fine_x, fine_y = 0.0, 0.0, float(m1w / 2), float(m1h / 2)
    else:
        match_img, best_angle, fine_score, fine_x, fine_y = overlay_t1_on_m1(
            t1, m1, t1_local, (t1_px, t1_py), angle_range=2.5 if high_mag else 5.0,
            angle_step=0.5 if high_mag else 1.0, polarity_invariant=False, edge_match=high_mag
        )

    return t1, m1, mag, (fx, fy), coarse_score, best_angle, fine_score, fine_x, fine_y, match_img, t1s_img, m1s_img, t1_local, thumb_match_img, score_map_img


# In[31]:


def t1_point_to_m1(t1: Image.Image, t1_local: Image.Image, m1: Image.Image,
                   fine_x: float, fine_y: float, angle: float, point: tuple,
                   coarse_score: float = None, fine_score: float = None) -> dict:
    """
    Map a point given in t1 pixel coordinates (e.g. the centre from find_t1_rect_center) to m1 pixel
    coordinates, using the fine-match result: t1 is scaled by k, rotated by `angle` about its own centre,
    then pasted so that its local patch sits at (fine_x, fine_y). This mirrors overlay_t1_on_m1().

    Returns cx, cy (m1 pixel coords, x right / y down, origin top-left) and from_right / from_top, the
    distances left of / below m1's top-right corner pixel. Only meaningful when the match is good.
    coarse_score and fine_score are passed through so the match quality travels with the point.
    """
    m1w, m1h = m1.size
    t1w, t1h = t1.size
    t1lw, t1lh = t1_local.size
    k = max(m1w / t1w, m1h / t1h)
    new_w, new_h = int(t1w * k), int(t1h * k)

    lx1_s = int(round((t1w - t1lw) / 2.0 * k))
    ly1_s = int(round((t1h - t1lh) / 2.0 * k))
    paste_x, paste_y = int(round(fine_x - lx1_s)), int(round(fine_y - ly1_s))

    # Scale the point, rotate it about the scaled t1 centre (same matrix as the overlay), then translate
    M = cv2.getRotationMatrix2D((new_w / 2.0, new_h / 2.0), angle, 1.0)
    rx, ry = M @ np.array([point[0] * k, point[1] * k, 1.0])
    cx, cy = rx + paste_x, ry + paste_y
    return {"cx": float(cx), "cy": float(cy),
            "from_right": float((m1w - 1) - cx), "from_top": float(cy),
            "coarse_score": coarse_score, "fine_score": fine_score}


def draw_m1_point(m1: Image.Image, pt: dict) -> Image.Image:
    """Return a copy of m1 with the mapped point marked by a red cross."""
    arr = np.array(m1.convert("RGB"))
    cv2.drawMarker(arr, (int(round(pt["cx"])), int(round(pt["cy"]))), (255, 0, 0), cv2.MARKER_CROSS, 25, 2)
    return Image.fromarray(arr)


def save_results(results: list, out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    mag_lines = []
    center_lines = ["image\tmag\tsource\tcx\tcy\tfrom_right\tfrom_top\tw\th\tscore"]
    m1_lines = ["image\tmag\tmatch\tm1_cx\tm1_cy\tfrom_right\tfrom_top\tangle\tcoarse\tfine\treliable"]

    for fname, t1, m1, mag, pos, coarse_score, best_angle, fine_score, fine_x, fine_y, match_img, t1s_img, m1s_img, t1_local, thumb_match_img, score_map_img, matched, elapsed in results:
        stem = os.path.splitext(os.path.basename(fname))[0]
        t1.save(os.path.join(out_dir, f"{stem}_t1.png"))
        m1.save(os.path.join(out_dir, f"{stem}_m1.png"))
        match_img.save(os.path.join(out_dir, f"{stem}_match.png"))

        match_label = "matched" if matched else "no_match"

        # Centre of the white rectangle in t1 (or the middle of t1 if no rectangle is visible)
        rect = find_t1_rect_center(t1)
        draw_t1_rect(t1, rect).save(os.path.join(out_dir, f"{stem}_t1_center.png"))
        rw, rh = (rect["w"], rect["h"]) if rect["source"] == "rectangle" else ("", "")
        center_lines.append(f"{stem}\t{mag}\t{rect['source']}\t{rect['cx']:.1f}\t{rect['cy']:.1f}\t{rect['from_right']:.1f}\t{rect['from_top']:.1f}\t{rw}\t{rh}\t{rect['score']:.1f}")

        # Same point located in m1 via the fine match (t1 scaled, rotated and shifted onto m1)
        pt = t1_point_to_m1(t1, t1_local, m1, fine_x, fine_y, best_angle, (rect["cx"], rect["cy"]), coarse_score, fine_score)
        draw_m1_point(m1, pt).save(os.path.join(out_dir, f"{stem}_m1_center.png"))
        inside = 0 <= pt["cx"] < m1.width and 0 <= pt["cy"] < m1.height
        reliable = "yes" if (matched and fine_score >= M1_POINT_MIN_FINE and inside) else "no"
        m1_lines.append(f"{stem}\t{mag}\t{match_label}\t{pt['cx']:.1f}\t{pt['cy']:.1f}\t{pt['from_right']:.1f}\t{pt['from_top']:.1f}\t{best_angle:.1f}\t{pt['coarse_score']:.4f}\t{pt['fine_score']:.4f}\t{reliable}")

        mag_lines.append(f"{stem}\t{mag}\tx={fine_x:.2f}\ty={fine_y:.2f}\tcoarse={coarse_score:.4f}\tangle={best_angle:.1f}\tfine={fine_score:.4f}\ttime={elapsed:.2f}s\t{match_label}")

    with open(os.path.join(out_dir, "magnification.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(mag_lines) + "\n")

    with open(os.path.join(out_dir, "t1_center.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(center_lines) + "\n")

    with open(os.path.join(out_dir, "m1_center.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(m1_lines) + "\n")


# # Execution Cell
# Runs the pipeline over the dataset folder and prints output logs. `PY`

# In[32]:


output_dir = os.path.join(input_base, "output")


def run_pipeline():

    project_root = input_base

    src_dir = os.path.join(project_root, "input")
    paths = sorted(glob.glob(os.path.join(src_dir, "cdsem*.png")) + glob.glob(os.path.join(src_dir, "cdsem*.jpg")))

    if not paths:
        print(f"No cdsem*.png/jpg image paths found under {src_dir}.")
        return

    print(f"Found project folder at: {project_root}")
    print(f"Processing {len(paths)} image samples...")

    hold_bgr, mag_bgr = load_anchors(project_root)
    cursor_rgba = load_cursor(project_root)

    results = []
    for p in paths:
        t0 = time.perf_counter()
        try:
            t1, m1, mag, pos, coarse_score, best_angle, fine_score, fine_x, fine_y, match_img, t1s_img, m1s_img, t1_local, thumb_match_img, score_map_img = process_image(p, hold_bgr, mag_bgr, cursor_rgba)
        except Exception as e:
            print(f"FAILED {os.path.basename(p)}: {e}")
            continue
        elapsed = time.perf_counter() - t0
        matched = determine_match(coarse_score, fine_score, _mag_to_x(mag)) == "match"

        print(f"Processed {os.path.basename(p)}: Mag={mag} | Coarse Score={coarse_score:.3f} | Fine Score={fine_score:.3f} | Matched={matched}")
        results.append((p, t1, m1, mag, pos, coarse_score, best_angle, fine_score, fine_x, fine_y, match_img, t1s_img, m1s_img, t1_local, thumb_match_img, score_map_img, matched, elapsed))

    save_results(results, output_dir)
    print(f"Results successfully saved to {output_dir}")


# In[33]:


if __name__ == "__main__":
    run_pipeline()

