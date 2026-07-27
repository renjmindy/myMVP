# Theo · 競品監控哨兵

> AI 自動化團隊的市場情報員，每天盯競品/關鍵字動態，早上推日報給你。

---

## 直接使用

你可以直接呼叫 Theo：

```
/theo-watch 幫我盯 3 個競品的動態
/theo-watch 這週競品有什麼變化
/theo-watch 幫我設定每天早上 7 點推送
```

但通常建議透過 Hugo 呼叫：

```
/hello-hugo 幫我盯競品
```

Hugo 會把任務轉給 Theo，並負責跨角色協作（例如把重大競品動態列入策略分析）。

---

## 能力詳情

請看 `SKILL.md`。監控來源設定在 `workflows/source-setup.md`，日報產出流程在 `workflows/daily-watch-report.md`。監控清單存在 `references/watchlist.md`。
