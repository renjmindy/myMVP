# AH9710 AOI-API v2 — 開發者 Package（dual-ROI, OR aggregation）

v1 的進化版本：把 ROI **左右對稱擴展**（原始 ROI + 水平鏡像），兩個 ROI 分別跑 logistic 判定，用 **OR 聚合**產生最終 status；影像在 API 內部 resize 到 **1280 × 1024**，配合新 resolution 做過的新 calibration。

- **服務 port**：`8000`（可透過 `config/aoi_api.json` 調整）
- **模型**：以 5 個低成本影像特徵（`lap_var`, `grad_mag`, `edge_den`, `mean`, `std`）為輸入的 logistic regression
- **判定規則**：`probability_contact >= 0.5` 單邊判定；兩邊取 OR
- **Reference ROI（LEFT）**：`rx1=0.25, ry1=0.45, rx2=0.50, ry2=0.85`
- **Reference ROI（RIGHT, mirror）**：`rx1=0.50, ry1=0.45, rx2=0.75, ry2=0.85`
- **內部 resize**：任何上傳的解析度一律 resize 到 **1280 × 1024** 後才處理
- **24 張 labeled data 準確率**：OR=95.8%（TP=10, FN=0, TN=13, FP=1）

---

## 1. 這個 Package 的內容

```
aoi-api-package_v2/
├── prob_api.py            # FastAPI 服務本體 (v8.0, dual-ROI OR)
├── config/
│   └── aoi_api.json       # 所有可調整的路徑 / server / log / input_resize 設定（見 §4）
├── local_output/
│   ├── calibration.json   # v2 專用模型（在 1280×1024 的 LEFT ROI 上訓練）
│   ├── contact/           # OR 判定為 contact 時：overlay 原圖 + 兩側 crop 串接
│   └── non-contact/       # OR 判定為 non_contact 時：僅 overlay 原圖（無 cropped）
├── logs/
│   └── aoi_api.log        # 每次 predict 的 JSON Lines 紀錄（詳見 §5）
├── requirements.txt       # Python 相依套件
├── scan_batch.py          # CLI 工具——批次掃描，印出 OVERALL + LEFT / RIGHT 判定
├── samples/
│   ├── contact.png            # 完整 1540×1050 RCM 截圖（contact）
│   └── non_contact.png        # 完整 1540×1050 RCM 截圖（non_contact）
├── README.md              # 本文件
└── README.html            # 本文件的 HTML 版（離線可讀）
```

**重要**：請從 **package 的根目錄**啟動服務，才能讓 `./config/aoi_api.json`、`./local_output/calibration.json`、`./logs/` 等相對路徑解析正確。

---

## 2. 安裝與啟動

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 啟動服務（會讀取 config/aoi_api.json）
python prob_api.py
# 或：
uvicorn prob_api:app --host 0.0.0.0 --port 8000
```

Health 檢查：`GET http://localhost:8000/api/v1/health` 應回：
```json
{"status":"ok","service":"aoi-api","version":"8.0","variant":"dual-roi-or","calibrated":true}
```

Swagger UI：`http://localhost:8000/docs`

---

## 3. 整體資料流

```
RCM 相機（任意解析度）
   │ snapshot
   ▼
contact-monitor-service
   │ 直接上傳整張（不要裁切、不要 resize）
   ▼
POST /api/v1/predict  multipart file=<整張 RCM>
   │
   ▼
AOI API v2 (prob_api.py)
   │ 1. 讀入 → resize 到 1280 × 1024
   │ 2. 依 reference_roi_left 裁出 LEFT crop (320 × 410)
   │    依 reference_roi_right （mirror）裁出 RIGHT crop (320 × 410)
   │ 3. 對 LEFT、RIGHT 各算 5 個特徵 → logistic → 各自 status / prob
   │ 4. OR 聚合：overall status = contact iff (left OR right == contact)
   │ 5. 存檔：
   │    每次都存 <timestamp>.jpg  ← resized 原圖 1280×1024 + 兩個黃色 ROI 外框
   │         - overall contact      → ./local_output/contact/
   │         - overall non_contact  → ./local_output/non-contact/
   │    僅 overall contact 時多存 cropped_<timestamp>.jpg（LEFT | RIGHT 橫向串接）
   │ 6. 寫一行 JSON Lines 到 ./logs/aoi_api.log（詳見 §5）
   │ 7. 回傳 JSON（含 per_roi 區塊，見 §6）
   ▼
monitor 依 response 更新 Redis / LED、Web UI 依 `roi_image` 顯示
```

---

## 4. 設定檔 `config/aoi_api.json`

v2 比 v1 多一個 `input_resize` 區塊。其他設定意義不變。

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

| 欄位 | 說明 |
|---|---|
| `server.host`, `server.port` | uvicorn 綁定位址與 port |
| `paths.*` | calibration、contact / non-contact JPG、log 的存放路徑 |
| `logging.*` | log level、檔名、每日輪替、保留天數 |
| `input_resize.width`, `.height` | 所有 incoming 影像一律 resize 到這個尺寸再處理。**如果你要改這個值，必須配合重新校正**（見 §10）|

**換到完全不同位置的設定檔**：在啟動前設定環境變數 `AOI_API_CONFIG` 指向目標檔案即可，例如 `AOI_API_CONFIG=/etc/aoi/aoi_api.json python prob_api.py`。

---

## 5. Log 紀錄（JSON Lines）

每次 `POST /api/v1/predict` 完成後寫入一行到 `<log_dir>/aoi_api.log`，每日午夜輪替。v2 的 log 行包含 `per_roi` 完整資訊，所以可以離線重建每一次 left / right 的判定。

**Predict 事件格式範例**（單行，為了易讀以下有換行）：

```json
{
  "ts": "2026-11-11T10:03:33.476",
  "level": "INFO",
  "event": "predict",
  "filename": "Screenshot 2026-11-06 121216.png",
  "status": "contact",
  "aggregation": "OR",
  "probability_contact": 0.8992,
  "roi_image": "/local_output/contact/cropped_20261111_100333_476.jpg",
  "fullframe_image": "/local_output/contact/20261111_100333_476.jpg",
  "per_roi": {
    "left":  {"status":"contact","probability_contact":0.8992,"laplacian_score":24.26,"features":{...}},
    "right": {"status":"contact","probability_contact":0.559, "laplacian_score":31.77,"features":{...}}
  },
  "latency_ms": 42.1
}
```

**其他事件**：

| event | 欄位 | 時機 |
|---|---|---|
| `startup` | `version`, `variant`, `input_resize`, `config_path`, `paths` | 服務啟動時 |
| `shutdown` | `version` | 服務停止時 |
| `predict_error` | `filename`, `error` | 上傳影像無法解碼、為空、或 ROI 無效 |

**查詢範例**：

```bash
# 只有左側 contact、右側 non_contact 的判定（AND 會漏掉，OR 會抓到）
jq -c 'select(.event=="predict" and .per_roi.left.status=="contact" and .per_roi.right.status=="non_contact")' logs/aoi_api.log

# 用 pandas 匯入、展開 per_roi
python -c "
import pandas as pd
df = pd.read_json('logs/aoi_api.log', lines=True)
df['L_status'] = df['per_roi'].apply(lambda d: d['left']['status'] if isinstance(d,dict) else None)
df['R_status'] = df['per_roi'].apply(lambda d: d['right']['status'] if isinstance(d,dict) else None)
print(df[['ts','status','L_status','R_status','probability_contact']].head())
"
```

---

## 6. HTTP endpoints

### `GET /api/v1/health`

```json
{
  "status": "ok",
  "service": "aoi-api",
  "version": "8.0",
  "variant": "dual-roi-or",
  "calibrated": true
}
```

### `GET /api/v1/config`

```json
{
  "variant": "dual-roi-or",
  "input_resize": { "width": 1280, "height": 1024 },
  "reference_roi":      { "rx1": 0.25, "ry1": 0.45, "rx2": 0.5, "ry2": 0.85 },
  "reference_roi_left": { "rx1": 0.25, "ry1": 0.45, "rx2": 0.5, "ry2": 0.85 },
  "reference_roi_right":{ "rx1": 0.5,  "ry1": 0.45, "rx2": 0.75,"ry2": 0.85 },
  "aggregation": "OR",
  "model": "logistic",
  "features": ["lap_var", "mean", "std", "edge_den", "grad_mag"],
  "decision_threshold": 0.5,
  "trained_on": {
    "n_contact": 10, "n_non_contact": 14,
    "resolution": { "width": 1280, "height": 1024 }
  }
}
```

`reference_roi` 保留為 LEFT（為了與 v1 monitor 設定相容），同時 `reference_roi_left` / `reference_roi_right` 給 UI 用來同時畫兩個 overlay 框。

### `POST /api/v1/predict`

`multipart/form-data`，單一欄位 `file`。上傳 **完整 RCM 截圖**（任何解析度都可以，API 會自行 resize）。

```bash
curl -s -X POST http://localhost:8000/api/v1/predict \
  -F 'file=@samples/contact.png' | jq .
```

**contact response 範例**：

```json
{
  "status": "contact",
  "aggregation": "OR",
  "probability_contact": 0.8992,
  "roi_image":       "/local_output/contact/cropped_20261111_100333_476.jpg",
  "fullframe_image": "/local_output/contact/20261111_100333_476.jpg",
  "per_roi": {
    "left":  { "status": "contact", "probability_contact": 0.8992, "laplacian_score": 24.26,
               "features": {"lap_var":24.2579,"mean":55.1226,"std":22.961,"edge_den":0.0145,"grad_mag":41.1918} },
    "right": { "status": "contact", "probability_contact": 0.559,  "laplacian_score": 31.77,
               "features": {"lap_var":31.774, "mean":21.1542,"std":18.8988,"edge_den":0.0111,"grad_mag":15.0586} }
  }
}
```

**non_contact response 範例**（`roi_image` 為 null，`fullframe_image` 有值）：

```json
{
  "status": "non_contact",
  "aggregation": "OR",
  "probability_contact": 0.0387,
  "roi_image": null,
  "fullframe_image": "/local_output/non-contact/20261111_100333_520.jpg",
  "per_roi": {
    "left":  { "status": "non_contact", "probability_contact": 0.0018, ... },
    "right": { "status": "non_contact", "probability_contact": 0.0387, ... }
  }
}
```

**欄位說明**：

| 欄位 | 說明 |
|---|---|
| `status` | OR 聚合的最終判定：`contact` 或 `non_contact` |
| `aggregation` | 固定為 `"OR"`（至少一側判定為 contact 即為 contact） |
| `probability_contact` | `max(per_roi.left.p, per_roi.right.p)` ——驅動 OR 的那一側的 probability |
| `roi_image` | overall contact 時為串接過的 ROI 影像 URL；overall non_contact 時為 `null` |
| `fullframe_image` | 一律有值——resized 原圖 (1280×1024) 加上兩個**黃色** ROI 外框 |
| `per_roi.left` / `per_roi.right` | 單側的 status、probability、laplacian_score、5 features |

### `GET /local_output/contact/<file>.jpg` 與 `/local_output/non-contact/<file>.jpg`

以 FastAPI StaticFiles 提供。URL path 可直接拼接服務 base URL，例如：
`http://192.168.137.101:8000/local_output/contact/20261111_100333_476.jpg`

---

## 7. 批次掃描工具 — `scan_batch.py`

v2 的 scanner 印出 OVERALL + LEFT + RIGHT 三組狀態 / 機率，讓你一眼看到是哪一側驅動判定。

```bash
python scan_batch.py samples/
```

預期輸出（示意）：

```
AOI API      : http://localhost:8000
variant      : dual-roi-or  aggregation=OR
input resize : 1280×1024
LEFT  ROI    : (0.25, 0.45, 0.5, 0.85)
RIGHT ROI    : (0.5, 0.45, 0.75, 0.85)
files found  : 2

file                                       OVERALL      p(c) | LEFT         L_p     R            R_p    |     ms
-----------------------------------------------------------------------------------------------------------
contact.png                                contact     0.899 | contact     0.899  contact     0.559 |   28.1
non_contact.png                            non_contact 0.039 | non_contact 0.002  non_contact 0.039 |   24.7
-----------------------------------------------------------------------------------------------------------
```

**有 label 時量測準確率**：資料放到 `<root>/contact/`、`<root>/non-contact/`，加 `--labeled`。

```bash
python scan_batch.py /path/to/labeled_root/ --labeled
```

輸出會多一個 `truth` 欄位 + `accuracy` summary。

**存成 CSV**：
```bash
python scan_batch.py samples/ --csv v2_results.csv
```

CSV 會包含 overall + 兩側 status / prob / lap_var + 兩個已儲存檔案的 URL path。

---

## 8. `contact-monitor-service` 應該怎麼呼叫這個 API

**跟 v1 幾乎一樣**：直接把 RCM snapshot 以 `file` 欄位 POST 給 `/api/v1/predict`，**不要裁切、不要 resize**。v2 不再要求相機解析度必須是 1540 × 1050——API 會把所有輸入 resize 到 1280 × 1024 再處理。

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
# resp["status"]               → "contact" or "non_contact"   (OR 聚合)
# resp["probability_contact"]  → max(left.p, right.p)
# resp["per_roi"]["left"]      → {status, probability_contact, laplacian_score, features}
# resp["per_roi"]["right"]     → 同上
# resp["roi_image"]            → cropped (LEFT|RIGHT) URL；non_contact 時為 null
# resp["fullframe_image"]      → 1280×1024 原圖 + 兩個黃色 ROI 外框 URL
```

### 單邊 debug 用途

`per_roi.left.status` 與 `per_roi.right.status` 可以獨立觀察：

- 若一邊常常 contact、另一邊常常 non_contact，代表 probe card 的對稱性不符合這個 mirror 假設，或是相機 framing 偏向一側。
- OR 聚合會以較強的一側為準；想切換成 AND（兩邊都要 contact）或 single-left 的話，改 prob_api.py 的 OR 判定邏輯即可（已標註在程式註解裡）。

### 儲存量估算 + 檔案回收

Monitor 每 `aoi.interval_ms` 呼叫一次（預設 200 ms = 5 Hz）。每次 AOI 寫：
- **一行 JSONL log**（約 600 B，含 per_roi）
- **一張 1280×1024 原圖**（帶兩個黃色 ROI 外框，~170 KB），依 status 存到 contact/ 或 non-contact/
- **僅 overall contact 時**多寫一張 LEFT|RIGHT 串接的 crop（~70 KB）

粗估：

- 每小時 log：18,000 × ~600 B ≈ **~10 MB**（daily rotate，`logging.backup_count` 預設保留 7 天）
- 每小時原圖：18,000 × ~170 KB ≈ **~3 GB**（大多分流到 non-contact/）
- 每小時 crop：取決於 contact 事件比例
- 檔案回收 service 要清理：
  - `paths.contact_dir`、`paths.non_contact_dir` （建議保留 24 小時）
  - `paths.log_dir` 內已輪替的 `aoi_api.log.YYYY-MM-DD`（當日 `aoi_api.log` 請勿刪除）

---

## 9. 特徵說明

與 v1 相同——5 個特徵都計算於 ROI 的灰階影像、且經過 5×5 Gaussian blur：

| Feature     | 衡量目標 | v2 模型權重 |
|-------------|---------|---------:|
| `lap_var`   | Laplacian 變異數——銳利度 / 高頻訊號 | **+2.12** |
| `grad_mag`  | Sobel gradient magnitude 平均——整體邊緣強度 | **+1.29** |
| `edge_den`  | Canny edge pixel 比例 | **+1.34** |
| `mean`      | 灰階平均強度 | +0.40 |
| `std`       | 灰階強度 std-dev | −0.64 |
| *intercept* | | −0.99 |

預測公式：`sigmoid( weight · ((feature − mean) / std) + intercept )`，在 0.5 處做判定。

同一組 weights / means / stds **同時套用在 LEFT 和 RIGHT crop 上**；因為訓練資料中 LEFT ROI 的 contact signature 就是「對焦條紋」，mirror 後的 RIGHT crop 若同時 in-focus 也會被捕捉到。

---

## 10. 相機 / FOV / resize 變更時的重新校正

v2 對 **input_resize 的尺寸**也很敏感——不同 resize target 會改變單位面積的 pixel 數量，連帶使 `lap_var`、`grad_mag`、`edge_den` 的絕對值大小整體偏移。所以若要調整 `config/aoi_api.json` 的 `input_resize`，請一併重新校正。

重新校正流程（給 API owner）：
1. 收集至少 10 張 contact + 14 張 non_contact 的 labeled 影像（放到 `PROB/input/<date>/contact/` 和 `non-contact/`）。
2. 把目標 resize 尺寸填進校正 script 的 `TARGET` 常數。
3. 執行 script，它會把影像 resize → 裁 LEFT ROI → 跑 logistic → 覆蓋 `aoi-api-package_v2/local_output/calibration.json`。
4. 不必改 `prob_api.py`。

---

## 11. 待確認事項（截至此版）

1. **OR vs AND 聚合**：目前採用 OR（24 張 labeled 準確率 95.8% vs. AND 的 83.3%）。單邊足以觸發 contact 的假設是「只要 probe card 任一側對焦就可以視為接觸」；若實際需要兩側都接觸才算，改成 AND 很容易（一行判定邏輯）。
2. **Right ROI 的 FP 風險**：OR 把兩側聯集起來，等同於判定面積變大，容易把 non_contact 影像中「右側恰好有紋理」的情況誤判為 contact（24 張裡的 1 個 FP：`Screenshot 2026-11-06 130643.png`）。如果發現 FP 比 FN 重要，請考慮：
   - 換 AND 聚合（更嚴）
   - 只用 LEFT ROI（等同 v1 單邊，24 張 100% accuracy）
3. **跟 v1 共存**：v2 是獨立 package，服務 port 都是 8000；若要同機同時跑 v1 + v2，請把其中一個改用別的 port（例如 v2 設 `server.port: 8001`）。

---

## 12. 疑難排解

| 現象 | 可能原因 | 修正方式 |
|---|---|---|
| `GET /api/v1/health` 回傳 `"calibrated": false` | `calibration.json` 缺失或格式有誤 | 從本 package 還原該檔案 |
| 所有判定都是 contact | 相機 framing 嚴重偏移、mirror ROI 碰到其他 UI 元件 | 用 `per_roi` 看哪一側異常；可能需要重新校正或改用 AND |
| 所有判定都是 non_contact | 1280×1024 resize 把內容縮得太小 / 失焦 | 嘗試其他 resize 尺寸並重新校正（§10） |
| POST 回 `422 Unprocessable Entity` | multipart 欄位名錯誤 | 欄位名必須完全是 `file` |
| POST 回 `500` 且訊息含 `計算出的 ROI 範圍無效` | 上傳的圖太小（resize 後小於 ROI） | 確認相機能提供至少 1280×1024 以上的影像 |
| POST 回 `500` 且訊息含 `calibration missing` | calibration.json 損壞或缺少 feature 資訊 | 從 package 還原，重新啟動服務 |
| 啟動時 stderr 出現 `WARN: config ... not found — using defaults` | config 檔不存在或路徑錯 | 確認從 package 根目錄啟動；或設定 `AOI_API_CONFIG` |
| Latency > 200 ms | AOI 本身約 25–50 ms，問題不在 AOI | 檢查網路以及 RCM 取圖時間 |
