# Robin · 收件匣管家

> AI 自動化團隊的信箱手，負責每天整理 Gmail、推送 Notion + LINE 日報。

---

## 直接使用

你可以直接呼叫 Robin：

```
/robin-inbox 幫我整理今天的信箱
/robin-inbox 這週有哪些信我還沒回
/robin-inbox 幫我設定每天早上 8 點自動推送
```

但通常建議透過 Hugo 呼叫：

```
/hello-hugo 整理信箱
```

Hugo 會把任務轉給 Robin，並負責跨角色協作（例如把落地頁詢問信一起彙整進日報）。

---

## 能力詳情

請看 `SKILL.md`。串接設定步驟在 `workflows/notion-line-setup.md`，每日摘要邏輯在 `workflows/daily-digest.md`。
