# AH9710 AOI-API — 開發者 Package

小型 FastAPI 服務，用來判定探針針尖是否已經與 probe card 接觸（ROI 影像為對焦狀態 = `contact`，失焦 = `non_contact`）。本服務對所有 probe card 類型通用——單一 calibration、單一 fixed reference ROI。

- **服務 port**：`8000`（可透過 `config/aoi_api.json` 或 uvicorn 參數調整）
- **模型**：以 5 個低成本影像特徵（`lap_var`, `grad_mag`, `edge_den`, `mean`, `std`）為輸入的 logistic regression
- **判定規則**：`probability_contact >= 0.5` 判為 `contact`
- **Reference ROI（全畫面的比例座標）**：`rx1=0.25, ry1=0.45, rx2=0.50, ry2=0.85`
- **內部 resize**：**v7.6 起，所有上傳的 RCM 影像一律 resize 到 1280 × 1024 後再處理**。相機解析度不再受限；monitor 直接送原圖即可。

---

## 1. 這個 Package 的內容

```
aoi-api-package/
├── prob_api.py            # FastAPI 服務本體 (v7.6, 1280×1024 resize)
├── config/
│   └── aoi_api.json       # 所有可調整的路徑與 server/log 設定（見 §4）
├── local_output/
│   ├── calibration.json   # 訓練好的模型（通用、單一物件，無 per-category 鍵）
│   ├── contact/           # 判定為 contact 時的 JPG 儲存位置（原圖 + 裁切兩個檔）
│   └── non-contact/       # 判定為 non_contact 時的全畫面儲存位置（僅原圖 + 黃色 ROI 外框，不含裁切）
├── logs/
│   └── aoi_api.log        # 每次 predict 的 JSON Lines 紀錄（見 §5；每日午夜輪替）
├── requirements.txt       # Python 相依套件
├── scan_batch.py          # CLI 工具——批次掃描資料夾、印出每張的 KPI 與判定
├── samples/
│   ├── contact.png            # 完整 1540×1050 RCM 截圖（contact）
│   └── non_contact.png        # 完整 1540×1050 RCM 截圖（non_contact）
├── README.md              # 本文件
└── README.html            # 本文件的 HTML 版（離線可讀，不需後端）
```

**重要**：請從 **package 的根目錄**啟動服務，才能讓 `./config/aoi_api.json`、`./local_output/calibration.json`、`./logs/` 等相對路徑解析正確——程式啟動時會從當下目錄讀取。

---

## 2. 安裝與啟動

```bash
# 建立 Python 3.10+ 環境（venv / conda 皆可）
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 啟動服務（會讀取 config/aoi_api.json）
python prob_api.py
# 或指定自訂設定檔：
AOI_API_CONFIG=/etc/aoi/aoi_api.json python prob_api.py
# 或 bypass config 用 uvicorn 直接啟動（仍會載入預設設定）：
uvicorn prob_api:app --host 0.0.0.0 --port 8000
```

當 `GET http://localhost:8000/api/v1/health` 回傳 `{"status":"ok", "calibrated": true, ...}` 就表示啟動成功。

Swagger UI 位址：`http://localhost:8000/docs`。

---

## 3. 整體資料流

```
RCM 相機（任意解析度）
   │ snapshot
   ▼
contact-monitor-service  ← 您同事的程式
   │ 不裁切、不 resize，直接上傳 RCM 整張（任意解析度）
   ▼
POST /api/v1/predict  multipart file=<整張 RCM>
   │
   ▼
AOI API (prob_api.py)
   │ 1. 讀入 → resize 到 1280 × 1024（v7.6 起）
   │ 2. 依 reference_roi 裁出 320×410 crop
   │ 3. 計算 5 個特徵 → logistic → status
   │ 4. 存檔：
   │    每次都存：<timestamp>.jpg          ← resized 原圖 1280×1024 + 黃色 ROI 外框
   │              - contact      → 存到 ./local_output/contact/
   │              - non_contact  → 存到 ./local_output/non-contact/
   │    僅 contact 多存一個：cropped_<timestamp>.jpg ← 320×410 crop
   │                        → ./local_output/contact/cropped_*.jpg
   │ 5. 寫一行 JSON Lines 到 ./logs/aoi_api.log（詳見 §5）
   │ 6. 回傳 JSON（status、roi_image、fullframe_image、features、probability）
   ▼
monitor 依 response 更新 Redis / LED、Web UI 依 `roi_image` 顯示（null 時不顯示）
```

Monitor 端的工作因此簡化：只負責 **fetch snapshot → 上傳**，裁切、存檔、日誌都由 AOI 做。

---

## 4. 設定檔 `config/aoi_api.json`

所有可調整的路徑與 server/logging 設定都寫在這裡；程式啟動時讀取，不存在時使用內建預設值。檔案回收 service 可讀取同一份設定來得知要掃哪些資料夾（見 §8「儲存量估算」）。

**預設內容**：

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
  }
}
```

**各欄位**：

| 欄位 | 說明 |
|---|---|
| `server.host`, `server.port` | uvicorn 綁定位址與 port |
| `paths.calibration_json` | 模型 calibration 檔路徑（相對或絕對皆可） |
| `paths.contact_dir` | predict 判定為 `contact` 時 JPG 寫入的資料夾 |
| `paths.non_contact_dir` | predict 判定為 `non_contact` 時 JPG 寫入的資料夾 |
| `paths.log_dir` | JSON Lines log 檔寫入的資料夾 |
| `logging.level` | Python logging level（`DEBUG` / `INFO` / `WARNING` / `ERROR`） |
| `logging.filename` | 當日 log 檔名（固定；輪替後會變成 `aoi_api.log.YYYY-MM-DD`） |
| `logging.rotation` | 目前僅支援 `daily`（午夜輪替）；留此欄位以便未來擴充 |
| `logging.backup_count` | 保留幾份輪替過的舊檔（超過的最舊檔會被 handler 自動刪除） |
| `input_resize.width`, `.height` | **v7.6 起**：所有 incoming 影像一律 resize 到這個尺寸再處理。**改這個值必須配合重新校正**（見 §10） |

**換到不同的路徑或 port**：直接改 `config/aoi_api.json`，然後重啟服務。StaticFiles 對外的 URL path 固定為 `/local_output/contact/...` 與 `/local_output/non-contact/...`，不受 `paths.contact_dir` / `paths.non_contact_dir` 影響，所以 monitor 端的呼叫合約穩定。

**換到完全不同位置的設定檔**：在啟動前設定環境變數 `AOI_API_CONFIG` 指向目標檔案即可，例如 `AOI_API_CONFIG=/etc/aoi/aoi_api.json python prob_api.py`。

---

## 5. Log 紀錄（JSON Lines）

每次 `POST /api/v1/predict` 完成後，AOI 會把完整 response + 來源檔名 + 處理耗時寫入 `<log_dir>/aoi_api.log`，格式為 **JSON Lines**（每一行是一個獨立 JSON 物件，方便 `jq`、`pandas`、`grep` 處理）。另會紀錄 `startup`、`shutdown`、`predict_error` 事件。

**檔名輪替**：使用 Python `TimedRotatingFileHandler`，每日 00:00 午夜產生新檔，舊檔改名成 `aoi_api.log.YYYY-MM-DD`。保留天數由 `logging.backup_count` 控制（預設 7）；超過的最舊檔自動刪除。

**Predict 事件格式範例**（單行，為了易讀以下有換行）：

```json
{
  "ts": "2026-11-10T11:41:52.156",
  "level": "INFO",
  "event": "predict",
  "filename": "Screenshot 2026-11-06 121216.png",
  "status": "contact",
  "roi_image": "/local_output/contact/cropped_20261110_114152_156.jpg",
  "fullframe_image": "/local_output/contact/20261110_114152_156.jpg",
  "laplacian_score": 24.25,
  "probability_contact": 0.8824,
  "features": {
    "lap_var": 24.2527, "mean": 55.1213, "std": 23.2327,
    "edge_den": 0.0128, "grad_mag": 40.9087
  },
  "latency_ms": 23.5
}
```

**其他事件**：

| event | 欄位 | 時機 |
|---|---|---|
| `startup` | `version`, `config_path`, `paths` | 服務啟動時 |
| `shutdown` | `version` | 服務停止時 |
| `predict_error` | `filename`, `error` | 上傳的影像無法解碼、為空、或 ROI 無效 |

**查詢範例**：

```bash
# 查看今日所有 contact 判定
grep '"status": "contact"' logs/aoi_api.log | wc -l

# 用 jq 挑出所有 latency > 100ms 的紀錄
jq -c 'select(.event == "predict" and .latency_ms > 100)' logs/aoi_api.log

# pandas 快速匯入
python -c "import pandas as pd; df = pd.read_json('logs/aoi_api.log', lines=True); print(df.describe())"
```

---

## 6. HTTP endpoints

### `GET /api/v1/health` — 可用性檢查

`contact-monitor-service` 在 `STARTING` 狀態會用這個 endpoint 確認 AOI 已經準備好。

```json
{
  "status": "ok",
  "service": "aoi-api",
  "version": "7.6",
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

`multipart/form-data`，單一欄位 `file`。上傳 **完整 RCM 截圖**（任意解析度；AOI 內部 resize 到 1280 × 1024 後再裁切）。

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
| `roi_image` | **contact 時**為裁切後 ROI 影像 URL path（`/local_output/contact/cropped_<timestamp>.jpg`）；**non_contact 時為 `null`**（non_contact 不會寫 cropped 檔） |
| `fullframe_image` | **一律提供**。contact → `/local_output/contact/<timestamp>.jpg`；non_contact → `/local_output/non-contact/<timestamp>.jpg`。皆為原圖 1540×1050 + **黃色** ROI 外框，給人工 offline review 用 |
| `laplacian_score` | 等同於 `features.lap_var`——保留以符合設計文件相容欄位 |
| `probability_contact` | logistic 模型輸出的 0.0 – 1.0 機率 |
| `features` | 五個特徵的全部數值（詳見 §9） |

**non_contact response 範例**（roi_image 為 null，但 fullframe_image 有值）：

```json
{
  "status": "non_contact",
  "roi_image": null,
  "fullframe_image": "/local_output/non-contact/20261110_141505_467.jpg",
  "laplacian_score": 11.68,
  "probability_contact": 0.0016,
  "features": { "lap_var": 11.6823, "mean": 48.4003, "std": 14.0118, "edge_den": 0.0048, "grad_mag": 7.402 }
}
```

### `GET /local_output/contact/<file>.jpg` 與 `/local_output/non-contact/<file>.jpg` — 取回已儲存的 JPG

以 FastAPI StaticFiles 提供；`roi_image` 與 `fullframe_image` 回傳的路徑可直接拼接服務 base URL，例如：
`http://192.168.137.101:8000/local_output/contact/20261107_123451_018.jpg`

> `local_output/calibration.json` **不會**被對外提供，因為我們只掛載 `contact/` 與 `non-contact/` 兩個子目錄。

---

## 7. 批次掃描工具 — `scan_batch.py`

掃描資料夾裡的所有影像，逐張呼叫 API，印出每一張的 KPI 與判定、最後顯示 summary。本工具不做任何裁切——API 內部完全處理。

### 7a. 基本用法

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

### 7b. 有 label 時量測準確率

把資料放到 `<root>/contact/` 和 `<root>/non-contact/` 子目錄，然後加 `--labeled`：

```bash
python scan_batch.py labeled_data/ --labeled
```

輸出會多一個 `truth` 欄位，summary 也會附上 `accuracy`。

### 7c. 輸出成 CSV

```bash
python scan_batch.py samples/ --csv results.csv
```

CSV 會包含兩個已儲存檔案的 URL path（`roi_image` 與 `fullframe_image`）。

### 7d. 指定不同的 API 位址

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

## 8. `contact-monitor-service` 應該怎麼呼叫這個 API

Monitor 端的工作非常單純：**不要裁切、不要 resize，直接把 RCM 整張 snapshot 以 `file` 欄位 POST 給 `/api/v1/predict`**。

### 相機設定

v7.6 起 **不再要求特定相機解析度**——AOI 內部會把所有上傳的影像 resize 到 1280 × 1024 再處理。Monitor 直接送原圖即可，不需裁切、不需 resize。

需要注意的是**構圖**：確保訓練時的 ROI 區域（左 25%–50% 寬 × 上 45%–85% 高）框到探針與 die 的接觸區。這跟相機絕對解析度無關，而是跟拍攝視野（FOV）有關。

AOI 內部會：
1. 把上傳影像 resize 到 1280 × 1024
2. 依 reference_roi 裁出 **320 × 410** px 的 crop
3. 計算 5 個特徵並跑 logistic 判定

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

拿任何一張**已知是 contact** 的 RCM 截圖丟進 `/api/v1/predict`，看 response 的 `features`（基於 1280 × 1024 resize 後的 crop）：

| Feature  | contact 預期區間 | non-contact 預期區間 |
|----------|---------------:|------------------:|
| `lap_var`   | 20 – 27 | 10 – 18 |
| `grad_mag`  | 41 – 57 | 7 – 39  |
| `edge_den`  | 0.01 – 0.08 | 0.00 – 0.02 |
| `mean`      | 51 – 62 | 45 – 58 |
| `std`       | 23 – 40 | 14 – 36 |

若實際數值嚴重偏離這些區間（例如 `lap_var = 3` 或 `lap_var = 80`），代表相機 **構圖** 錯誤或 FOV 嚴重偏移（而不是解析度問題——v7.6 已經會 resize）。請重新對準 probe / die 位置。

### 儲存量估算 + 檔案回收

Monitor 每 `aoi.interval_ms` 呼叫一次（預設 200 ms = 5 Hz）。每次 AOI 寫：
- **一行 JSONL log**（約 400 B）
- **一張 1540×1050 原圖**（帶黃色 ROI 外框，~220 KB），依 status 存到 contact/ 或 non-contact/
- **僅 contact 時**多寫一張 385×420 crop（~40 KB）

粗估：

- 每小時 log 行：18,000 × ~400 B ≈ **~7 MB**（daily rotate，由 `logging.backup_count` 自動限制，預設保留 7 天）
- 每小時原圖：18,000 × ~220 KB ≈ **~4 GB**（大多數分流到 non-contact/）
- 每小時 crop：~1,000–3,600 × ~40 KB ≈ **~50–150 MB**（取決於 contact 事件比例）
- 檔案回收 service 要清理的路徑（都可從 `config/aoi_api.json` 讀到）：
  - `paths.contact_dir` （預設 `./local_output/contact/*.jpg`）——建議保留 24 小時
  - `paths.non_contact_dir` （預設 `./local_output/non-contact/*.jpg`）——建議保留 24 小時（這裡佔最大儲存量）
  - `paths.log_dir` 內已輪替的檔（`aoi_api.log.YYYY-MM-DD`）——當日 `aoi_api.log` **請勿刪除**

---

## 9. 特徵說明

五個特徵都計算於 ROI 的灰階影像、且經過 5×5 Gaussian blur。挑選標準：**至少兩個特徵能單獨區分 contact / non-contact**，當 probe card 類型改變時仍然 robust。

| Feature     | 衡量目標 | v7.6 模型權重（在 1280×1024 的 LEFT ROI 上訓練） |
|-------------|---------|---------:|
| `lap_var`   | Laplacian 變異數——銳利度 / 高頻訊號 | **+2.12**（主訊號） |
| `grad_mag`  | Sobel gradient magnitude 平均——整體邊緣強度 | **+1.29**（主訊號） |
| `edge_den`  | Canny edge pixel 比例 | **+1.34**（主訊號） |
| `mean`      | 灰階平均強度 | +0.40 |
| `std`       | 灰階強度 std-dev | −0.64（被 L2 regularize 壓縮） |
| *intercept* | | −0.99 |

預測公式：`sigmoid( weight · ((feature − mean) / std) + intercept )`，在 0.5 處做判定。

---

## 10. 相機 / FOV / resize 變更時的重新校正

v7.6 的 calibration 是在 **1280 × 1024** resize 後的 LEFT ROI 上訓練的。以下情況需要重新校正：

- 鏡頭 / FOV / zoom 有明顯變動（特徵分布會偏移）
- 修改 `config/aoi_api.json` 的 `input_resize.width` 或 `.height`（像素密度改變，`lap_var` / `grad_mag` / `edge_den` 的絕對值會整體偏移）

校正流程（給 API owner）：
1. 收集至少 10 張 contact + 10 張 non-contact 的 labeled 影像（放到 `PROB/input/<date>/contact/` 和 `non-contact/`）。
2. 把目標 resize 尺寸填進校正 script 的 `TARGET` 常數。
3. 執行校正 script，它會：影像 resize → 裁 LEFT ROI → 跑 logistic → 覆蓋 `aoi-api-package/local_output/calibration.json`。
4. 不必改 `prob_api.py`。

API 的程式與 endpoint 在校正前後**不會改變**。

---

## 11. 待確認事項（截至此版）

1. **`roi_image` 格式確定。** 回傳的是本 API 內建 StaticFiles 提供的 **URL path**（`GET /local_output/contact/<file>.jpg` 或 `/local_output/non-contact/<file>.jpg`），monitor 自行加上 base URL 就能給前端 Web UI 顯示。
2. **`category` 欄位取消。** 設計文件 `monitor.json` 裡的 `aoi.category` 不再需要——本 API 通用於所有 probe card。Monitor 可將該欄位留空，或（更保險）直接從上傳 payload 中移除。
3. **Log rotation + 檔案回收。** 每 tick 寫一張 overlay 原圖（contact 分流到 `paths.contact_dir`，non_contact 分流到 `paths.non_contact_dir`）；僅 contact 多寫 crop。JSON Lines log 儲存在 `paths.log_dir`，每日午夜自動輪替。檔案回收 service 請讀取 `config/aoi_api.json` 來知道所有需要掃描的路徑（詳見 §8 儲存量估算）。
4. **v7.5 行為變更**：
   - ROI 外框顏色從**藍色改為黃色**（更顯眼、在深色背景下可讀性高）。
   - non_contact 的原圖**會存檔**到 `paths.non_contact_dir`，response `fullframe_image` 回該檔的 URL。
   - non_contact **仍不存 crop 檔**，response `roi_image` 為 `null`。
5. **v7.6 行為變更**：
   - **所有上傳影像一律 resize 到 1280 × 1024 再處理**（可透過 `config/aoi_api.json` 的 `input_resize` 調整）。Monitor 不再需要特定相機解析度。
   - `calibration.json` 已在 1280 × 1024 的 LEFT ROI 上重新訓練，24 張 labeled data 準確率 **100%**。
   - 存檔的 `fullframe_image` 尺寸從 1540 × 1050 變為 **1280 × 1024**。

---

## 12. 疑難排解

| 現象 | 可能原因 | 修正方式 |
|---|---|---|
| `GET /api/v1/health` 回傳 `"calibrated": false` | `calibration.json` 缺失或格式有誤 | 從本 package 還原該檔案；確認 `config/aoi_api.json` 的 `paths.calibration_json` 指到對的位置 |
| 已知是 contact 的影像都被判成 `non_contact` 且 `p ≈ 0.0` | 相機構圖 / FOV 不對（解析度已被 API 自動 resize） | 用 §8 的表格檢查 `features` 值，重新對準 probe / die |
| POST 回 `422 Unprocessable Entity` | multipart 欄位名錯誤 | 欄位名必須完全是 `file` |
| POST 回 `500` 且訊息含 `計算出的 ROI 範圍無效` | 上傳的圖太小，reference_roi 裁出來的 crop 是 0×0 | 確認上傳的是完整 RCM 截圖，不是已經裁好的 ROI |
| POST 回 `500` 且訊息含 `calibration missing` | calibration.json 損壞或缺少 feature 資訊 | 從 package 還原，重新啟動服務 |
| 啟動時 stderr 出現 `WARN: config ... not found — using defaults` | config 檔不存在或路徑錯 | 確認從 package 根目錄啟動；或設定 `AOI_API_CONFIG` 環境變數 |
| `logs/aoi_api.log` 一直沒有新內容 | `paths.log_dir` 無寫入權限，或 handler 初始化失敗 | 檢查資料夾存在性與權限；重啟後觀察 stderr |
| Latency > 200 ms | AOI 本身約 25 ms，問題不在 AOI | 檢查網路以及 RCM 取圖時間 |
