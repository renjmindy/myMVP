# Unit 0｜環境建置 + 個人資料建置

> 這個單元完成後，你的 Claude 會知道你的稱呼、你的生意，而且整個六人團隊都已經就位。

---

## 你會得到什麼

- Claude Code（或 Claude Desktop）裡跑著一支完整的 AI 自動化團隊
- 一份讓所有夥伴都能讀懂你狀況的「共用大腦」（`_base/`）
- 知道接下來每個單元該找誰、怎麼開始

---

## Step 1：打開 Claude Code

跟團隊對話的地方是 **Claude Code**（Claude Desktop 裡的終端機視窗），不是 claude.ai 網頁聊天、也不是一般 Chat 分頁——只有 Claude Code 碰得到你電腦裡的檔案，才裝得了團隊。

> ⚠️ **本課會常常請你「完全關閉 Claude Code 再重開」**：只縮小視窗、關分頁都不算數，Claude 只有在重新啟動那一刻才會重新讀取技能設定。

---

## Step 2：一次裝好整個團隊

整個團隊——Hugo（總管）＋六位成員＋所有工作流——都在 `AI-Team/skills/` 底下。✏️ 在 Claude Code 貼：

```
請把 AI-Team/skills 底下的全部內容，複製到我的 Claude 技能資料夾（~/.claude/skills/，沒有就建立），
包含 _base 和所有子資料夾。
```

複製完成後，**完全關閉 Claude Code 再重新打開**。

> ✅ 這步把 **Hugo、Robin、Kai、Ray、Mia、Theo、Ada ＋ 所有工作流 ＋ `_base/` 個人資料範本** 一次裝齊，後面單元不用再安裝。

---

## Step 3：跟 Hugo 打第一次招呼

✏️ 輸入：

```
/hello-hugo 你好
```

Hugo 會自我介紹、介紹六位夥伴，並帶你回答第一個問題：「你現在最想先解決哪一個痛點？」

第一次見面，他也會問你希望被怎麼稱呼——回答後會存進 `_base/user-profile.md`，之後每位成員出場都會用這個稱呼叫你。

---

## Step 4：建立你的業務基本資料

Hugo（以及你選定的第一位夥伴）會一題一題帶你把 `_base/business-profile.md` 填起來，不用自己整份寫：

- 你是誰 / 做什麼的
- 目標客群
- 品牌語氣（給 Kai、Ray、Mia 這類會產文案的成員參考）
- 目前最想解決的痛點

> 💡 不想用問答的方式也可以：直接打開 `~/.claude/skills/_base/business-profile.md`，把 `[填寫]` 的地方換成你的真實資訊。

---

## Step 5：認識工具盤點表

打開（或請 Hugo 唸給你聽）`~/.claude/skills/_base/tool-inventory.md`——這張表記錄哪些外部工具（Gmail、Notion、Vercel、LINE…）已經接好、哪些還沒。

> 沒接的工具不代表做不到：每位成員遇到工具沒接時，會先給你一個半自動方案（見 `_base/fallback-principles.md`），同時邀你要不要現在接上。接工具的步驟都在對應成員的 `workflows/*-setup.md` 裡，不急著這個單元就做完。

---

## ✅ 驗收任務

完成以下三件事：

- [ ] `/hello-hugo 你好` 有正確自我介紹、並問了你的稱呼
- [ ] `_base/user-profile.md` 已經寫入你的稱呼
- [ ] `_base/business-profile.md` 至少填了「我是誰 / 做什麼的」跟「目前主要痛點」兩塊

---

## 小提示

> `_base/` 是整個團隊的共用大腦。填得越清楚，六位夥伴給你的東西就越貼近你的實際狀況。
>
> 接下來每個單元會帶你認識一位成員、逐一驗收他的能力。Unit 8 全隊到齊，才是整個團隊真正發揮效果的時候。
