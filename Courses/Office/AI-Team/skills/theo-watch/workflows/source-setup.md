# Workflow：監控來源 + 推播管道設定

> 帶用戶把要盯的競品、關鍵字、推播管道設定起來。

---

## 觸發條件

- 「幫我盯 OO」（第一次提到某競品）
- 「幫我設定監控」
- 「幫我設定每天推送」

---

## Step 1：確認監控對象

> 「你想盯的競品或關鍵字是？（可以多個，一次告訴我）
> 每個競品，順便告訴我：
> 1. 網站/部落格網址（如果有）
> 2. 社群帳號（Twitter/X、粉專）
> 3. 你最在意的觀察重點（例如：定價、新功能、促銷活動）」

## Step 2：確認要盯哪些面向

> 「要盯的來源：
> A. 只盯官網／部落格
> B. 加上社群（Twitter/X）
> C. 全部都要（含 Reddit 討論）」

## Step 3：建立監控清單檔案

把資訊寫進 `~/.claude/skills/theo-watch/references/watchlist.md`：

```markdown
# 監控清單

## [競品名稱 A]
- 網站：[URL]
- 社群：[Twitter/X 帳號、粉專連結]
- 觀察重點：[定價 / 新功能 / 促銷 / 內容策略]
- 上次快照日期：[尚未建立]
- 上次快照重點：[尚未建立]

## [競品名稱 B]
...
```

## Step 4：確認推播管道

> 「日報要推到哪裡？
> A. LINE　B. Slack　C. 兩個都要　D. 先貼在對話裡就好」

### LINE 串接

1. 到 [LINE Notify](https://notify-bot.line.me/) 或 LINE Messaging API 後台建立 Channel
2. 取得 Access Token，存進憑證設定檔
3. 測試推播一則訊息確認收得到

> 若 Robin 或 Ada 已經接過 LINE，三人可以共用同一組串接，不用重複設定。

### Slack 串接

1. 到 [api.slack.com/apps](https://api.slack.com/apps) 建立一個 App
2. 啟用 Incoming Webhooks，取得 Webhook URL
3. 測試：

```bash
curl -X POST -H 'Content-type: application/json' \
  --data '{"text":"Theo 測試訊息"}' \
  {WEBHOOK_URL}
```

## Step 5：確認監控頻率

> 「多久幫你看一次？A. 每天　B. 每 2-3 天　C. 每週一次」

## Step 6：更新工具盤點

回 `~/.claude/skills/_base/tool-inventory.md`，把 Twitter/X 監控、Reddit 監控、LINE、Slack 對應狀態改成 ✅。

---

## 排程自動化（讓 Theo 每天自己跑）

**老實說在前面**：設定好監控清單和推播管道，不代表 Theo 會自己在指定時間醒過來跑。要做到真正無人值守：

| 方案 | 說明 |
|---|---|
| 本機 Cron | 電腦要開著，用 Cron/工作排程器在指定時間執行呼叫 Claude Code 的腳本 |
| 雲端方案（推薦） | 包成腳本部署到 Vercel，用 Vercel Cron 定時觸發，電腦關著也會跑 |

這屬於進階自動化課題，跟用戶說明是「一次設定、之後全自動」的投資，並詢問要不要現在開始設定。
