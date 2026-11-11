# AH9710 AOI-API v3 — 開發者 Package（central ROI, overlay-removed）

v1 的另一個進化版本：**先把 AOI 機器 UI 的藍色外框與白色十字線拿掉**，再把 ROI 擺在**中央區域**做判定。想法是：讓 classifier 看到的 ROI 幾乎只剩下 probe / die 的內容，不被量測軟體的 UI overlay 干擾。

- **服務 port**：`8000`（可透過 `config/aoi_api.json` 調整）
- **模型**：以 5 個低成本影像特徵（`lap_var`, `grad_mag`, `edge_den`, `mean`, `std`）為輸入的 logistic regression
- **判定規則**：`probability_contact >= 0.5` 判為 `contact`
- **Reference ROI（central）**：`rx1=0.30, ry1=0.35, rx2=0.75, ry2=0.80`
- **內部 resize**：**1280 × 1024**
- **Overlay 移除**：啟用（詳見 §4）
- **24 張 labeled data 準確率**：**100%**（min decision margin 0.29）

---

## 1. 這個 Package 的內容

```
aoi-api-package_v3/
├── prob_api.py            # FastAPI 服務本體 (v9.0, central ROI + overlay removal)
├── config/
│   └── aoi_api.json       # 新增 overlay_removal 區塊（見 §4）
├── local_output/
│   ├── calibration.json   # v3 專用模型（在 1280×1024 的 cleaned central ROI 上訓練）
│   ├── contact/           # contact 判定：cleaned 原圖 + cropped crop
│   └── non-contact/       # non_contact 判定：僅 cleaned 原圖
├── logs/
│   └── aoi_api.log        # 每次 predict 的 JSON Lines 紀錄
├── requirements.txt
├── scan_batch.py          # CLI 工具（與 v1 相同的 response shape，可直接用）
├── samples/
│   ├── contact.png            # 完整 1540×1050 RCM 截圖（contact）
│   └── non_contact.png        # 完整 1540×1050 RCM 截圖（non_contact）
├── README.md              # 本文件
└── README.html            # 本文件的 HTML 版
```

---

## 2. 安裝與啟動

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python prob_api.py          # 讀 config/aoi_api.json，預設 port 8000
```

Health 檢查：`GET http://localhost:8000/api/v1/health` 應回：
```json
{"status":"ok","service":"aoi-api","version":"9.0","variant":"central-roi-overlay-removed","calibrated":true}
```

Swagger UI：`http://localhost:8000/docs`

---

## 3. 整體資料流

```
RCM 相機（任意解析度）
   │ snapshot
   ▼
POST /api/v1/predict  multipart file=<整張 RCM>
   │
   ▼
AOI API v3
   │ 1. 讀入 → resize 到 1280 × 1024
   │ 2. 偵測 AOI 機器 UI overlay：
   │       - 藍/青色像素（B − R > 25，對外框、內框、cyan teal 框都有效）
   │       - 白色十字線（亮度 > 180 且形成長 run）
   │    → 用 cv2.inpaint 填補
   │ 3. 依 reference_roi (0.30, 0.35, 0.75, 0.80) 裁出中央 crop (576 × 461)
   │ 4. 算 5 個特徵 → logistic → status
   │ 5. 存檔：
   │    每次都存 <timestamp>.jpg ← **cleaned** 1280×1024 原圖 + 黃色 ROI 外框
   │         - contact      → ./local_output/contact/
   │         - non_contact  → ./local_output/non-contact/
   │    僅 contact 多存：cropped_<timestamp>.jpg ← 中央 crop
   │ 6. 寫一行 JSON Lines 到 ./logs/aoi_api.log
   │ 7. 回傳 JSON
   ▼
monitor 依 response 更新 Redis / LED、Web UI 依 `roi_image` 顯示
```

**為什麼要去 overlay？** AOI 機器的 UI 本身會在畫面上畫一個藍/青色框（固定位置）和白色十字線。這些東西對 contact 判定毫無意義，但 Laplacian / Sobel / Canny 會把它們當成強邊緣，拉高 `lap_var` / `grad_mag` / `edge_den`，可能讓 non_contact 影像也被誤判為 contact。v3 先把它們擦掉，讓 classifier 只看 probe / die 的訊號。

---

## 4. 設定檔 `config/aoi_api.json`

v3 比 v1 多一個 `overlay_removal` 區塊。其他設定意義不變。

```json
{
  "server": {
    "host": "0.0.0.0",
    "port": 8000
  },
  "paths": {
    "calibration_json": "./local_output/calibration.json",
    "contact_dir": "./local_output/contact",
    "non_contact_dir": "./local_output/non-contact",
    "log_dir": "./logs"
  },
  "logging": {
    "level": "INFO",
    "filename": "aoi_api.log",
    "rotation": "daily",
    "backup_count": 7
  },
  "input_resize": {
    "width": 1280,
    "height": 1024
  },
  "overlay_removal": {
    "enabled": true,
    "blue_delta": 25,
    "cross_brightness": 180,
    "cross_min_run": 20,
    "inpaint_radius": 3
  }
}
```

### overlay_removal 欄位

| 欄位 | 說明 |
|---|---|
| `enabled` | 設 `false` 可完全關掉 overlay removal（例如除錯、或換成沒有 UI 的 raw snapshot） |
| `blue_delta` | 當某像素 `blue − red > blue_delta` 即判為 overlay 的一部分。預設 25。值太低 → 把正常 probe 內容也當 overlay；值太高 → 抓不到淡藍色的細框 |
| `cross_brightness` | 白色十字線的亮度下限。預設 180。probe tips 的亮度約 100–160，所以 180 可以避開它們 |
| `cross_min_run` | 白色連續像素長度 ≥ 這個值才判為十字線。預設 20 |
| `inpaint_radius` | `cv2.inpaint` 的 radius 參數。預設 3 |

**改任何欄位都要重新校正**（§10），因為特徵分布會跟著變。

---

## 5. Log 紀錄（JSON Lines）

與 v1 相同——每次 predict 一行 JSON，每日午夜輪替。`startup` 事件額外紀錄 `variant` 與 `overlay_removal` 設定，讓之後排查時知道當時服務的 overlay 參數。

**Predict 事件格式範例**：

```json
{
  "ts": "2026-11-11T14:20:55.999",
  "level": "INFO",
  "event": "predict",
  "filename": "contact.png",
  "status": "contact",
  "roi_image": "/local_output/contact/cropped_20261111_142055_999.jpg",
  "fullframe_image": "/local_output/contact/20261111_142055_999.jpg",
  "laplacian_score": 11.78,
  "probability_contact": 0.7912,
  "features": {"lap_var":11.7824,"mean":36.2945,"std":25.6104,"edge_den":0.0076,"grad_mag":21.0901},
  "latency_ms": 85.3
}
```

**注意**：feature 數值的絕對範圍跟 v1 / v2 不同（因為是在**去除 overlay 後**的 central ROI 上算的），所以 v3 的 log 不能跟 v1 / v2 的 log 直接比較。要比較不同版本的話，看 `probability_contact` 和 `status`，不要看 raw features。

---

## 6. HTTP endpoints

### `GET /api/v1/health`

```json
{
  "status": "ok",
  "service": "aoi-api",
  "version": "9.0",
  "variant": "central-roi-overlay-removed",
  "calibrated": true
}
```

### `GET /api/v1/config`

```json
{
  "variant": "central-roi-overlay-removed",
  "input_resize": { "width": 1280, "height": 1024 },
  "overlay_removal": { "enabled": true, "blue_delta": 25, "cross_brightness": 180, "cross_min_run": 20, "inpaint_radius": 3 },
  "reference_roi": { "rx1": 0.30, "ry1": 0.35, "rx2": 0.75, "ry2": 0.80 },
  "model": "logistic",
  "features": ["lap_var", "mean", "std", "edge_den", "grad_mag"],
  "decision_threshold": 0.5,
  "trained_on": {
    "n_contact": 10, "n_non_contact": 14,
    "resolution": {"width":1280,"height":1024},
    "overlay_removal": true
  }
}
```

### `POST /api/v1/predict`

`multipart/form-data`，單一欄位 `file`。上傳 **完整 RCM 截圖**（任意解析度）。

```bash
curl -s -X POST http://localhost:8000/api/v1/predict \
  -F 'file=@samples/contact.png' | jq .
```

**contact response**：

```json
{
  "status": "contact",
  "roi_image": "/local_output/contact/cropped_20261111_142055_999.jpg",
  "fullframe_image": "/local_output/contact/20261111_142055_999.jpg",
  "laplacian_score": 11.78,
  "probability_contact": 0.7912,
  "features": { "lap_var": 11.78, "mean": 36.29, "std": 25.61, "edge_den": 0.0076, "grad_mag": 21.09 }
}
```

**non_contact response**：

```json
{
  "status": "non_contact",
  "roi_image": null,
  "fullframe_image": "/local_output/non-contact/20261111_142056_120.jpg",
  "laplacian_score": 14.06,
  "probability_contact": 0.395,
  "features": { "lap_var": 14.06, "mean": 36.86, "std": 21.85, "edge_den": 0.008, "grad_mag": 10.52 }
}
```

| 欄位 | 說明 |
|---|---|
| `status` | `contact` 或 `non_contact` |
| `roi_image` | contact 時為中央 crop 的 URL；non_contact 時為 `null` |
| `fullframe_image` | 一律有值——**cleaned** 1280×1024 原圖 + 黃色 ROI 外框 |
| `laplacian_score` | 等同於 `features.lap_var` |
| `probability_contact` | logistic 機率 |
| `features` | 5 個特徵（在**去除 overlay 的 central crop** 上算的） |

### `GET /local_output/contact/<file>.jpg`、`/local_output/non-contact/<file>.jpg`

以 FastAPI StaticFiles 提供。

---

## 7. 批次掃描工具 — `scan_batch.py`

與 v1 完全相同的介面；response shape 也一樣，所以直接用：

```bash
python scan_batch.py samples/
python scan_batch.py labeled_data/ --labeled   # 有 label 時量測準確率
python scan_batch.py samples/ --csv v3_results.csv
```

---

## 8. `contact-monitor-service` 應該怎麼呼叫這個 API

與 v1 相同：**不要裁切、不要 resize、不要去 overlay**，整張送 AOI 就好。所有前處理（resize、overlay 去除、裁切）都在 AOI 內部。

### 相機設定

- RCM 解析度不限（API 會 resize 到 1280 × 1024）
- 構圖：確保 central ROI（左 30%–75% 寬 × 上 35%–80% 高）框到 probe / die 接觸區
- AOI 機器內建的藍色框與十字線可以保留——API 會把它們去掉

### 儲存量估算 + 檔案回收

Monitor 每 `aoi.interval_ms` 呼叫一次（預設 200 ms = 5 Hz）：
- 每次 AOI 寫**一行 JSONL log**（約 450 B）
- **每次都寫**一張 cleaned 原圖（1280 × 1024，~130 KB——比 v1/v2 稍小因為 overlay 被擦掉了）
- **僅 contact 時**多寫一張中央 crop（576 × 461，~70 KB）

粗估：

- 每小時 log：18,000 × ~450 B ≈ **~8 MB**
- 每小時原圖：18,000 × ~130 KB ≈ **~2.3 GB**（大多分流到 non-contact/）
- 每小時 crop：取決於 contact 事件比例

檔案回收 service 要清理 `paths.contact_dir`、`paths.non_contact_dir`、`paths.log_dir` 內已輪替的檔案。

### 和 v1/v2 的比較

| 面向 | v1 (v7.6) | v2 (v8.0) | v3 (v9.0) |
|---|---|---|---|
| ROI 數量 | 1（LEFT） | 2（LEFT + RIGHT mirror） | 1（CENTRAL） |
| Overlay 移除 | ✗ | ✗ | ✓（藍/青框 + 白十字） |
| 聚合方式 | — | per-ROI OR | — |
| Latency | ~25 ms | ~40 ms | **~80 ms**（inpaint 比較慢） |
| 24 張 labeled 準確率 | 100% | 95.8% | 100% |
| 適用情境 | 相機 framing 穩定、不在意 UI overlay 污染 ROI | 想看 probe card 左右兩側獨立判定 | AOI 機器本身會畫 UI overlay、擔心 overlay 影響 ROI 準確度 |

---

## 9. 特徵說明

與 v1 / v2 相同的 5 個特徵、相同的計算方式（ROI 灰階 + 5×5 Gaussian blur）。差別只在於 ROI **內容**不同（central vs. left，overlay 已去除 vs. 沒去除），所以特徵的絕對範圍和模型權重會不同。

**v3 模型權重（在 1280×1024 的 cleaned central ROI 上訓練）**：

| Feature     | 衡量目標 | v3 權重 |
|-------------|---------|---------:|
| `lap_var`   | Laplacian 變異數 | **+1.54** |
| `grad_mag`  | Sobel gradient magnitude 平均 | **+1.83** |
| `edge_den`  | Canny edge pixel 比例 | **+1.59** |
| `mean`      | 灰階平均強度 | **−1.59** |
| `std`       | 灰階強度 std-dev | +0.26 |
| *intercept* | | −0.56 |

注意 `mean` 的權重是**負的**——因為 v3 的 central ROI 包含較多 die 的暗背景；contact 事件讓局部有探針反射，但整體 mean 反而稍微變低（跟 v1/v2 的 left ROI 不同，那邊的 contact 常常更亮）。模型自己學到這個方向。

---

## 10. 校正：相機 / FOV / resize / overlay 參數變更時

需要重新校正的情況：
- 鏡頭、FOV、zoom 有明顯變動
- 修改 `config/aoi_api.json` 的 `input_resize`
- 修改 `config/aoi_api.json` 的 `overlay_removal` 任何欄位（含 `enabled`）
- 更新機器 UI 樣式（新版的 AOI 機器 overlay 可能顏色 / 位置不同）

校正流程（給 API owner）：
1. 收集 ≥10 張 contact + ≥10 張 non_contact 的 labeled 影像。
2. 在校正 script 內設定 `TARGET` 與 `ROI` 常數（和你改的 config 一致）。
3. 執行 script，它會：resize → overlay removal → central crop → 跑 logistic → 覆蓋 `aoi-api-package_v3/local_output/calibration.json`。
4. 不必改 `prob_api.py`。

---

## 11. 待確認事項

1. **Overlay removal 可能影響 probe / die 的輕微反射**：blue_delta 預設 25 比較保守，但若某些 die 本身有藍色反光（例如多層金屬疊構造），會被誤當成 overlay 去掉。遇到時調高 `blue_delta`（例如 40–60）或改 ROI 避開那塊區域。
2. **白色十字線偵測可能誤傷**：若 probe tip 反光很強（亮度 > 180）且連續排列超過 `cross_min_run` 像素，會被誤當成十字線。目前 24 張訓練資料沒出現這個問題；若實際佈線有大面積的亮白條紋請調 `cross_brightness`。
3. **Latency ~80 ms**：主要是 `cv2.inpaint` 的成本。若完全不需要 overlay 移除（相機沒有 UI overlay），把 `overlay_removal.enabled` 設為 `false` 並重新校正即可降到 ~25 ms。

---

## 12. 疑難排解

| 現象 | 可能原因 | 修正方式 |
|---|---|---|
| `GET /api/v1/health` 回傳 `"calibrated": false` | `calibration.json` 缺失或格式有誤 | 從本 package 還原該檔案 |
| 所有判定都是 contact | overlay removal 過度激烈，把 probe 內容也擦掉 | 把 `blue_delta` 調大（例如 40）、`cross_brightness` 調高、或暫時 `enabled: false` 看 raw |
| 所有判定都是 non_contact | overlay removal 不足，ROI 還是看到 UI 邊 | 把 `blue_delta` 調小（例如 15）、`cross_brightness` 調低 |
| POST 回 `500` 且訊息含 `計算出的 ROI 範圍無效` | 上傳的圖太小 | 確認相機能提供至少 1280×1024 以上影像 |
| 啟動時 stderr 出現 `WARN: config ... not found — using defaults` | config 檔不存在或路徑錯 | 確認從 package 根目錄啟動 |
| Latency > 200 ms | 絕大部分在 inpaint | 關掉 overlay removal 或縮小 inpaint_radius |
