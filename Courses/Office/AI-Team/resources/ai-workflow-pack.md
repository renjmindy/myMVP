# 🎁 AI 工作流設定包

> 這包讓你不只「擁有」六人 AI 自動化團隊，而是**真的把它接起來、跑起來、不出包**。
> 一句話：把六位成員從「會聊天」變成「能幫你實際整理信箱、上線頁面、剪片、發文、盯競品、回客服」的完整工作流。

---

## 這包裡有什麼

### 1. 🧭 共用大腦 `_base/`
每位成員接任務前都會先讀的個人化資料：
- `business-profile.md` —— 你是誰、做什麼、目標客群、品牌語氣、目前主要痛點
- `user-profile.md` —— 你希望被怎麼稱呼
- `tool-inventory.md` —— 哪些工具（Gmail、Notion、Vercel、LINE、Buffer…）已接好、哪些還沒
- `task-log.md` —— 團隊做過什麼的累積記錄，跨對話也記得進度
- `fallback-principles.md` —— 工具沒接時的半自動應對原則，全隊共同遵守

### 2. 🚦 誠實的自動化邊界
每位成員的 SKILL.md 都會老實告訴你：哪些事「現在馬上能做」、哪些事需要「先接工具」、哪些事需要「排程觸發才叫真自動」——不會打包票說裝完就全自動。想真的接上排程，見 [`course/unit-9-automation.md`](../course/unit-9-automation.md)。

### 3. 📚 各角色專用知識庫
- Theo 的 `references/watchlist.md` —— 競品監控清單 + 上次快照
- Ada 的 `references/faq.md` —— 客服知識庫本體
- Hugo 的 `references/team-roster.md` —— 團隊花名冊，誰擅長什麼、可呼叫哪些工作流、跨角色協作組合

### 4. 🛠️ 每位成員的設定工作流
遇到「想要自動化」的需求，對應成員都有專屬的 `workflows/*-setup.md` 帶你一步步接：
- Robin → Gmail / Notion / LINE
- Kai → Vercel 部署 / 網域
- Ray → TTS 配音 / 剪輯工具
- Mia → Buffer / IG / Threads API
- Theo → 監控來源 / 推播管道
- Ada → LINE Bot / Email 客服信箱

### 5. 📝 30 個實戰 Prompt 食譜
[👉 30 個複製貼上就能用的情境食譜](30-prompts.md)——新品上線衝刺、一批照片變短影音、競品逆向工程…常常一句話就讓 Hugo 同時調度好幾位夥伴，把跨角色打法直接打包給你。

---

## 怎麼啟用

裝好團隊後，直接跟 Hugo 說：

```
/hello-hugo 幫我設定
```

他會依你目前最想解決的痛點，帶你把該接的工具一個一個接起來，每步都會驗證。

> 💡 沒有時間一次接完全部工具也沒關係——`_base/tool-inventory.md` 會一直記錄狀態，之後想到再回來接，不會影響團隊現在就能用的部分。

---

*AI 工作流設定包 ｜ 你的六人 AI 自動化團隊*
