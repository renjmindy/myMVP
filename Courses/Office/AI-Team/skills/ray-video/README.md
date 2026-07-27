# Ray · 短影音流水線

> AI 自動化團隊的影片手，主題→腳本→AI配音→字幕→剪輯→上架 YT/IG 一條龍。

---

## 直接使用

你可以直接呼叫 Ray：

```
/ray-video 幫我把「三個提升生產力的習慣」做成短影音
/ray-video 這支影片幫我上字幕
/ray-video 幫我把橫式影片轉成 Reels 尺寸
```

但通常建議透過 Hugo 呼叫：

```
/hello-hugo 幫我做一支短影音
```

Hugo 會把任務轉給 Ray，並負責跨角色協作（例如影片做好後請 Mia 排程發布）。

---

## 能力詳情

請看 `SKILL.md`。腳本產出流程在 `workflows/script-to-video.md`，配音字幕剪輯上架在 `workflows/voiceover-captions.md`。
