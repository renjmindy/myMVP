# CD-SEM Predict API 使用說明（給 Zack / RPA）

## 1. 這個 API 做什麼

RPA 上傳一張**全螢幕截圖**，API 會自動完成：

1. 將截圖縮放到標準尺寸（1920×1000）並移除滑鼠游標
2. 以定位標記自動裁切出 **t1**（Template Monitor 預覽圖）與 **m1**（主 SEM 影像）
3. 解析倍率（OCR）
4. 在 m1 上比對 t1（粗比對 + 細比對）
5. 找出 t1 中**白色矩形的中心點**（沒有白色矩形時，改用 t1 的中心點），並換算成**截圖上的座標**
6. 回傳是否匹配成功及該座標

回傳座標以**上傳截圖的左上角為原點 (0,0)**，是全螢幕截圖下的座標，RPA 可直接拿來滑鼠點擊。

> 每次判斷約 1 秒。伺服器一次只處理一張圖（請依序呼叫，不要同時送多張）。

---

## 2. 資料夾內容

| 檔案 / 資料夾 | 說明 |
|---|---|
| `cdsem_api.py` | API 本體（FastAPI） |
| `cdsem-crop.py` | 影像辨識核心（API 會自動載入，請勿移動或改名） |
| `template/` | 定位用的樣板圖：`align_hold.png`、`align_mag.png`、`cursor.png`（**必須與程式放在一起**） |
| `requirements.txt` | Python 套件清單（已鎖定測試過的版本） |
| `setup.bat` / `setup.sh` | 首次安裝（Windows / Linux） |
| `start_api.bat` / `start_api.sh` | 啟動 API（Windows / Linux） |
| `examples/call_predict.py` | 呼叫範例（只用 Python 標準函式庫） |
| `samples/` | 兩張測試截圖：`sample_found.jpg`（應找到）、`sample_notfound.jpg`（應找不到） |

---

## 3. 環境需求

- **Python 3.12 以上**（測試版本：3.13）
- **Tesseract OCR 5.x**（辨識倍率用）
  - Windows：安裝 UB Mannheim 版安裝程式（預設路徑 `C:\Program Files\Tesseract-OCR\tesseract.exe`），安裝時請保留英文語言資料（預設已包含）。
  - Linux / WSL：`sudo apt-get install -y tesseract-ocr`

---

## 4. 安裝（只需做一次）

**Windows**

1. 安裝 Python 3.12 以上與 Tesseract OCR。
2. 在資料夾中雙擊 `setup.bat`（會建立 `.venv` 並安裝套件）。

**Linux / WSL**

```bash
sudo apt-get install -y tesseract-ocr
./setup.sh
```

---

## 5. 啟動

**Windows**：雙擊 `start_api.bat`
**Linux / WSL**：`./start_api.sh`

看到 `Uvicorn running on http://0.0.0.0:8000` 即啟動成功（預設 port 8000）。

快速確認：

```
curl http://localhost:8000/health
→ {"status":"ok"}
```

用內附樣本測試：

```
python examples/call_predict.py samples/sample_found.jpg
→ {"found":true,"x":1222,"y":659}

python examples/call_predict.py samples/sample_notfound.jpg
→ {"found":false,"x":-1,"y":-1}
```

> 注意：請只啟動**一個**服務程序（不要加 `--workers`）。

---

## 6. API 規格

### `POST /predict`

以 `multipart/form-data` 上傳：

| 欄位 | 必填 | 說明 |
|---|---|---|
| `file` | 是 | 全螢幕截圖（png / jpg） |
| `timestamp` | 否 | 格式 `yyyymmdd_HHMMss`（24 小時制，例如 `20261014_204421`）。用於儲存影像的檔名。**建議由 Zack 產生後寫入自己的 Log，並一併傳給 API**，這樣 Log 與影像檔名一定對得上。不傳或格式錯誤時，改用伺服器時間。 |

**回傳（HTTP 200，單行 JSON，永遠只有這三個欄位）**

偵測到：
```json
{"found":true,"x":1250,"y":680}
```
未偵測到：
```json
{"found":false,"x":-1,"y":-1}
```

| 欄位 | 型態 | 說明 |
|---|---|---|
| `found` | Boolean | 是否匹配成功 |
| `x` | Integer | 點擊用的 X 座標；未偵測到為 -1 |
| `y` | Integer | 點擊用的 Y 座標；未偵測到為 -1 |

**額外資訊在回應標頭**（不在 JSON 內，不影響 RPA 解析）：

| 標頭 | 說明 |
|---|---|
| `X-Image` | 已儲存的影像檔名，例如 `Image_Predicted_20261014_204421.jpg` |
| `X-Reason` | 只有在 `found:false` 時才有，說明原因（見下表） |

**`X-Reason` 對照**

| 內容 | 意思 |
|---|---|
| `no match` | 找到 Template 視窗，但 t1 與 m1 匹配失敗 |
| `Template match score too low (…); anchor not found.` | 畫面上找不到定位標記（可能 Template Monitor 或 Magnification 區域沒有出現在截圖中） |
| `no coarse match` | 粗比對失敗 |
| `point outside screen` | 匹配成功，但換算出的點落在截圖範圍之外（安全機制，不回傳不合理座標） |
| `unreadable image` | 上傳的檔案不是有效影像 |
| 其他 `error…` | 程式內部錯誤，請把該張影像與 Log 提供給我們 |

> 任何失敗一律回傳 `{"found":false,"x":-1,"y":-1}`，HTTP 狀態碼仍為 200。只有漏傳 `file` 欄位時會回 HTTP 422。

**匹配成功的判斷標準**（`found` 只依匹配結果決定）

- 倍率 **< 20k**：粗比對分數 ≥ 0.40 **或** 細比對分數 ≥ 0.25
- 倍率 **≥ 20k**：粗比對分數 ≥ 0.40 **且** 細比對分數 ≥ 0.25

---

## 7. 儲存的影像（方便釐清 RPA 問題）

每次呼叫 `/predict` 都會把判斷過的截圖存成：

```
Image_Predicted_{yyyymmdd_HHMMss}.jpg
```

- 偵測到：在回傳的 (x, y) 位置畫**紅色十字加圓圈**。
- 未偵測到：存原始截圖（不畫十字），方便事後分析失敗原因。
- 同一個 timestamp 重複時，不會覆蓋，會自動加 `_2`、`_3`。
- 預設存放在 `predicted/` 資料夾，可用環境變數 `CDSEM_IMAGE_DIR` 更改。

**網頁下載**（瀏覽器開啟 `http://<伺服器IP>:8000/`）

| 網址 | 功能 |
|---|---|
| `/` | 網頁：由新到舊列出影像縮圖、下載連結、「Download all (zip)」，可用日期（`yyyymmdd`）篩選 |
| `/images` | JSON 清單（可加 `?date=yyyymmdd`、`?limit=N`） |
| `/images/{檔名}` | 在瀏覽器顯示影像；加 `?download=true` 則下載檔案 |
| `/images.zip` | 全部影像打包下載（可加 `?date=yyyymmdd` 只下載某一天） |

無瀏覽器時可用 curl：
```
curl -o predicted.zip "http://<伺服器IP>:8000/images.zip"
```

---

## 8. 環境變數（皆為選填）

| 變數 | 說明 | 預設 |
|---|---|---|
| `PORT` | 服務 port（由 start 腳本讀取） | 8000 |
| `HOST` | 監聽位址（由 start 腳本讀取） | 0.0.0.0 |
| `CDSEM_IMAGE_DIR` | 存放 `Image_Predicted_*.jpg` 的資料夾 | `./predicted` |
| `CDSEM_DATA_DIR` | 含 `template/` 的資料夾 | 程式所在資料夾 |
| `TESSERACT_CMD` | `tesseract` 執行檔完整路徑（不在 PATH 時需要） | Windows 預設路徑會自動偵測 |

---

## 9. 呼叫範例

**curl**（Windows PowerShell 請用 `curl.exe`）

```
curl -i -F "file=@C:\snap\snapshot.png" -F "timestamp=20261014_204421" http://<伺服器IP>:8000/predict
```

**Python**：見 `examples/call_predict.py`

**C#**（範例；**未實際編譯測試**，請依專案調整）

```csharp
using System.Net.Http;
using System.Net.Http.Headers;
using System.Text.Json;

using var client = new HttpClient();
using var form = new MultipartFormDataContent();

// .NET 的時間格式是 yyyyMMdd_HHmmss（MM = 月、mm = 分、HH = 24 小時）
string stamp = DateTime.Now.ToString("yyyyMMdd_HHmmss");   // 請同時寫入 Zack 的 Log
form.Add(new StringContent(stamp), "timestamp");

var img = new ByteArrayContent(File.ReadAllBytes(snapshotPath));
img.Headers.ContentType = new MediaTypeHeaderValue("image/png");
form.Add(img, "file", Path.GetFileName(snapshotPath));

var resp = await client.PostAsync("http://<伺服器IP>:8000/predict", form);
string json = await resp.Content.ReadAsStringAsync();

using var doc = JsonDocument.Parse(json);
bool found = doc.RootElement.GetProperty("found").GetBoolean();
int x = doc.RootElement.GetProperty("x").GetInt32();
int y = doc.RootElement.GetProperty("y").GetInt32();
// resp.Headers.TryGetValues("X-Image", ...) 可取得儲存的影像檔名
```

---

## 10. 與 Zack 主控流程的對應

1. 截圖 → 呼叫 `/predict` 上傳。
2. `found:true` → 依 `x`、`y` 滑鼠點擊 → 點擊 OK 按鈕 → 搜尋下一個觀測點。
3. `found:false` → 換下一個座標重新截圖、呼叫。
4. 掃描一圈都失敗 → 由 Zack 的程式發出 Alarm 請 OP 介入。事後可到 `/` 網頁或 `predicted/` 資料夾，用 `Image_Predicted_{timestamp}.jpg` 查看當時的影像，並對照 `X-Reason` 與服務 Log 釐清原因。

API 本身不保存流程狀態；掃描順序、重試與 Alarm 都由 Zack 的主控程式控制。

---

## 11. 疑難排解

| 狀況 | 處理 |
|---|---|
| 啟動時出現 `address already in use` | port 已被占用：關閉舊的服務程序，或改用其他 port（`set PORT=8001` / `PORT=8001 ./start_api.sh`） |
| 一直回傳 `found:false`，`X-Reason` 為 `Template match score too low…` | 截圖裡沒有 Template Monitor 的 Hold 按鈕或 Magnification 標籤，或截圖尺寸／版面與校準時不同；確認截的是 1680×1050 的 SEM 完整畫面（見第 13 節） |
| 倍率一直讀不到 / 回傳失敗 | 確認 Tesseract 已安裝，必要時設定 `TESSERACT_CMD` |
| 別台電腦連不上 | 改用伺服器 IP（不是 `localhost`），並確認防火牆已開放該 port（Linux：`sudo ufw allow 8000/tcp`） |
| 想看每次判斷的分數 | 看服務視窗的 Log：每次呼叫會印出 `found`、座標、倍率、粗/細比對分數 |

---

## 12. 已知限制

- **截圖尺寸**：目前以 1680×1050 的截圖調校。非 1920×1000 的截圖會先縮放到 1920×1000，最後再換算回原圖座標。**若實際截圖是帶有視窗標題列與工作列的 1920×1080 桌面，縮放會造成變形，請先與我們確認截圖來源與尺寸。**
- **匹配門檻**：門檻依目前樣本設定。部分「匹配成功」的案例細比對分數偏低（例如倍率 4.00k、10.0k），其座標可能有數個像素的誤差；可用儲存的影像確認。
- **無驗證機制**：任何能連到該 port 的人都可呼叫 API，也能下載儲存的影像（影像內含 SEM 畫面）。請限制在內網，必要時再加上 API Key。
- **影像不會自動清除**：每張約 0.5–0.7 MB，請定期清理 `predicted/` 資料夾。
- **Windows 腳本未在 Windows 上實測**：`setup.bat`、`start_api.bat` 是依 Linux 版對應撰寫，如有問題請回報。

---

## 13. 影像樣本準備指南

**為什麼重要：** 程式會先在畫面上找兩個固定的定位標記：**Hold 按鈕**與 **Magnification（倍率）標籤**，再依照固定的像素位移切出 Template 預覽圖與 SEM 影像。所以每一張影像（無論是 RPA 上傳的截圖，或用來測試的樣本）都必須跟程式當初校準時的畫面一致。

### 必須做到

1. **以 SEM 畫面的原生解析度 1680×1050 截圖。** 目前所有可正常處理的影像都是這個尺寸。
2. **只截 SEM 畫面本身。** 不要有黑邊、視窗標題列、工作列，也不要有瀏覽器或遠端桌面的外框。
3. **不要縮放、裁切、放大或旋轉**截圖，也不要讓截圖工具或系統顯示比例（例如 Windows 顯示縮放 125%）改變影像尺寸。
4. **SEM 視窗請維持正常配置。** 不要移動或調整 Template Monitor 與 SEM 影像視窗的位置或大小；裁切位置是固定的，視窗移位就會裁錯。
5. **以下三處必須完整可見、不被遮住：**
   - Template Monitor 的 **Hold** 按鈕
   - **Magnification** 標籤與其數值（例如 `4.00k`）
   - SEM 影像區域

   只要有對話框或視窗蓋住其中一處，定位就會失敗。
6. **畫質要清晰。** 避免過度壓縮、模糊或加濾鏡，因為定位與倍率文字辨識都依賴清楚的像素。目前驗證過的樣本都是 **JPG**（138 張，皆為 1680×1050）；程式也接受 PNG，但**尚未用 PNG 實際測試過**。
7. **離線批次測試時的檔名與資料夾**（使用 `cdsem-crop.py` 對整個資料夾跑一遍）：檔名用 `cdsem1.jpg`、`cdsem2.jpg`…，放在資料集的 `input/` 資料夾；與它同層的 `template/` 資料夾必須包含 `align_hold.png`、`align_mag.png`、`cursor.png`。透過 API 上傳時，檔名不限。

### 建議做到

- 盡量涵蓋不同倍率（例如 4.00k、30k、150k），每種情況都能被測試到。
- 也請包含「SEM 影像裡確實看得到 Template 圖案」的截圖。圖案不在畫面中的截圖，程式會正確回報「找不到」。
- 滑鼠游標可以留在畫面上，程式會自動移除；但請避免游標停在 Hold 按鈕或倍率文字上。

### 交件前的自我檢查

影像應該是 1680×1050，外觀與先前的樣本相同、沒有黑邊。最可靠的確認方式是實際送一次（例如 `python examples/call_predict.py <截圖>`），看 `X-Reason` 是否出現 `anchor not found`。

### 如果一定得用其他截圖尺寸

程式必須重新校準：需要從該尺寸的截圖重新裁切 `template/align_hold.png` 與 `template/align_mag.png`，並重新量測腳本中的裁切位移。這屬於開發工作，無法由提供樣本的人自行解決。

### 實際案例（供參考）

一張 **1024×768、上下帶黑邊**的 SEM 截圖，縮放後 Hold 定位標記的比對分數只有 0.567，低於所需的 0.75，因此回報 "anchor not found"，無法處理。
