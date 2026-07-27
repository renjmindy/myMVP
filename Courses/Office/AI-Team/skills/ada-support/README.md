# Ada · 客服知識庫機器人

> AI 自動化團隊的客服手，把產品文件建成知識庫，對接 LINE Bot / Email 7×24 自動回覆。

---

## 直接使用

你可以直接呼叫 Ada：

```
/ada-support 把這份產品文件建成客服知識庫
/ada-support 幫我整理常見問題
/ada-support 幫我接 LINE Bot 自動回覆
```

但通常建議透過 Hugo 呼叫：

```
/hello-hugo 幫我做客服知識庫
```

Hugo 會把任務轉給 Ada，並負責跨角色協作（例如知識庫回不了的問題轉給 Robin 追蹤）。

---

## 能力詳情

請看 `SKILL.md`。知識庫建立流程在 `workflows/knowledge-base-build.md`，通道串接設定在 `workflows/channel-setup.md`。知識庫本體存在 `references/faq.md`。
