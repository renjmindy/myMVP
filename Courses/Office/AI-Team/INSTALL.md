# 安裝指引

> 時間抓個底：**裝好整個團隊約 5 分鐘**（複製資料夾、重開 Claude Code）；**填個人資料另花約 10 分鐘**（用 `/hello-hugo 你好` 對話式最快）。想接自動化工具（Gmail、Notion、Vercel、LINE…）再各加一點，不急的話可以先裝好、先試玩，工具之後慢慢接。

---

## 前置需求

- **安裝要用電腦做**（Mac 或 Windows 都可以）
- **Claude Code** 已安裝（[官方下載](https://claude.com/claude-code)）——Claude Code 已原生支援 Windows，**不需要 WSL**
- 一個 Claude 帳號（建議 Claude Pro 以穩定使用全部功能）
- 這個 `AI-Team/` 資料夾已經在你的電腦裡（就是你現在看的這個）

> 🆓 **只有 Claude 免費版？** 不用管這份文件，走 [`free-version/README.md`](free-version/README.md)，下載 zip 上傳到 claude.ai 就好，不用碰終端機。

---

## 安裝步驟

### Step 1：把技能複製到 Claude 技能資料夾

打開 **Claude Code**（不是 claude.ai 網頁、也不是 Claude 桌面聊天分頁——這步一定要在 Claude Code 做）。

✏️ 貼上：

```
請把這個 AI-Team 資料夾裡 skills 底下的全部內容，複製到我的 Claude 技能資料夾
（`~/.claude/skills/`，沒有就建立），包含 _base 和所有子資料夾。複製完成後，
請逐一確認 hello-hugo、robin-inbox、kai-pages、ray-video、mia-social、theo-watch、
ada-support 和 _base 都複製成功了，列出來給我看；如果少了哪一個，幫我再複製一次。
```

Claude 會自動判斷你的系統、複製好，並當場幫你點名團隊有沒有到齊。

> ⚠️ **路徑對不上？** 如果 Claude 找不到 `AI-Team` 資料夾，直接告訴它完整路徑，例如「我的 AI-Team 在 `~/Desktop/AI-Team`，skills 底下全部複製到 `.claude/skills/`」。

完成後，**完全關閉 Claude Code 再重新打開**（不是按紅色叉叉關視窗）：
- **Mac**：左上角選單「Claude」→「結束 Claude」（⌘Q），再重開
- **Windows**：右下角工具列 Claude 圖示右鍵 →「結束」，再重開

> ⚠️ **為什麼要「完全結束」？** Claude 只有在重新啟動那一刻才會重新讀取技能設定——很多「裝好卻沒反應」都是卡在這一步沒做。

你的技能資料夾（Mac：`~/.claude/skills/`；Windows：`C:\Users\你\.claude\skills\`）會有這些：

```
~/.claude/skills/
├── _base/            ← 全隊共用個人化資料（你要填）
│
├── 七位成員
│   ├── hello-hugo/    ← Hugo 團隊總管（輸入 /hello-hugo 啟動）
│   ├── robin-inbox/   ← Robin 收件匣管家
│   ├── kai-pages/     ← Kai 落地頁工程師
│   ├── ray-video/     ← Ray 短影音流水線
│   ├── mia-social/    ← Mia 社群排程機器人
│   ├── theo-watch/    ← Theo 競品監控哨兵
│   └── ada-support/   ← Ada 客服知識庫機器人
```

### Step 2：填好你的個人資料

✏️ 輸入：

```
/hello-hugo 你好
```

Hugo 會自我介紹、問你的稱呼、問你目前最想解決的痛點，帶你一題一題把 `_base/business-profile.md` 填起來。

> 想自己手動填？看 [PROFILE-SETUP.md](PROFILE-SETUP.md) 的步驟引導，跟對話式**擇一即可**。

---

## 驗證安裝（兩關都過才算真的裝好）

### 第 1 關 · 功能驗證：Hugo 會不會回你

✏️ 輸入：

```
/hello-hugo 你好
```

Hugo 跟你打招呼、介紹團隊 → 功能正常。

### 第 2 關 · 完整性驗證：七位成員到齊了嗎

> ⚠️ **這關別跳過**：有時複製只成功一半——Hugo 回得了話，但其他成員根本沒進來。

✏️ 直接跟 Claude 說：

```
幫我看 ~/.claude/skills/ 裡面有哪些資料夾，確認 hello-hugo、robin-inbox、kai-pages、
ray-video、mia-social、theo-watch、ada-support 和 _base 都在
```

八個都在就完全 OK。

### Plan B：少了東西怎麼救

- **找不到 `/hello-hugo` 指令** → ① 確認有複製到 `~/.claude/skills/hello-hugo/`；② **完全關閉 Claude Code 再重開一次**。
- **少了某一位成員** → 跟 Claude 說「幫我把 AI-Team/skills 裡的 `robin-inbox`（換成缺的那個）再複製一次到 `.claude/skills/`」。
- **資料夾整個是空的** → 確認你複製的是 `AI-Team/skills/` 底下的內容，不是外層的 `AI-Team/` 本身。

---

## Claude 付費版功能（選用）

裝好核心團隊後，可以額外接這幾個工具啟用進階功能。**這些都是「選用」，需要你自己去接外部服務：**

| 工具 | 適用成員 | 功能 | 怎麼接 |
|-----|-----------|------|------|
| Gmail + Notion | Robin | 自動讀信、日報存進可搜尋資料庫 | 見 `skills/robin-inbox/workflows/notion-line-setup.md` |
| LINE Messaging API | Robin／Theo／Ada（可共用同一組）| 推播日報／監控報告／客服自動回覆 | 見 `ADVANCED-line-messaging-api.md` |
| Vercel | Kai | 一鍵部署落地頁 | 見 `skills/kai-pages/workflows/vercel-deploy.md` |
| Google Calendar | Robin | 信箱時效性事項自動進日曆 | 見 `ADVANCED-google-calendar.md` |
| Buffer / IG／Threads API | Mia | 排程自動發文 | 見 `skills/mia-social/workflows/scheduling-setup.md` |
| TTS 服務（如 ElevenLabs） | Ray | AI 配音 | 見 `skills/ray-video/workflows/voiceover-captions.md` |

> ⚠️ 老實說：接哪個都不是「裝完團隊就有」，要自己花時間接一次。沒接也完全不影響核心功能——把資料貼給對應成員，他們一樣幫你做，只是少了「自動」那一步。

---

## 🗑️ 不想要了？一鍵刪除碼

複製下面這串貼進終端機執行，會把整個團隊乾淨移除（只刪這個團隊的資料夾，不會動到你 Claude 的其他東西）。

Mac / Linux：

```bash
rm -rf ~/.claude/skills/{_base,hello-hugo,robin-inbox,kai-pages,ray-video,mia-social,theo-watch,ada-support}
```

Windows（PowerShell）：

```powershell
Remove-Item -Recurse -Force "$env:USERPROFILE\.claude\skills\_base","$env:USERPROFILE\.claude\skills\hello-hugo","$env:USERPROFILE\.claude\skills\robin-inbox","$env:USERPROFILE\.claude\skills\kai-pages","$env:USERPROFILE\.claude\skills\ray-video","$env:USERPROFILE\.claude\skills\mia-social","$env:USERPROFILE\.claude\skills\theo-watch","$env:USERPROFILE\.claude\skills\ada-support"
```

> 刪完重開 Claude Code，團隊就不在了。想再裝回來，回到本檔 Step 1 重跑一次即可（想保留個人資料，先把 `_base/` 從上面那串移掉再執行）。
