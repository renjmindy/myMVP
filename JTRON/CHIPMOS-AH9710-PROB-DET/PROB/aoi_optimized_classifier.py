import cv2
import glob
import os
import numpy as np
from PIL import Image

# 1. 替換為您本機實際存放圖片的資料夾路徑 (例如您的 dat 資料夾)
dataset_dir = os.environ.get("DATASET_DIR", "./input")  # 依照您的環境調整路徑
test_images = glob.glob(os.path.join(dataset_dir, "**", "*.jpg"), recursive=True)
if not test_images:
    test_images = glob.glob("*.jpg") + glob.glob("*.png")

print(f"總共找到 {len(test_images)} 張測試圖片")

# 2. 確保本機的輸出與儲存資料夾存在
working_dir = "./local_output"  # 改為本機資料夾
diff_output_dir = os.path.join(working_dir, "category_grid_samples")
template_dir = os.path.join(working_dir, "templates")
os.makedirs(diff_output_dir, exist_ok=True)
os.makedirs(template_dir, exist_ok=True)

# 3. 自動過濾取得 Down 與 Up 圖片 (不分大小寫)
down_images = [
    img for img in test_images if "down" in os.path.basename(img).lower()
]
up_images = [
    img for img in test_images if "up" in os.path.basename(img).lower()
]

print(f"成功抓取到 Down 圖片: {len(down_images)} 張")
print(f"成功抓取到 Up 圖片: {len(up_images)} 張")

# 4. 定義類別群組、各自專屬的網格搜尋範圍，以及【獨立的門檻值 min_diff】
categories = {
    "01_Series": {
        "down": [img for img in down_images if "01" in os.path.basename(img)],
        "up": [img for img in up_images if "01" in os.path.basename(img)],
        "rx1_cand": np.arange(0.55, 0.90, 0.05),
        "ry1_cand": np.arange(0.55, 0.90, 0.05),
        "rx2_cand": np.arange(0.60, 0.95, 0.05),
        "ry2_cand": np.arange(0.60, 0.95, 0.05),
        "min_diff": 50.0,
    },
    "02_Series": {
        "down": [img for img in down_images if "02" in os.path.basename(img)],
        "up": [img for img in up_images if "02" in os.path.basename(img)],
        "rx1_cand": np.arange(0.20, 0.40, 0.05),
        "ry1_cand": np.arange(0.20, 0.90, 0.05),
        "rx2_cand": np.arange(0.25, 0.45, 0.05),
        "ry2_cand": np.arange(0.25, 0.95, 0.05),
        "min_diff": 15.0,
    },
}

# 5. 針對每個類別分別執行獨立的網格搜尋與雙指標評估
for cat_name, data in categories.items():
    target_diff = data["min_diff"]
    print(f"\n=== 開始進行 [{cat_name}] 的獨立網格搜尋 (目標: diff >= {target_diff}) ===")
    d_imgs = data["down"]
    u_imgs = data["up"]

    if not d_imgs or not u_imgs:
        print(f"[{cat_name}] 找不到對應的圖片樣本，跳過。")
        continue

    best_score_diff = -float("inf")
    best_box = None
    checked_count = 0

    rx1_c = data["rx1_cand"]
    ry1_c = data["ry1_cand"]
    rx2_c = data["rx2_cand"]
    ry2_c = data["ry2_cand"]

    total_combos = len(rx1_c) * len(ry1_c) * len(rx2_c) * len(ry2_c)
    print(f"[{cat_name}] 預計測試組合數: {total_combos:,} 種")

    for rx1 in rx1_c:
        for ry1 in ry1_c:
            for rx2 in rx2_c:
                for ry2 in ry2_c:
                    if (
                        rx2 <= rx1
                        or ry2 <= ry1
                        or (rx2 - rx1) < 0.05
                        or (ry2 - ry1) < 0.05
                    ):
                        continue

                    box = (round(rx1, 2), round(ry1, 2), round(rx2, 2), round(ry2, 2))

                    down_scores = []
                    for fname in d_imgs:
                        img_bgr = cv2.imread(fname)
                        if img_bgr is None:
                            continue
                        h, w = img_bgr.shape[:2]
                        x1, y1 = int(w * rx1), int(h * ry1)
                        x2, y2 = int(w * rx2), int(h * ry2)
                        roi = img_bgr[y1:y2, x1:x2]
                        if roi.size == 0:
                            continue
                        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
                        score = cv2.Laplacian(blurred, cv2.CV_64F).var()
                        down_scores.append(score)

                    up_scores = []
                    for fname in u_imgs:
                        img_bgr = cv2.imread(fname)
                        if img_bgr is None:
                            continue
                        h, w = img_bgr.shape[:2]
                        x1, y1 = int(w * rx1), int(h * ry1)
                        x2, y2 = int(w * rx2), int(h * ry2)
                        roi = img_bgr[y1:y2, x1:x2]
                        if roi.size == 0:
                            continue
                        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
                        score = cv2.Laplacian(blurred, cv2.CV_64F).var()
                        up_scores.append(score)

                    if not down_scores or not up_scores:
                        continue

                    mean_down = np.mean(down_scores)
                    mean_up = np.mean(up_scores)
                    diff = mean_down - mean_up
                    checked_count += 1

                    d_sample_img = cv2.imread(d_imgs[0])
                    u_sample_img = cv2.imread(u_imgs[0])
                    ncc_d_score, ncc_u_score = 1.0, 0.0

                    if d_sample_img is not None and u_sample_img is not None:
                        h, w = d_sample_img.shape[:2]
                        x1, y1, x2, y2 = int(w * rx1), int(h * ry1), int(w * rx2), int(h * ry2)
                        template_curr = d_sample_img[y1:y2, x1:x2]
                        roi_up_curr = u_sample_img[y1:y2, x1:x2]

                        if template_curr.size > 0 and roi_up_curr.size > 0:
                            tpl_gray = cv2.cvtColor(template_curr, cv2.COLOR_BGR2GRAY)
                            roi_d_gray = cv2.cvtColor(template_curr, cv2.COLOR_BGR2GRAY)
                            roi_u_gray = cv2.cvtColor(roi_up_curr, cv2.COLOR_BGR2GRAY)

                            res_d = cv2.matchTemplate(roi_d_gray, tpl_gray, cv2.TM_CCOEFF_NORMED)
                            _, ncc_d_score, _, _ = cv2.minMaxLoc(res_d)

                            if tpl_gray.shape[0] <= roi_u_gray.shape[0] and tpl_gray.shape[1] <= roi_u_gray.shape[1]:
                                res_u = cv2.matchTemplate(roi_u_gray, tpl_gray, cv2.TM_CCOEFF_NORMED)
                                _, ncc_u_score, _, _ = cv2.minMaxLoc(res_u)

                    is_valid_candidate = (diff >= target_diff) and (ncc_u_score < 0.50)

                    if is_valid_candidate:
                        coord_suffix = f"{cat_name}_diff_{diff:.2f}_nccU_{ncc_u_score:.2f}_r_{rx1:.2f}_{ry1:.2f}_{rx2:.2f}_{ry2:.2f}"

                        if d_sample_img is not None:
                            h, w = d_sample_img.shape[:2]
                            roi_d = d_sample_img[int(h * ry1) : int(h * ry2), int(w * rx1) : int(w * rx2)]
                            if roi_d.size > 0:
                                cv2.imwrite(os.path.join(diff_output_dir, f"roi_DOWN_{coord_suffix}.jpg"), roi_d)

                        if u_sample_img is not None:
                            h, w = u_sample_img.shape[:2]
                            roi_u = u_sample_img[int(h * ry1) : int(h * ry2), int(w * rx1) : int(w * rx2)]
                            if roi_u.size > 0:
                                cv2.imwrite(os.path.join(diff_output_dir, f"roi_UP_{coord_suffix}.jpg"), roi_u)

                    if is_valid_candidate and (diff > best_score_diff):
                        best_score_diff = diff
                        best_box = box

    print(f"\n--- [{cat_name}] 最佳化搜尋完成 ---")
    if best_box:
        print(f"[{cat_name}] 最佳 ROI 比例座標: {best_box}")
        print(f"[{cat_name}] 最大化分數差 (Down - Up): {best_score_diff:.2f}")

        rx1, ry1, rx2, ry2 = best_box
        for sample_type, sample_path in [("DOWN", d_imgs[0]), ("UP", u_imgs[0])]:
            img = cv2.imread(sample_path)
            if img is not None:
                h, w = img.shape[:2]
                best_roi = img[int(h * ry1) : int(h * ry2), int(w * rx1) : int(w * rx2)]
                cv2.imwrite(os.path.join(working_dir, f"best_roi_{cat_name}_{sample_type}.jpg"), best_roi)
        print(f"[{cat_name}] 已儲存最佳代表圖至 {working_dir}/best_roi_{cat_name}_*.jpg")

        sample_down_img = cv2.imread(d_imgs[0])
        h, w = sample_down_img.shape[:2]
        template = sample_down_img[int(h * ry1) : int(h * ry2), int(w * rx1) : int(w * rx2)]
        cv2.imwrite(os.path.join(template_dir, f"template_{cat_name}.jpg"), template)

        all_images = [(f, "Down (Contact)") for f in d_imgs] + [(f, "Up (Non-contact)") for f in u_imgs]
        print(f"\n[{cat_name}] 最終雙指標綜合評估：")
        print("-" * 90)
        for fname, ground_truth in all_images:
            img_bgr = cv2.imread(fname)
            if img_bgr is None:
                continue
            roi = img_bgr[int(h * ry1) : int(h * ry2), int(w * rx1) : int(w * rx2)]
            if roi.size == 0:
                continue

            gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            lap_score = cv2.Laplacian(cv2.GaussianBlur(gray_roi, (5, 5), 0), cv2.CV_64F).var()

            tpl_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
            if tpl_gray.shape[0] > gray_roi.shape[0] or tpl_gray.shape[1] > gray_roi.shape[1]:
                ncc_score = 0.0
            else:
                match_result = cv2.matchTemplate(gray_roi, tpl_gray, cv2.TM_CCOEFF_NORMED)
                _, ncc_score, _, _ = cv2.minMaxLoc(match_result)

            print(f"檔案: {os.path.basename(fname):<20} | 標籤: {ground_truth:<16} | 拉普拉斯分數: {lap_score:6.2f} | NCC 分數: {ncc_score:.4f}")
        print("-" * 90)
    else:
        print(f"[{cat_name}] 在目前的候選範圍內未找到滿足雙重門檻條件的組合。")
