"""Train/calibrate the AOI classifier from folder-labeled data.

Folder layout (adapter):
    <root>/contact/*.{png,jpg}         -> label: Contact  (Down)
    <root>/non-contact/*.{png,jpg}     -> label: Non-contact (Up)

Picks the ROI that maximises mean(contact_lap) - mean(non_contact_lap)
while keeping NCC(sample non-contact, sample contact template) < ncc_max.
Saves template and calibration.json for the API to consume.
"""
import argparse
import glob
import json
import os

import cv2
import numpy as np


def load_images(folder):
    paths = sorted(glob.glob(os.path.join(folder, "*.png")) +
                   glob.glob(os.path.join(folder, "*.jpg")))
    imgs = []
    for p in paths:
        im = cv2.imread(p)
        if im is not None:
            imgs.append((p, im))
    return imgs


def lap_var(roi):
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    return float(cv2.Laplacian(blurred, cv2.CV_64F).var())


def crop_pct(img, rx1, ry1, rx2, ry2):
    h, w = img.shape[:2]
    x1, y1 = int(w * rx1), int(h * ry1)
    x2, y2 = int(w * rx2), int(h * ry2)
    return img[y1:y2, x1:x2]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--contact-dir", required=True)
    ap.add_argument("--non-contact-dir", required=True)
    ap.add_argument("--category", default="02_Series",
                    help="Category name — template is saved as template_<category>.jpg")
    ap.add_argument("--output-dir", default="./local_output")
    ap.add_argument("--step", type=float, default=0.05)
    ap.add_argument("--rx-range", nargs=2, type=float, default=[0.05, 0.90])
    ap.add_argument("--ry-range", nargs=2, type=float, default=[0.05, 0.90])
    ap.add_argument("--min-size", type=float, default=0.05,
                    help="Minimum ROI side as a fraction of image.")
    ap.add_argument("--ncc-max", type=float, default=0.50,
                    help="Non-contact sample vs contact template NCC must stay below this.")
    args = ap.parse_args()

    tpl_dir = os.path.join(args.output_dir, "templates")
    os.makedirs(tpl_dir, exist_ok=True)

    contacts = load_images(args.contact_dir)
    non_contacts = load_images(args.non_contact_dir)
    print(f"Loaded {len(contacts)} contact, {len(non_contacts)} non-contact images.")
    if not contacts or not non_contacts:
        raise SystemExit("Need at least one image in each folder.")

    # Candidate grid
    starts_x = np.arange(args.rx_range[0], args.rx_range[1] + 1e-9, args.step)
    starts_y = np.arange(args.ry_range[0], args.ry_range[1] + 1e-9, args.step)
    ends_x = np.arange(args.rx_range[0] + args.min_size, args.rx_range[1] + args.step, args.step)
    ends_y = np.arange(args.ry_range[0] + args.min_size, args.ry_range[1] + args.step, args.step)

    sample_c_img = contacts[0][1]
    sample_nc_img = non_contacts[0][1]

    best = {"diff": -float("inf"), "box": None, "mean_c": None, "mean_nc": None, "ncc_nc": None}
    checked = 0
    total = len(starts_x) * len(starts_y) * len(ends_x) * len(ends_y)
    print(f"Grid upper bound: {total:,} combos (many pruned).")

    for rx1 in starts_x:
        for ry1 in starts_y:
            for rx2 in ends_x:
                if rx2 - rx1 < args.min_size:
                    continue
                for ry2 in ends_y:
                    if ry2 - ry1 < args.min_size:
                        continue

                    # Laplacian variance over all images
                    c_scores = []
                    for _, im in contacts:
                        roi = crop_pct(im, rx1, ry1, rx2, ry2)
                        if roi.size == 0:
                            continue
                        c_scores.append(lap_var(roi))
                    nc_scores = []
                    for _, im in non_contacts:
                        roi = crop_pct(im, rx1, ry1, rx2, ry2)
                        if roi.size == 0:
                            continue
                        nc_scores.append(lap_var(roi))

                    if not c_scores or not nc_scores:
                        continue
                    mean_c = float(np.mean(c_scores))
                    mean_nc = float(np.mean(nc_scores))
                    diff = mean_c - mean_nc
                    checked += 1

                    if diff <= best["diff"]:
                        continue  # fast reject

                    # NCC sanity: non-contact sample should NOT match contact template well
                    tpl = cv2.cvtColor(crop_pct(sample_c_img, rx1, ry1, rx2, ry2), cv2.COLOR_BGR2GRAY)
                    nc_roi = cv2.cvtColor(crop_pct(sample_nc_img, rx1, ry1, rx2, ry2), cv2.COLOR_BGR2GRAY)
                    if tpl.size == 0 or nc_roi.size == 0:
                        continue
                    if tpl.shape[0] > nc_roi.shape[0] or tpl.shape[1] > nc_roi.shape[1]:
                        continue
                    res = cv2.matchTemplate(nc_roi, tpl, cv2.TM_CCOEFF_NORMED)
                    _, ncc_nc, _, _ = cv2.minMaxLoc(res)
                    ncc_nc = float(ncc_nc)
                    if ncc_nc >= args.ncc_max:
                        continue

                    best.update(diff=diff, box=(round(float(rx1), 3), round(float(ry1), 3),
                                                round(float(rx2), 3), round(float(ry2), 3)),
                                mean_c=mean_c, mean_nc=mean_nc, ncc_nc=ncc_nc,
                                c_scores=c_scores, nc_scores=nc_scores)

    print(f"Combos evaluated (passed geometry prune): {checked:,}")
    if best["box"] is None:
        raise SystemExit("No ROI satisfied the constraints. Try widening the grid or raising --ncc-max.")

    rx1, ry1, rx2, ry2 = best["box"]
    print(f"\nBest ROI for [{args.category}]: ({rx1}, {ry1}, {rx2}, {ry2})")
    print(f"  mean_lap(contact)     = {best['mean_c']:.2f}")
    print(f"  mean_lap(non-contact) = {best['mean_nc']:.2f}")
    print(f"  diff                  = {best['diff']:.2f}")
    print(f"  sample NCC(non-contact vs contact-template) = {best['ncc_nc']:.4f}")

    # Decision threshold: midpoint between the two cluster means (simple, calibrated single-image threshold)
    lap_threshold = round((best["mean_c"] + best["mean_nc"]) / 2.0, 2)
    print(f"  chosen single-image lap threshold = {lap_threshold}")

    # Save template from the first contact image
    tpl_bgr = crop_pct(sample_c_img, rx1, ry1, rx2, ry2)
    tpl_path = os.path.join(tpl_dir, f"template_{args.category}.jpg")
    cv2.imwrite(tpl_path, tpl_bgr)
    print(f"  template saved -> {tpl_path}  (size={tpl_bgr.shape[:2]})")

    # Save calibration JSON
    calib_path = os.path.join(args.output_dir, "calibration.json")
    existing = {}
    if os.path.exists(calib_path):
        try:
            with open(calib_path) as f:
                existing = json.load(f)
        except Exception:
            existing = {}
    existing[args.category] = {
        "rx1": rx1, "ry1": ry1, "rx2": rx2, "ry2": ry2,
        "lap_threshold": lap_threshold,
        "ncc_threshold": 0.50,
        "mean_lap_contact": round(best["mean_c"], 2),
        "mean_lap_non_contact": round(best["mean_nc"], 2),
        "n_contact": len(contacts),
        "n_non_contact": len(non_contacts),
    }
    with open(calib_path, "w") as f:
        json.dump(existing, f, indent=2)
    print(f"  calibration -> {calib_path}")

    # Per-image evaluation at the chosen ROI + threshold
    print("\nPer-image evaluation at best ROI:")
    tpl_gray = cv2.cvtColor(tpl_bgr, cv2.COLOR_BGR2GRAY)
    correct = 0
    total_imgs = 0
    for folder_label, imgs, truth in [("contact", contacts, True), ("non-contact", non_contacts, False)]:
        print(f"\n  [{folder_label}]")
        for p, im in imgs:
            roi = crop_pct(im, rx1, ry1, rx2, ry2)
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            lap = lap_var(roi)
            ncc = 0.0
            if tpl_gray.shape[0] <= gray.shape[0] and tpl_gray.shape[1] <= gray.shape[1]:
                r = cv2.matchTemplate(gray, tpl_gray, cv2.TM_CCOEFF_NORMED)
                _, ncc, _, _ = cv2.minMaxLoc(r)
                ncc = float(ncc)
            pred = (lap >= lap_threshold) and (ncc >= 0.50)
            ok = (pred == truth)
            correct += int(ok)
            total_imgs += 1
            print(f"    {os.path.basename(p):<22} | lap={lap:7.2f} | ncc={ncc:+.4f} | "
                  f"pred={'Contact' if pred else 'Non-contact':<12} | {'OK ' if ok else 'MISS'}")
    print(f"\nAccuracy: {correct}/{total_imgs} = {100*correct/total_imgs:.1f}%")


if __name__ == "__main__":
    main()
