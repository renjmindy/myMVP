# 進階串接教學：LINE 整合（Robin／Theo／Ada 共用）

> 這是**進階、選用**功能。先講最重要的一句話：**LINE 這邊「免費」跟「即時智能回覆」也是二選一**，跟 Google Ads 的處境很像——想免費、免伺服器 → 只能做關鍵字式自動回應；想要真正即時的 AI 語意回覆 → 得自己架一台會一直開著的伺服器。
>
> ⚠️ 沒接也完全不影響你用團隊——Robin／Theo／Ada 一樣能把日報、監控報告、客服回覆準備好，你手動貼到 LINE 發送或設定。

---

## ① 先看清楚：哪些做得到、哪些做不到

| 你想做的事 | LINE 內建（免費、免伺服器） | Messaging API（免費額度有限） | 自架 Webhook 伺服器（技術門檻較高） |
|---|---|---|---|
| 群發訊息給所有好友 | — | ✅ 每月有免費則數上限，超過按則收費 | ✅ 同左 |
| 關鍵字自動回應（FAQ 式） | ✅ 後台直接設定，最推薦 | — | — |
| 即時讀取客戶傳來的訊息、AI 語意判斷回覆 | ❌ 沒有讀取訊息的入口 | ❌ 需要 webhook 才能接收 | ✅ 但要有一台隨時在線的伺服器 |
| 排程未來某天發送 | — | 需自己寫排程觸發（Cron/Vercel Cron） | 同左 |

> 一句話總結：**「免費」跟「即時智能回覆」在 LINE 這邊目前二選一。** 想免費又免設定 → 用 LINE 內建關鍵字自動回應；想要真正智能回覆 → 得架一台伺服器接 webhook。

---

## ② 最推薦：LINE 內建關鍵字自動回應（免費、免伺服器）

這是**多數人真正需要的方案**——不用寫程式、不用架伺服器，跑在 LINE 自己的雲端上，電腦關了照樣運作。

1. 打開 [LINE Official Account Manager](https://manager.line.biz/)，登入你的 LINE 官方帳號
2. 左側選單找「**自動回應訊息**」（或「Auto-reply messages」）
3. 新增一則回應：設定「關鍵字」→ 設定「回覆內容」
4. 開啟這則自動回應

Ada 會幫你把知識庫轉成這個格式：

```
關鍵字：多少錢、費用、價格
回覆：[清楚的答案]

關鍵字：退貨、換貨
回覆：[清楚的答案]
```

你把這些一組一組貼進後台設定就完成了。

> ✅ 這條路**免費版、付費版都能用**——因為運作完全在 LINE 自己的雲端，跟 Claude 有沒有連線無關。

---

## ③ 群發 / 推播：Messaging API（需要一組憑證）

想讓 Robin（信箱重點）、Theo（監控日報）主動推一則訊息給你自己，或想群發通知給客戶，需要申請 Messaging API 憑證：

### 申請步驟

1. 打開 [LINE Developers Console](https://developers.line.biz/console/)，用你的 LINE 帳號登入
2. 建立一個 **Provider**（服務提供者，取個名字即可，例如你的品牌名）
3. 在該 Provider 下建立一個 **Messaging API Channel**
4. 進到該 Channel 的「Messaging API」分頁，找到：
   - **Channel access token**（點「Issue」產生一組）
   - **Channel secret**（在「Basic settings」分頁）

> 🔒 **這兩組憑證等於密碼**：別截圖外傳、別貼進會同步分享的雲端資料夾。只存在自己電腦的設定檔裡。哪天要作廢，回 Console 重新產生一組即可讓舊的失效。

### 測試推播

把 Channel access token 給 Claude（或存進你自己的設定檔），跟對應成員說「幫我測試推播一則訊息」，他會用這個指令驗證：

```bash
curl -X POST "https://api.line.me/v2/bot/message/broadcast" \
  -H "Authorization: Bearer {Channel access token}" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"type":"text","text":"測試訊息"}]}'
```

你的 LINE 收到這則訊息，就代表設定成功。

> ⚠️ **免費額度有限**：群發超過當月免費則數會開始按則收費，發大量前先確認你的方案額度（LINE Developers Console 可查）。

---

## ④ 真的要「即時智能回覆」：需要自架 Webhook 伺服器（技術門檻較高）

如果你要的是「客戶傳訊息進來，AI 立刻讀懂、比對知識庫、自動回覆」，這件事**在網頁版或單純 Claude Code 對話裡做不到**——LINE 只能透過 **webhook**（一個你架設、永遠在線的網址）把訊息即時推給你的程式，Claude Code 本身不是一台隨時開著的伺服器。

### 前提

| 前提 | 說明 |
|------|------|
| **一個公開的 HTTPS 端點** | 需要部署一支會一直運作的小程式，接收 LINE 傳來的 webhook |
| **Vercel Functions（推薦）** | 可以請 **Kai** 協助——他熟悉 Vercel 部署，能幫你把「接收 LINE 訊息 → 比對 Ada 的知識庫 → 呼叫 LINE API 回覆」包成一支雲端函式 |
| **Channel secret** | 用來驗證 webhook 請求真的來自 LINE（見上方②申請步驟拿到的那組）|

### 怎麼開始

跟 Kai 說：

```
/kai-pages 我想架一個 LINE Webhook，接收訊息後比對 Ada 的知識庫自動回覆，幫我設計架構
```

他會協助設計部署架構；實際的知識庫比對邏輯由 Ada 提供。

> 🙋 **老實建議**：如果你看到「webhook」「伺服器」就頭痛，**這條可以先不做**。用 ② 的 LINE 內建關鍵字自動回應，多數常見問題都能覆蓋，而且完全免費、免維護。等哪天真的量大到關鍵字不夠用，再回來考慮這段。

---

## ⑤ 動手前一定要知道的幾件事

- ⚠️ **LINE 沒有「讀取收到訊息／對話列表」的一般 API**——訊息只能靠 webhook 即時接收，這是 LINE 平台本身的限制，不是團隊做不到。
- ⚠️ **「免費」和「即時智能回覆」二選一**：免費、免伺服器 → 走內建關鍵字自動回應；要真正智能 → 得自架伺服器（有技術門檻，或請 Kai 協助）。
- 🔒 **Channel access token / secret 等於鑰匙**：只留自己電腦那份，別截圖外傳、別放公開雲端。不用了回 LINE Developers Console 重新產生即可作廢舊的。
- ✅ **不接 Messaging API 也完全 OK**：LINE 內建關鍵字自動回應免費、免伺服器，涵蓋多數客服場景；Robin、Theo 的日報也能直接貼在對話裡看，不強求推播。

---

*卡關了？先把錯誤訊息丟給你的 Claude 試試，多數情況它當場就能幫你查清楚。*
