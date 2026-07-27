# Workflow：一鍵 Vercel 部署 + 網域設定

> 頁面做好、用戶確認後，部署到 Vercel 拿到可分享網址。

---

## 觸發條件

- 「幫我部署」「幫我上線」
- 「我要正式發布這個頁面」
- 「幫我接網域」

---

## 前置：確認 Vercel 帳號

第一次部署，先確認：

> 「你有 Vercel 帳號嗎？沒有的話免費註冊很快：
> 1. 打開 [vercel.com/signup](https://vercel.com/signup)
> 2. 用 GitHub / Email 註冊（免費方案就夠用）
> 3. 註冊完跟我說一聲，我們就能開始部署」

## 部署方式

### 方式 A：Vercel CLI（推薦，最快）

```bash
# 第一次使用，安裝 Vercel CLI
npm install -g vercel

# 登入（會開瀏覽器完成授權）
vercel login

# 在頁面資料夾內執行部署
vercel --prod
```

部署完成後，終端機會印出正式網址（例如 `https://your-project.vercel.app`），直接回傳給用戶。

### 方式 B：拖拉部署（免安裝任何工具）

1. 打開 [vercel.com/new](https://vercel.com/new)
2. 把整個頁面資料夾拖進瀏覽器上傳區
3. 點 Deploy，等待約 30 秒
4. 拿到網址

> 沒有 Node.js / npm 環境時，方式 B 最省事，適合完全不想碰終端機的用戶。

---

## 更新已部署的頁面

內容有修改時：

```bash
# 在同一個專案資料夾內，重新執行
vercel --prod
```

會覆蓋更新到同一個網址，不會產生新連結。

---

## 掛自訂網域

用戶已經有網域（例如在 GoDaddy、Namecheap、Gandi 買的）：

1. Vercel 專案後台 → Settings → Domains → 輸入網域
2. Vercel 會給一組 DNS 紀錄（通常是 A record 或 CNAME）
3. 到網域註冊商的 DNS 設定頁，貼上 Vercel 給的紀錄
4. 等待 DNS 生效（通常 10 分鐘 – 24 小時，多數很快）
5. 用 [dnschecker.org](https://dnschecker.org) 確認生效狀況

用戶還沒有網域：

> 「你可以先用 Vercel 給的免費網址（`xxx.vercel.app`）開始賣，之後想換成自己的網域，隨時可以去網域註冊商（Namecheap、GoDaddy 等）買一個，買好跟我說，我一步步帶你接上。」

---

## 部署後檢查清單

- [ ] 網址能正常打開，手機版排版正常
- [ ] 所有 CTA 按鈕連結正確（表單連結 / 金流連結 / 導購連結）
- [ ] SEO meta 標籤有正確顯示（可用 [metatags.io](https://metatags.io) 檢查社群分享預覽）
- [ ] 表單提交後有明確的成功訊息

---

## 收尾

記進 `~/.claude/skills/_base/task-log.md`，並更新 `~/.claude/skills/_base/tool-inventory.md` 的 Vercel 狀態為 ✅：

```
- 【日期】｜Kai｜[產品名] 落地頁已部署｜網址：[URL]
```

交棒給用戶或 Hugo：「頁面上線了，網址是 [URL]。要不要請 Mia 幫你排一篇社群貼文導流過來？」
