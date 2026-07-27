# Workflow：Gmail / Notion / LINE 串接設定

> 帶用戶一步步把三個工具接起來，每步驗證，接好之後 Robin 才能真正「自動」讀信、推送。

---

## 觸發條件

- 「幫我設定」（在 Robin 情境下）
- 「幫我接 Gmail / Notion」
- 「想要每天自動推送」

---

## 設定前先講清楚

> 「要做到『不用開口，日報自動出現』，需要接好 3 個東西：
> 1. **Gmail**（讀信）
> 2. **Notion**（存日報，可回溯搜尋）
> 3. **LINE**（選配，即時推播提醒）
>
> 接好之後，還需要排程工具讓我在早上 8 點自動跑一次（見本文件最後一節）。
> 我們先從哪個開始？A. Gmail　B. Notion　C. LINE」

---

## A. Gmail 串接

1. 確認是否已有 Gmail MCP / 授權工具可用
2. 沒有 → 帶用戶完成 OAuth 授權流程（依實際使用的 MCP 或串接方案指示操作）
3. 授權完成後，測試：「讀我最新 3 封信」驗證能不能正常拉信

> 沒接好前，Robin 一樣能工作——用戶轉寄或貼信件內容即可，只是不能自動化。

---

## B. Notion 串接

1. 到 [notion.so/my-integrations](https://www.notion.so/my-integrations) 建立一個 Integration，取得 **API Token**
2. 在 Notion 裡建立一個「收件匣日報」資料庫，欄位建議：

| 欄位 | 類型 |
|---|---|
| 日期 | Date |
| 待回件數 | Number |
| 留意件數 | Number |
| 今日摘要 | Text |
| 優先事項 | Text |

3. 把該資料庫「分享」給剛才建立的 Integration（資料庫右上角 ••• → Connections → 選擇該 Integration）
4. 複製資料庫 URL 中的 **Database ID**（32 碼字串）
5. 把 **API Token** 和 **Database ID** 存進設定檔（例如 `~/.claude/skills/_base/tool-inventory.md` 備註欄，或用戶慣用的憑證檔）

> 🔒 API Token 等同密碼，不要貼進會同步/分享的雲端資料夾，也不要截圖外傳。

6. 測試寫入一筆：「幫我在 Notion 資料庫寫一筆測試日報」驗證串接成功

---

## C. LINE 串接（選配）

1. 到 [LINE Notify](https://notify-bot.line.me/) 或 LINE Messaging API 後台建立 Channel
2. 取得 **Access Token**
3. 存進憑證設定檔
4. 測試：發一則「Robin 測試訊息」確認收得到

> LINE Notify／Messaging API 兩者能力不同：Notify 較簡單但功能有限（僅推播），Messaging API 較完整但設定較複雜。依用戶需求選一個即可，不用兩個都接。

---

## 接好之後：更新工具盤點

三個工具接好一個，就回 `~/.claude/skills/_base/tool-inventory.md` 把對應狀態改成 ✅，並補上接的日期。

---

## 排程自動化（讓 Robin 每天 8 點自己跑）

**老實說在前面**：接好上面三個工具，只代表 Robin「有能力」自動讀信推送，不代表它「會自己在 8 點醒過來跑」。要做到真正的無人值守，還需要：

| 方案 | 說明 | 適用情境 |
|---|---|---|
| **本機 Cron / 工作排程器** | 電腦要開著，用 Mac/Linux 的 Cron 或 Windows 工作排程器，在 8:00 執行一支呼叫 Claude Code 的腳本 | 電腦習慣整天開著 |
| **雲端方案（推薦）** | 把整理邏輯包成腳本，部署到 Vercel，用 Vercel Cron 定時觸發，電腦關著也會跑 | 想要真正的全自動 |

> 這屬於進階自動化課題（腳本撰寫 + Cron/Hooks + 雲端部署）。跟用戶說明這是「一次設定、之後全自動」的投資，值得但需要一點時間，並詢問要不要現在開始設定。若用戶要架站/部署，這步可以請 Kai 協助建立部署環境。
