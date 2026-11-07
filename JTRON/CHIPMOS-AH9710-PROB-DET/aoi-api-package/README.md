# AH9710 AOI-API — 開發者 Package

小型 FastAPI 服務，用來判定探針針尖是否已經與 probe card 接觸（ROI 影像為對焦狀態 = `contact`，失焦 = `non_contact`）。本服務對所有 probe card 類型通用——單一 calibration、單一 fixed reference ROI。

- **服務 port**：`8000`（可透過 uvicorn 參數調整）
- **模型**：以 5 個低成本影像特徵（`lap_var`, `grad_mag`, `edge_den`, `mean`, `std`）為輸入的 logistic regression
- **判定規則**：`probability_contact >= 0.5` 判為 `contact`
- **Reference ROI（全畫面的比例座標）**：`rx1=0.25, ry1=0.45, rx2=0.50, ry2=0.85`
- **建議相機解析度**：**1540 × 1050**，使 reference_roi 的原生裁切恰為 **385 × 420 px**（與訓練資料一致）

---

## 1. 這個 Package 的內容

```
aoi-api-package/
├── prob_api.py            # FastAPI 服務本體
├── local_output/
│   ├── calibration.json   # 訓練好的模型（通用、單一物件，無 per-category 鍵）
│   ├── contact/           # 判定為 contact 時的 JPG 儲存位置（原圖 + 裁切兩個檔）
│   └── non-contact/       # 判定為 non_contact 時的 JPG 儲存位置（原圖 + 裁切兩個檔）
├── requirements.txt       # Python 相依套件
├── scan_batch.py          # CLI 工具——批次掃描資料夾、印出每張的 KPI 與判定
├── samples/
│   ├── contact.png            # 完整 1540×1050 RCM 截圖（contact）
│   └── non_contact.png        # 完整 1540×1050 RCM 截圖（non_contact）
├── README.md              # 本文件
└── README.html            # 本文件的 HTML 版（離線可讀，不需後端）
```

**重要**：請從 **package 的根目錄**啟動服務，才能讓 `./local_output/calibration.json` 的相對路徑解析正確——程式啟動時會從當下目錄讀取。

---

## 2. 安裝與啟動

```bash
# 建立 Python 3.10+ 環境（venv / conda 皆可）
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 啟動服務
python prob_api.py
# 或：
uvicorn prob_api:app --host 0.0.0.0 --port 8000
```

當 `GET http://localhost:8000/api/v1/health` 回傳 `{"status":"ok", "calibrated": true, ...}` 就表示啟動成功。

Swagger UI 位址：`http://localhost:8000/docs`。

---

## 3. 整體資料流

```
RCM 相機 (1540 × 1050)
   │ snapshot
   ▼
contact-monitor-service  ← 您同事的程式
   │ 不裁切、不 resize，直接上傳 1540×1050 整張
   ▼
POST /api/v1/predict  multipart file=<整張 1540×1050>
   │
   ▼
AOI API (prob_api.py)
   │ 1. 讀入 → 依 reference_roi 裁出 385×420 crop
   │ 2. 計算 5 個特徵 → logistic → status
   │ 3. 存 2 個 JPG 到 ./local_output/<status>/：
   │       <timestamp>.jpg          ← 原圖 1540×1050 + 藍色 ROI 外框 (給人工檢視)
   │       cropped_<timestamp>.jpg  ← 原始 385×420 crop (給模型除錯)
   │ 4. 回傳 JSON（status、roi_image、fullframe_image、features、probability）
   ▼
monitor 依 response 更新 Redis / LED、Web UI 依 `roi_image` 顯示
```

Monitor 端的工作因此簡化：只負責 **fetch snapshot → 上傳**，裁切與存檔都由 AOI 做。

---

## 4. HTTP endpoints

### `GET /api/v1/health` — 可用性檢查

`contact-monitor-service` 在 `STARTING` 狀態會用這個 endpoint 確認 AOI 已經準備好。

```json
{
  "status": "ok",
  "service": "aoi-api",
  "version": "7.2",
  "calibrated": true
}
```

### `GET /api/v1/config` — 模型 metadata

Monitor 啟動時呼叫一次即可；用 `reference_roi` 確認 RCM framing 與訓練幾何一致。

```json
{
  "reference_roi": { "rx1": 0.25, "ry1": 0.45, "rx2": 0.5, "ry2": 0.85 },
  "model": "logistic",
  "features": ["lap_var", "mean", "std", "edge_den", "grad_mag"],
  "decision_threshold": 0.5,
  "trained_on": { "n_contact": 10, "n_non_contact": 14 }
}
```

### `POST /api/v1/predict` — 判定一張 RCM 截圖

`multipart/form-data`，單一欄位 `file`。上傳 **完整 RCM 截圖**（建議 1540 × 1050），AOI 會自行裁切。

```bash
curl -s -X POST http://localhost:8000/api/v1/predict \
  -F 'file=@samples/contact.png' | jq .
```

Response：

```json
{
  "status": "contact",
  "roi_image": "/local_output/contact/cropped_20261107_123451_018.jpg",
  "fullframe_image": "/local_output/contact/20261107_123451_018.jpg",
  "laplacian_score": 24.74,
  "probability_contact": 0.9138,
  "features": {
    "lap_var": 24.74,
    "mean": 55.11,
    "std": 23.31,
    "edge_den": 0.015,
    "grad_mag": 41.35
  }
}
```

欄位說明：

| 欄位 | 說明 |
|---|---|
| `status` | `"contact"` 或 `"non_contact"`——monitor 需要的二元判定 |
| `roi_image` | 已儲存的裁切後 ROI 影像 URL path（`cropped_<timestamp>.jpg`）。Web UI 依設計文件 §7 只在 `contact` 時顯示 |
| `fullframe_image` | 已儲存的原圖 URL path（`<timestamp>.jpg`），上面有藍色 ROI 外框——給人工 offline review 用 |
| `laplacian_score` | 等同於 `features.lap_var`——保留以符合設計文件相容欄位 |
| `probability_contact` | logistic 模型輸出的 0.0 – 1.0 機率 |
| `features` | 五個特徵的全部數值（詳見 §7） |

### `GET /local_output/contact/<file>.jpg` 與 `/local_output/non-contact/<file>.jpg` — 取回已儲存的 JPG

以 FastAPI StaticFiles 提供；`roi_image` 與 `fullframe_image` 回傳的路徑可直接拼接服務 base URL，例如：
`http://192.168.137.101:8000/local_output/contact/20261107_123451_018.jpg`

> `local_output/calibration.json` **不會**被對外提供，因為我們只掛載 `contact/` 與 `non-contact/` 兩個子目錄。

---

## 5. 批次掃描工具 — `scan_batch.py`

掃描資料夾裡的所有影像，逐張呼叫 API，印出每一張的 KPI 與判定、最後顯示 summary。本工具不做任何裁切——API 內部完全處理。

### 5a. 基本用法

```bash
python scan_batch.py samples/
```

預期輸出：

```
AOI API      : http://localhost:8000
reference ROI: (0.25, 0.45, 0.5, 0.85)
mode         : full-frame upload (API crops internally and saves overlaid+cropped files)
files found  : 2

file                  status          p(c)  lap_var  grad_mag  edge_den    mean     std     ms
---------------------------------------------------------------------------------------------
contact.png           contact       0.9138    24.74    41.35     0.0151   55.11   23.31   15.0
non_contact.png       non_contact   0.0021    12.27     7.43     0.0048   48.39   14.09   12.1
---------------------------------------------------------------------------------------------

scanned      : 2   contact: 1   non_contact: 1   errors: 0
avg latency  : 13.5 ms
```

### 5b. 有 label 時量測準確率

把資料放到 `<root>/contact/` 和 `<root>/non-contact/` 子目錄，然後加 `--labeled`：

```bash
python scan_batch.py labeled_data/ --labeled
```

輸出會多一個 `truth` 欄位，summary 也會附上 `accuracy`。

### 5c. 輸出成 CSV

```bash
python scan_batch.py samples/ --csv results.csv
```

CSV 會包含兩個已儲存檔案的 URL path（`roi_image` 與 `fullframe_image`）。

### 5d. 指定不同的 API 位址

```bash
python scan_batch.py samples/ --url http://192.168.137.101:8000
```

### 所有參數

```
positional:
  path                 要掃描的影像資料夾

options:
  --url URL            AOI API base URL（預設 http://localhost:8000）
  --timeout SECONDS    HTTP timeout（預設 5.0 秒）
  --csv PATH           將每張結果寫入指定 CSV 檔
  --labeled            把 <path> 當作含 ./contact/ 和 ./non-contact/ 的 root
```

---

## 6. `contact-monitor-service` 應該怎麼呼叫這個 API

Monitor 端的工作非常單純：**不要裁切、不要 resize，直接把 RCM 整張 snapshot 以 `file` 欄位 POST 給 `/api/v1/predict`**。

### 相機設定（必須）

- RCM 全畫面解析度：**1540 × 1050 px**
- 構圖：確保訓練時的 ROI 區域（左 25%–50% 寬 × 上 45%–85% 高）框到探針與 die 的接觸區

這組設定讓 AOI 內部裁切後得到 **385 × 420** 原生 crop，與訓練資料幾何一致，不需要在 monitor 或 AOI 任一端做 resize。

### 範例呼叫（Python）

```python
import requests

with open(rcm_snapshot_bytes, "rb") as fh:
    r = requests.post(
        "http://192.168.137.101:8000/api/v1/predict",
        files={"file": ("snap.jpg", fh, "image/jpeg")},
        timeout=3,
    )
resp = r.json()
# resp["status"]              → "contact" or "non_contact"
# resp["roi_image"]           → cropped file URL
# resp["fullframe_image"]     → full-frame + overlay file URL
# resp["probability_contact"] → 0.0–1.0
```

### 裝好之後的驗收檢查

拿任何一張**已知是 contact** 的 RCM 截圖丟進 `/api/v1/predict`，看 response 的 `features`：

| Feature  | contact 預期區間 | non-contact 預期區間 |
|----------|---------------:|------------------:|
| `lap_var`   | 21 – 29 | 12 – 19 |
| `grad_mag`  | 40 – 57 | 7 – 38  |
| `edge_den`  | 0.01 – 0.08 | 0.00 – 0.01 |
| `mean`      | 51 – 62 | 45 – 57 |
| `std`       | 24 – 36 | 14 – 32 |

若實際數值嚴重偏離這些區間（例如 `lap_var = 3` 或 `lap_var = 80`），代表相機解析度或 framing 不對，不是 AOI 的 bug——請確認相機設為 1540 × 1050 且構圖正確。

### 儲存量估算

Monitor 每 `aoi.interval_ms` 呼叫一次（預設 200 ms = 5 Hz），每次 AOI 寫兩個 JPG（原圖 ~450 KB、裁切 ~20 KB）。粗估：

- 每小時：18,000 次呼叫 × 2 檔 ≈ **36,000 檔、約 1 GB**
- 設計文件 §9 的 log-cleaner 必須同時清理 `./local_output/contact/` 與 `./local_output/non-contact/`，建議保留 24 小時。

---

## 7. 特徵說明

五個特徵都計算於 ROI 的灰階影像、且經過 5×5 Gaussian blur。挑選標準：**至少兩個特徵能單獨區分 contact / non-contact**，當 probe card 類型改變時仍然 robust。

| Feature     | 衡量目標 | 模型權重 |
|-------------|---------|---------:|
| `lap_var`   | Laplacian 變異數——銳利度 / 高頻訊號 | **+2.23**（主訊號） |
| `grad_mag`  | Sobel gradient magnitude 平均——整體邊緣強度 | **+1.28**（主訊號） |
| `edge_den`  | Canny edge pixel 比例 | **+1.17**（主訊號） |
| `mean`      | 灰階平均強度 | +0.44 |
| `std`       | 灰階強度 std-dev | −0.45（被 L2 regularize 到接近 0） |
| *intercept* | | −0.90 |

預測公式：`sigmoid( weight · ((feature − mean) / std) + intercept )`，在 0.5 處做判定。

---

## 8. 相機 / FOV 變更時的重新校正

若鏡頭、FOV、或 zoom 有明顯變動，特徵分布會偏移，需要重新校正。收集大約 10 張 contact 與 10 張 non-contact 的 labeled 影像，再執行校正 script（請找 API owner——這是一個小的訓練 script，會重寫 `calibration.json`）。

API 的程式與 endpoint 在校正前後**不會改變**。

---

## 9. 待確認事項（截至此版）

1. **`roi_image` 格式確定。** 回傳的是本 API 內建 StaticFiles 提供的 **URL path**（`GET /local_output/contact/<file>.jpg` 或 `/local_output/non-contact/<file>.jpg`），monitor 自行加上 base URL 就能給前端 Web UI 顯示。
2. **`category` 欄位取消。** 設計文件 `monitor.json` 裡的 `aoi.category` 不再需要——本 API 通用於所有 probe card。Monitor 可將該欄位留空，或（更保險）直接從上傳 payload 中移除。
3. **Log rotation。** 本 API 每次判定都會在對應子資料夾產生 2 個 JPG。請將 `./local_output/contact/` 與 `./local_output/non-contact/` 同時加入設計文件 §9 log-cleaner 的清理範圍，建議保留 24 小時。

---

## 10. 疑難排解

| 現象 | 可能原因 | 修正方式 |
|---|---|---|
| `GET /api/v1/health` 回傳 `"calibrated": false` | `calibration.json` 缺失或格式有誤 | 從本 package 還原該檔案 |
| 已知是 contact 的影像都被判成 `non_contact` 且 `p ≈ 0.0` | 相機解析度或 framing 不對 | 用 §6 的表格檢查 `features` 值，確認相機設為 1540 × 1050 |
| POST 回 `422 Unprocessable Entity` | multipart 欄位名錯誤 | 欄位名必須完全是 `file` |
| POST 回 `500` 且訊息含 `計算出的 ROI 範圍無效` | 上傳的圖太小，reference_roi 裁出來的 crop 是 0×0 | 確認上傳的是完整 RCM 截圖，不是已經裁好的 ROI |
| POST 回 `500` 且訊息含 `calibration.json missing` | calibration.json 損壞或缺少 feature 資訊 | 從 package 還原，重新啟動服務 |
| Latency > 200 ms | AOI 本身約 25 ms，問題不在 AOI | 檢查網路以及 RCM 取圖時間 |
