# Workflow：Buffer / 排程 API 串接設定

> 帶用戶把排程工具接起來，接好之後 Mia 才能真正「定時自動發布」。

---

## 觸發條件

- 「幫我設定」（在 Mia 情境下）
- 「幫我接 Buffer」
- 「想要自動發文」

---

## 設定前先講清楚

> 「要做到『排好之後自動發布，不用手動貼』，有兩條路：
> A. **Buffer**（最簡單，一個工具管多平台，適合大部分人）
> B. **IG / Threads 官方 API**（功能更完整，但設定步驟較多）
> 你想接哪個？」

---

## A. Buffer 串接

1. 到 [buffer.com](https://buffer.com) 註冊（免費方案可管 3 個社群帳號）
2. 連結你的 IG / Threads 帳號到 Buffer
3. 到 Buffer 後台 → Settings → 找到 **API Access Token**
4. 把 Token 存進憑證設定檔（例如 `~/.claude/skills/_base/tool-inventory.md` 備註欄）

> 🔒 API Token 等同密碼，不要貼進會同步/分享的雲端資料夾。

5. 測試：「幫我在 Buffer 排一則測試貼文」驗證串接成功

**用 Buffer API 排程貼文：**

```bash
curl -X POST "https://api.bufferapp.com/1/updates/create.json" \
  -d "access_token={TOKEN}" \
  -d "profile_ids[]={PROFILE_ID}" \
  -d "text={貼文文案}" \
  -d "scheduled_at={排程時間，unix timestamp}"
```

---

## B. IG / Threads 官方 API 串接

> ⚠️ **前提：IG 帳號要是「專業帳號」（商業/創作者），個人帳號完全不能用 API。**

### IG 解卡步驟

```
Step 1：IG 轉專業帳號（設定 → 帳號類型與工具 → 切換成專業帳號）
Step 2：IG 連結到 FB 粉專
Step 3：把帳號加進 Meta App 角色（App 後台 → 應用程式角色）
Step 4：重新產生 Token，勾選 instagram_content_publish 權限
Step 5：確認 IG Business Account ID（GET /{粉專ID}?fields=instagram_business_account）
```

### 發文機制（兩步驟，圖片需公開 URL）

> 🔎 圖片必須是公開網址（http/https 開頭）。本機檔案、私人連結 IG 抓不到——需要先有圖片托管服務給的公開連結。

```bash
# 1. 建立 media container
curl -X POST "https://graph.facebook.com/v25.0/{IG_ID}/media" \
  -F "image_url={圖片URL}" -F "caption={文案}" -F "access_token={TOKEN}"

# 2. 發布
curl -X POST "https://graph.facebook.com/v25.0/{IG_ID}/media_publish" \
  -F "creation_id={container id}" -F "access_token={TOKEN}"
```

### ⚠️ IG 排程限制（先跟用戶講清楚）

- IG **立即發文** → 設定通了就能做
- IG **原生未來排程** → IG API 不支援，要嘛時間到時觸發發布，要嘛用 Meta 內建工具排
- 上限：每 24 小時最多 25 篇

---

## 接好之後：更新工具盤點

排程工具接好，回 `~/.claude/skills/_base/tool-inventory.md` 把對應狀態改成 ✅，並補上接的日期。

---

## 讓排程真的「定時」跑

接好工具只代表「Mia 有能力發文」，要讓它在指定時間自動觸發，還需要：

- **Buffer**：Buffer 本身內建排程佇列，設定好發布時間後由 Buffer 自己執行，不需要額外排程工具
- **官方 API 直發**：需要 Cron / Vercel Cron 在指定時間呼叫發文流程，電腦關著也要能跑才算真正全自動

> 建議大多數用戶先用 Buffer——內建排程最省事，不用自己顧觸發時間。
