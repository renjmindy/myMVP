# AI-Team · 你的六人 AI 自動化團隊

> 每個人對應一個具體的「每天在浪費你時間」的痛點。跟 Hugo 打聲招呼，他會問你想先解決哪一個，再把任務轉給對的人。

> 🆓 **只有 Claude 免費版（claude.ai 網頁版）？** 走 [`free-version/`](free-version/README.md)——7 個 zip，上傳就能用，不用碰終端機。下面的安裝方式是給 **Claude Code（付費版）** 用的。

> 📄 **快速連結**：[INSTALL.md](INSTALL.md)（詳細安裝步驟）・[PROFILE-SETUP.md](PROFILE-SETUP.md)（個人資料填寫指引）・[FAQ.md](FAQ.md)（常見問題）

---

## 團隊成員

| 成員 | 資料夾 | 痛點 | 解法一句話 |
|---|---|---|---|
| **Hugo** ☕ | `hello-hugo` | 團隊總管，不知道該找誰時先找他 | 接收任務、判斷該誰做、追蹤跨角色進度 |
| **Robin** 📥 | `robin-inbox` | 每天花 1 小時整理郵件 | 自動讀 Gmail、提煉重點、推送 Notion 日報 + LINE |
| **Kai** 🛠 | `kai-pages` | 寫個落地頁要找工程師等兩週 | 一句話生落地頁文案+配色+SEO，一鍵 Vercel 部署 |
| **Ray** 🎬 | `ray-video` | 拍影片要剪輯配音發布全自己來 | 主題→腳本→AI配音→字幕→短影音→上架 YT/IG |
| **Mia** 📱 | `mia-social` | 每次發社群帖子要想文案配圖選時段 | 一週 IG/Threads 文案+配圖提示詞+排程 |
| **Theo** 🔭 | `theo-watch` | 競品監控全靠手動、消息慢半拍 | 每天盯網站/Twitter/Reddit，提煉變化推日報 |
| **Ada** 🤖 | `ada-support` | 客戶問題重複回、FAQ做不完 | 建知識庫，對接 LINE Bot/Email 7×24 自動回覆 |

完整職責、可呼叫的工作流、擅長/不擅長，見 `skills/hello-hugo/references/team-roster.md`。

---

## 📚 課綱（逐步安裝＋驗收每位成員）

想照單元、一步步安裝並驗收每位成員的能力，走 **`course/`** 資料夾：

| 單元 | 內容 |
|---|---|
| [Unit 0](course/unit-0-setup.md) | 環境建置 + 個人資料建置 |
| [Unit 1](course/unit-1-hugo.md) | Hugo · 團隊總管 |
| [Unit 2](course/unit-2-robin.md) | Robin · 收件匣管家 |
| [Unit 3](course/unit-3-kai.md) | Kai · 落地頁工程師 |
| [Unit 4](course/unit-4-ray.md) | Ray · 短影音流水線 |
| [Unit 5](course/unit-5-mia.md) | Mia · 社群排程機器人 |
| [Unit 6](course/unit-6-theo.md) | Theo · 競品監控哨兵 |
| [Unit 7](course/unit-7-ada.md) | Ada · 客服知識庫機器人 |
| [Unit 8](course/unit-8-full-team.md) | 全隊到齊，跑一次跨角色任務 |
| [Unit 9](course/unit-9-automation.md) | 進階自動化：讓團隊自己定時跑（選用） |

不想照課綱走也沒關係，下面「安裝」「日常怎麼用」兩節就是最精簡的上手方式。

---

## 📄 範例（想先看每位成員實際產出長怎樣）

`examples/` 資料夾收錄每位成員的完整產出範例（多數為示範情境，Ray 那篇是真實產出）：

| 檔案 | 內容 |
|---|---|
| [hugo-task-dispatch-sample.md](examples/hugo-task-dispatch-sample.md) | Hugo 接到新品上線任務，拆解＋跨角色派工的完整對話 |
| [hugo-progress-overview.md](examples/hugo-progress-overview.md) | `/hello-hugo 進度總覽` 的完整輸出 |
| [robin-daily-digest.md](examples/robin-daily-digest.md) | Robin 的收件匣日報範例 |
| [kai-landing-page.md](examples/kai-landing-page.md) | Kai 的落地頁完整架構範例 |
| [ray-video-script.md](examples/ray-video-script.md) | Ray 的真實產出案例——照片剪成短影音全流程 |
| [mia-weekly-content.md](examples/mia-weekly-content.md) | Mia 的一週排程草案＋逐篇產出範例 |
| [theo-watch-report.md](examples/theo-watch-report.md) | Theo 的每日競品監控日報範例 |
| [ada-knowledge-base.md](examples/ada-knowledge-base.md) | Ada 的知識庫建立＋自動回覆範例 |

---

## 🎁 資源包

`resources/` 資料夾放跨角色的實戰資源：

| 檔案 | 內容 |
|---|---|
| [ai-workflow-pack.md](resources/ai-workflow-pack.md) | AI 工作流設定包總覽——`_base/` 共用大腦、各角色設定工作流、自動化邊界說明 |
| [30-prompts.md](resources/30-prompts.md) | 30 個複製貼上就能用的跨角色組合技 Prompt |

---

## 安裝

1. 把 `skills/` 底下的每個資料夾（`_base`、`hello-hugo`、`robin-inbox`、`kai-pages`、`ray-video`、`mia-social`、`theo-watch`、`ada-support`）複製到 `~/.claude/skills/`
2. 在 Claude Desktop / Claude Code 開一個新對話（建議建一個專屬 Project，例如命名「AI Team」），輸入：

```
/hello-hugo 你好
```

3. Hugo 會自我介紹、問你的稱呼、問你想先解決哪個痛點，帶你把 `_base/business-profile.md` 填起來

> `_base/` 資料夾放的是全隊共用的個人化資料（業務基本資料、工具串接狀態、戰情記錄、用戶稱呼），只需要填一次，每位成員接任務前都會自動讀取。

---

## 日常怎麼用

**不確定該找誰 → 找 Hugo：**
```
/hello-hugo 幫我整理信箱
/hello-hugo 進度總覽
```

**確定要找誰 → 直接呼叫：**
```
/robin-inbox 幫我整理今天的信箱
/kai-pages 我要賣線上課程，幫我做一個落地頁
/ray-video 幫我把這個主題做成短影音
/mia-social 排這週的 IG 貼文
/theo-watch 幫我盯 3 個競品的動態
/ada-support 把這份產品文件建成客服知識庫
```

Hugo 負責派工與跨角色協作；直接呼叫某位成員時，他一樣會先讀 `_base/` 資料再開工，只是不經過 Hugo 派發。

---

## ⚡ 指令總覽小抄

> 不用背——直接用白話跟 Hugo 說也通。這張是給你快速參考。

### 💬 直接用白話交辦（Hugo 自動派工）

| 你說 | 誰接手 |
|------|--------|
| 「整理信箱」「今天的信有什麼重點」 | Robin |
| 「做落地頁」「我要賣 OO」 | Kai |
| 「幫我把這個主題做成短影音」「腳本」 | Ray |
| 「排這週貼文」「IG 發什麼」 | Mia |
| 「盯競品」「這個對手有什麼動靜」 | Theo |
| 「建客服知識庫」「幫我回這則留言」 | Ada |
| 「進度總覽」「這週狀況」「更新團隊」 | Hugo |

### 🛠️ 直接呼叫（跳過 Hugo）

| 指令 | 對應成員 |
|------|--------|
| `/hello-hugo` | Hugo |
| `/robin-inbox` | Robin |
| `/kai-pages` | Kai |
| `/ray-video` | Ray |
| `/mia-social` | Mia |
| `/theo-watch` | Theo |
| `/ada-support` | Ada |

---

## 🔄 一句話更新，永遠用最新版

如果你的團隊技能是從共用資料夾或 repo 複製安裝的（而不是手動維護），跟 Hugo 說一句話：

```
/hello-hugo 更新團隊
```

Hugo 會重新同步 `skills/*` 到最新版本，**你的 `_base/` 個人資料不會被動到**（品牌語氣、工具串接狀態、稱呼設定都原封不動保留）。

> 💡 更新後，開一個新對話就會用到最新版。
> 如果是本機手動維護的版本（沒有共用來源），Hugo 會誠實告訴你「這份沒有自動更新來源」——想調整某位成員的能力，直接告訴他要改哪裡即可。

---

## 資料夾結構

```
AI-Team/
├── README.md                        ← 你在這裡
├── INSTALL.md                       ← 詳細安裝步驟
├── FAQ.md                            ← 常見問題（卡關自救）
├── PROFILE-SETUP.md                  ← 個人資料填寫指引
├── ADVANCED-google-calendar.md       ← 進階：信箱提醒同步 Google 日曆（Robin）
├── ADVANCED-line-messaging-api.md    ← 進階：LINE 整合（Robin／Theo／Ada 共用）
│
├── skills/                    ← 整包丟進 ~/.claude/skills/
│   ├── _base/                  # 全隊共用個人化資料
│   ├── hello-hugo/              # Hugo · 團隊總管
│   ├── robin-inbox/              # Robin · 收件匣管家
│   ├── kai-pages/                # Kai · 落地頁工程師
│   ├── ray-video/                 # Ray · 短影音流水線
│   ├── mia-social/               # Mia · 社群排程機器人
│   ├── theo-watch/                # Theo · 競品監控哨兵
│   └── ada-support/               # Ada · 客服知識庫機器人
│
├── course/                    ← 教學單元（Unit 0–9）
├── examples/                  ← 每位成員的真實產出範例
├── resources/                 ← AI 工作流設定包 + 30 個實戰 Prompt 食譜
└── free-version/              ← Claude 免費版專用（7 個 zip，上傳即用）
```

每位成員資料夾裡都有：
- `SKILL.md`：角色設定、能力、標準流程（安裝到 `~/.claude/skills/<name>/SKILL.md`）
- `README.md`：快速上手，怎麼直接呼叫這位成員
- `workflows/`：各項能力的詳細執行步驟
- `references/`（部分成員）：該角色專用的持久化資料，例如 Theo 的監控清單、Ada 的知識庫

---

## 老實話：關於「全自動」

團隊每位成員都能立刻開始工作（用戶手動提供資料、開口請求），但要做到「不用開口，自己每天固定時間跑」，需要：

1. 對應的外部工具都已串接（Gmail、Notion、Vercel、LINE、Buffer 等，狀態記在 `_base/tool-inventory.md`）
2. 有排程工具（本機 Cron，或雲端 Vercel Cron）在固定時間觸發

沒有排程工具的階段，團隊一樣能用，只是「你開口，我立刻做」，不會自己主動跳出來——每位成員的 SKILL.md 裡都會誠實講清楚這件事，不會打包票說裝完就全自動。
