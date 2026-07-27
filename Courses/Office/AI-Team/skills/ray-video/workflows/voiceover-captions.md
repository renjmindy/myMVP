# Workflow：AI 配音 + 字幕 + 剪輯 + 上架

> 腳本確定（或素材到手）之後，Ray 接手技術處理到上架。
> 所有 ffmpeg 指令以 **macOS 實測為主**；Windows 學員的字幕燒錄流程未實測，建議改用 CapCut／剪映自動字幕。

---

## 觸發條件

- 腳本已確認，用戶說「開始做」「幫我配音」
- 用戶丟來拍好的素材說「幫我剪」「幫我上字幕」

---

## 前置：取得 ffmpeg

```bash
pip3 install imageio-ffmpeg -q
FF=$(python3 -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())")
```

---

## Step 1：AI 配音（純口播/知識型內容，或腳本已定）

> 「配音接了嗎？沒接的話幫你設定一下 TTS 服務（例如 ElevenLabs、Azure TTS），或者你想自己錄音也可以，把音檔給我一樣能接著做。」

已接 TTS → 依腳本逐句生成配音檔，合併成完整口白音軌。
沒接 → 請用戶自行錄音或用現成 App 配音，把音檔給我接手後續。

## Step 2：畫面素材處理

- **有實拍/生成素材** → 依腳本分鏡順序剪接
- **純口播** → 用文字卡（大標題呈現重點句）+ 簡單背景畫面/圖片，搭配配音

### 轉直式 9:16（Reels / Shorts）

```bash
# 裁切填滿
"$FF" -y -i input.mp4 -vf \
  "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920" \
  -c:a copy output-9x16.mp4
```

```bash
# 背景模糊填滿（不切畫面）
"$FF" -y -i input.mp4 -vf \
  "split[a][b];[a]scale=1080:1920,boxblur=20[bg];[b]scale=1080:-1[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2" \
  -c:a copy output-9x16-blur.mp4
```

## Step 3：自動聽打字幕

```bash
pip3 install faster-whisper -q
```

```python
from faster_whisper import WhisperModel
import subprocess

FF = "<ffmpeg 路徑>"
subprocess.run([FF, "-y", "-i", "input.mp4", "-vn", "-ar", "16000", "-ac", "1", "audio.wav"])

model = WhisperModel("small", device="cpu", compute_type="int8")
segments, _ = model.transcribe("audio.wav", language="zh", beam_size=5)

for seg in segments:
    print(f"[{seg.start:.1f}s → {seg.end:.1f}s] {seg.text.strip()}")  # 給人校對
```

> 拿到逐句時間+文字後，**先讓用戶校對錯字**，中文辨識偶有錯字，影片素材出錯字很傷專業感。

## Step 4：燒字幕（字幕規範，強制遵守）

**位置**：垂直 55–70%（安全區），避開頂部帳號名/追蹤鈕、底部平台 UI
**大小**：單行 72px / 兩行 64px / 三行 58px，一行最多 12 個中文字寬，超過自動斷行
**字體**：思源黑體 Noto Sans TC Bold/Black（免費商用）
**樣式**：白字 + 黑色描邊（8–12px），重點詞可換色，逐句出現

```bash
FONT="$HOME/Library/Fonts/NotoSansTC-Bold.otf"  # 沒有則 fallback 系統字體

"$FF" -y -i input.mp4 -vf \
  "drawtext=text='一支手機也能拍出質感':fontfile=$FONT:fontsize=80:fontcolor=white:borderw=10:bordercolor=black:x=(w-text_w)/2:y=1150" \
  -c:a copy output-subtitled.mp4
```

> 多句字幕建議寫一支自動化腳本統一處理斷行、字級、置中，避免手動計算出血或漏掉影像軌（`-map` 一定要含 `0:v`）。

## Step 5：加背景音樂 / 剪頭尾

```bash
# 加背景音樂
"$FF" -y -i video.mp4 -i music.mp3 -filter_complex \
  "[1:a]volume=0.3[bg];[0:a][bg]amix=inputs=2:duration=first" \
  -c:v copy output-bgm.mp4

# 剪頭尾
"$FF" -y -i input.mp4 -ss 00:00:03 -to 00:00:18 -c copy clip.mp4
```

## Step 6：批次處理（多支影片套同一套設定）

```bash
for f in *.mp4; do
  "$FF" -y -i "$f" \
    -vf "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920" \
    -c:a copy "reels_$f"
done
```

## Step 7：驗證

```bash
"$FF" -y -ss 7.0 -i output-final.mp4 -frames:v 1 check.png   # 抽格看字幕位置與錯字
```

## Step 8：上架

> 「準備上架了。要發哪裡？
> A. YouTube Shorts　B. IG Reels　C. 兩個都要」

- **API 已接** → 直接呼叫 YouTube Data API / Meta Graph API 上傳
- **沒接** → 給用戶上傳步驟（標題、描述、標籤建議一併準備好），用戶手動上傳

上傳文案建議：

```
標題：[吸睛標題，含關鍵字]
描述：[2-3 句說明 + CTA + 相關連結]
標籤：#[主題標籤] #[品牌標籤]
```

## Step 9：收尾

記進 `~/.claude/skills/_base/task-log.md`，交棒：

> 「短影音上架了，連結是 [URL]。要不要請 Mia 剪成社群貼文素材一起排程？」
