# Workflow：LINE Bot / Email 通道串接

> 知識庫建好後，把回覆通道接起來，客戶問問題就能自動比對回覆。

---

## 觸發條件

- 「幫我接 LINE Bot」
- 「幫我設定自動回覆」
- 「客戶問題怎麼自動回」

---

## 設定前先講清楚

> 「要做到『客戶問問題，自動準確回覆』，有兩條路，可以都接：
> A. **LINE Bot**（客戶熟悉、互動即時）
> B. **Email 客服信箱**（適合正式詢問、報價類問題）
> 你想先接哪個？」

---

## A. LINE Bot 串接

### 設定步驟

1. 到 [LINE Developers](https://developers.line.biz/) 建立一個 Messaging API Channel
2. 取得 **Channel Access Token** 和 **Channel Secret**
3. 設定 Webhook URL（需要一個能接收 LINE 訊息的伺服器端點）
4. 把憑證存進設定檔（例如 `~/.claude/skills/_base/tool-inventory.md` 備註欄）

> 🔒 Channel Access Token 等同密碼，不要貼進會同步/分享的雲端資料夾。

### 運作方式

```
客戶在 LINE 傳訊息
        ↓
Webhook 收到訊息內容
        ↓
Ada 比對 references/faq.md
        ↓
有答案 → 自動回覆
沒答案 → 回覆「幫你轉真人客服，稍後跟進」+ 標記待辦
```

### 回覆訊息 API

```bash
curl -X POST "https://api.line.me/v2/bot/message/reply" \
  -H "Authorization: Bearer {Channel Access Token}" \
  -H "Content-Type: application/json" \
  -d '{
    "replyToken": "{從 webhook 收到的 replyToken}",
    "messages": [{"type": "text", "text": "{比對後的回覆內容}"}]
  }'
```

> ⚠️ LINE 的自動回應也可以直接用官方帳號後台內建的「關鍵字自動回應」功能（免伺服器，跑在 LINE 雲端）——把 `references/faq.md` 轉成關鍵字格式貼進後台即可，適合不想架伺服器的用戶。

---

## B. Email 客服信箱串接

1. 確認要用哪個信箱作為客服信箱
2. 若已有 Gmail 串接（可能與 Robin 共用同一組授權），確認能讀取該信箱的來信
3. 設定比對邏輯：

```
新客服信件進來
        ↓
Ada 讀取信件內容
        ↓
比對 references/faq.md
        ↓
有答案 → 草擬回覆（建議先設定為草稿，人工確認後發送，穩定後可轉全自動）
沒答案 → 標記「待真人回覆」，交給 Robin 彙整進信箱日報
```

> 建議 Email 通道先從「自動草擬回覆、人工確認發送」開始，穩定一段時間、確認回覆品質沒問題後，再考慮全自動發送。

---

## 接好之後：更新工具盤點

回 `~/.claude/skills/_base/tool-inventory.md`，把 LINE Bot、Email 客服信箱狀態改成 ✅。

---

## ⚠️ 老實話：24 小時無人值守需要什麼

通道接好，代表「客戶問問題時能觸發自動比對回覆」這件事本身不需要用戶開著電腦——LINE Webhook 和 Email 收信都是雲端觸發。但如果要做到「比對邏輯」也完全在雲端跑（不是每次都經過用戶手動確認），需要把整套流程部署成常駐服務（例如 Vercel Functions），這屬於進階設定，值得投資但需要額外的部署步驟，可以請 Kai 協助建立部署環境。
