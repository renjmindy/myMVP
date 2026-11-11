"""Batch-scan a folder of RCM screenshots through the v2 (dual-ROI OR) AOI API
and print per-image per-ROI KPIs + overall decision.

The API resizes internally to 1280×1024, crops left + right ROIs, runs the
logistic model on each, and reports both statuses plus the OR-aggregated
overall verdict. This scanner just forwards each file and prints the summary.

Usage:
    # Scan a folder of RCM snapshots (any resolution; API will resize)
    python scan_batch.py samples/

    # Hit a non-local API
    python scan_batch.py samples/ --url http://192.168.137.101:8000

    # Save per-image results (including both saved-image URLs) to CSV
    python scan_batch.py samples/ --csv results.csv

    # Report accuracy if files live in labeled subfolders ./contact/ + ./non-contact/
    python scan_batch.py labeled_root/ --labeled
"""
import argparse
import csv
import glob
import os
import sys
import time

import requests


IMG_GLOBS = ("*.png", "*.jpg", "*.jpeg", "*.bmp", "*.PNG", "*.JPG", "*.JPEG", "*.BMP")


def fetch_config(base_url: str) -> dict:
    r = requests.get(f"{base_url.rstrip('/')}/api/v1/config", timeout=5)
    r.raise_for_status()
    return r.json()


def post_predict(base_url: str, img_path: str, timeout_s: float) -> dict:
    with open(img_path, "rb") as fh:
        mime = "image/png" if img_path.lower().endswith(".png") else "image/jpeg"
        r = requests.post(
            f"{base_url.rstrip('/')}/api/v1/predict",
            files={"file": (os.path.basename(img_path), fh, mime)},
            timeout=timeout_s,
        )
    r.raise_for_status()
    return r.json()


def discover_files(root: str, labeled: bool):
    if labeled:
        out = []
        for lbl, sub in (("contact", "contact"), ("non_contact", "non-contact")):
            d = os.path.join(root, sub)
            if os.path.isdir(d):
                for g in IMG_GLOBS:
                    out += [(p, lbl) for p in glob.glob(os.path.join(d, g))]
        return sorted(out, key=lambda x: x[0])
    files = []
    for g in IMG_GLOBS:
        files += glob.glob(os.path.join(root, g))
    return sorted((f, None) for f in files)


def main():
    ap = argparse.ArgumentParser(description="Batch-scan images through the v2 dual-ROI AOI API.")
    ap.add_argument("path", help="Folder of RCM screenshots to scan")
    ap.add_argument("--url", default="http://localhost:8000",
                    help="Base URL of the AOI API (default: http://localhost:8000)")
    ap.add_argument("--timeout", type=float, default=5.0,
                    help="HTTP timeout seconds (default: 5)")
    ap.add_argument("--csv", default=None, help="Save per-image results to this CSV path")
    ap.add_argument("--labeled", action="store_true",
                    help="Treat 'path' as containing ./contact/ and ./non-contact/ subfolders")
    args = ap.parse_args()

    base_url = args.url
    try:
        cfg = fetch_config(base_url)
    except Exception as e:
        print(f"ERROR: cannot reach {base_url}/api/v1/config  ->  {e}", file=sys.stderr)
        sys.exit(2)

    lroi = cfg["reference_roi_left"]; rroi = cfg["reference_roi_right"]
    resize = cfg.get("input_resize", {})
    print(f"AOI API      : {base_url}")
    print(f"variant      : {cfg.get('variant', '?')}  aggregation={cfg.get('aggregation', '?')}")
    print(f"input resize : {resize.get('width')}×{resize.get('height')}")
    print(f"LEFT  ROI    : ({lroi['rx1']}, {lroi['ry1']}, {lroi['rx2']}, {lroi['ry2']})")
    print(f"RIGHT ROI    : ({rroi['rx1']}, {rroi['ry1']}, {rroi['rx2']}, {rroi['ry2']})")

    files = discover_files(args.path, args.labeled)
    if not files:
        print(f"No images found under {args.path}", file=sys.stderr); sys.exit(1)
    print(f"files found  : {len(files)}\n")

    header = (f"{'file':<42} "
              f"{'OVERALL':<12} {'p(c)':>6} | "
              f"{'LEFT':<12} {'L_p':>6}  {'R':<12} {'R_p':>6} | "
              f"{'ms':>6}")
    if args.labeled:
        header += "  truth       match"
    print(header)
    print("-" * len(header))

    rows = []
    tp = fp = tn = fn = 0
    total_ms = 0.0
    errors = 0
    for path, truth in files:
        t0 = time.perf_counter()
        try:
            resp = post_predict(base_url, path, args.timeout)
        except Exception as e:
            print(f"{os.path.basename(path):<42} HTTP ERROR  {e}")
            errors += 1
            continue
        dt_ms = (time.perf_counter() - t0) * 1000.0
        total_ms += dt_ms

        L = resp["per_roi"]["left"]; R = resp["per_roi"]["right"]
        line = (f"{os.path.basename(path):<42} "
                f"{resp['status']:<12} {resp['probability_contact']:>6.3f} | "
                f"{L['status']:<12} {L['probability_contact']:>6.3f}  "
                f"{R['status']:<12} {R['probability_contact']:>6.3f} | "
                f"{dt_ms:>6.1f}")
        if args.labeled and truth is not None:
            is_c = resp["status"] == "contact"
            is_t = truth == "contact"
            match = "OK " if is_c == is_t else "MISS"
            line += f"  {truth:<10}  {match}"
            if is_t and is_c: tp += 1
            elif is_t and not is_c: fn += 1
            elif not is_t and is_c: fp += 1
            else: tn += 1
        print(line)
        rows.append({
            "file": os.path.basename(path),
            "status": resp["status"],
            "probability_contact": resp["probability_contact"],
            "aggregation": resp.get("aggregation"),
            "left_status": L["status"],   "left_prob":  L["probability_contact"],
            "right_status": R["status"],  "right_prob": R["probability_contact"],
            "left_lap_var":  L["features"].get("lap_var"),
            "right_lap_var": R["features"].get("lap_var"),
            "roi_image": resp.get("roi_image"),
            "fullframe_image": resp.get("fullframe_image"),
            "latency_ms": round(dt_ms, 1),
            "truth": truth,
        })

    n = len(rows)
    print("-" * len(header))
    c = sum(1 for r in rows if r["status"] == "contact")
    nc = sum(1 for r in rows if r["status"] == "non_contact")
    avg_ms = total_ms / n if n else 0
    print(f"\nscanned      : {n}   contact: {c}   non_contact: {nc}   errors: {errors}")
    print(f"avg latency  : {avg_ms:.1f} ms")
    if args.labeled and (tp + fp + tn + fn) > 0:
        total = tp + fp + tn + fn
        acc = (tp + tn) / total
        print(f"accuracy     : {tp+tn}/{total} = {acc*100:.1f}%   TP={tp} TN={tn} FP={fp} FN={fn}")

    if args.csv:
        fieldnames = ["file", "status", "probability_contact", "aggregation",
                      "left_status", "left_prob", "right_status", "right_prob",
                      "left_lap_var", "right_lap_var",
                      "roi_image", "fullframe_image", "latency_ms", "truth"]
        with open(args.csv, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            for r in rows:
                w.writerow(r)
        print(f"\nCSV saved -> {args.csv}")


if __name__ == "__main__":
    main()
