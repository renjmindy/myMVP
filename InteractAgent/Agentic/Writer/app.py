import os
import base64
import gradio as gr
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from dotenv import load_dotenv

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
_MIME = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "gif": "gif", "webp": "webp", "bmp": "bmp"}


def _resolve_file(file):
    """Return (file_path, filename) from whatever Gradio passes."""
    if isinstance(file, dict):
        file_path = file.get("path") or file.get("name", "")
        filename = file.get("orig_name") or os.path.basename(file_path)
    elif isinstance(file, str):
        file_path, filename = file, os.path.basename(file)
    else:
        file_path = getattr(file, "name", str(file))
        filename = os.path.basename(file_path)
    return file_path, filename


def analyze_image(file_path: str, filename: str) -> str:
    """Send an image to GPT-4o-mini vision and return a detailed description."""
    if llm is None:
        return f"[🖼 {filename}：OPENAI_API_KEY 未設定，無法分析圖片]"
    ext = os.path.splitext(filename)[1].lower().lstrip(".")
    mime = _MIME.get(ext, "jpeg")
    with open(file_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    vision_msg = HumanMessage(content=[
        {"type": "text", "text": (
            "請詳細描述這張圖片的所有內容，包括：文字、圖表、表格、流程圖、關鍵數據、版面結構等。"
            "用繁體中文回答，盡量完整，讓閱讀者無需看圖也能理解圖片傳達的資訊。"
        )},
        {"type": "image_url", "image_url": {"url": f"data:image/{mime};base64,{b64}"}},
    ])
    response = llm.invoke([vision_msg])
    return f"[🖼 {filename} — 圖片分析]\n\n{response.content}"


def extract_text(file) -> str:
    """Extract text (or vision description) from an uploaded file."""
    if file is None:
        return ""
    file_path, filename = _resolve_file(file)
    ext = os.path.splitext(filename)[1].lower()
    try:
        if ext in _IMAGE_EXTS:
            return analyze_image(file_path, filename)
        if ext == ".pdf":
            import pypdf
            reader = pypdf.PdfReader(file_path)
            content = "\n".join(p.extract_text() for p in reader.pages if p.extract_text())
        elif ext == ".docx":
            import docx
            doc = docx.Document(file_path)
            content = "\n".join(p.text for p in doc.paragraphs if p.text)
        else:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        return f"[📎 {filename}]\n\n{content}"
    except Exception as e:
        return f"[無法讀取 {filename}：{e}]"


load_dotenv()

_api_key = os.environ.get("OPENAI_API_KEY")
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7) if _api_key else None

_KEY_MISSING_MSG = (
    "⚠️ **`OPENAI_API_KEY` 尚未設定。**\n\n"
    "請至 HuggingFace Space → **Settings → Variables and secrets** 新增此 Secret，"
    "儲存後 Space 會自動重新啟動。"
)

QUESTIONS = [
    {
        "id": "Q1",
        "title": "告知背景、動機與目的",
        "prompt": "請描述您的背景、動機與目的",
        "hint": (
            "例如：\n"
            "- ✓ **背景**：我是製造業業務，負責客戶訂單、報價與交期追蹤\n"
            "- ✓ **動機**：資料分散，新人接手慢，主管也難掌握進度與風險\n"
            "- ✓ **目的**：請協助判斷\n"
            "  - 哪些流程適合用 AI 協助\n"
            "  - 如何降低對個人經驗的依賴\n"
            "  - 如何整理成追蹤表或週報"
        ),
    },
    {
        "id": "Q2",
        "title": "設定 LLM 與自己的角色",
        "prompt": "請設定您自己的角色，以及您希望 AI 扮演的角色",
        "hint": (
            "例如：\n"
            "- ✓ **自己**：我是企業專案負責人，這些資料分散、格式不一，我現在要整理給總經理看\n"
            "- ✓ **LLM**：你是專業的\n"
            "  - 資深主管、流程顧問、資料分析師，也是簡報大師\n"
            "  - 任務：請你協助我將附件整理成 20 頁的簡報"
        ),
    },
    {
        "id": "Q3",
        "title": "給予附件、閱讀後回答",
        "prompt": "請提供素材內容（文字、資料摘要等），並說明您的預期效果",
        "hint": (
            "「先讓 AI 讀懂，再讓它動手。」\n\n"
            "- Step1：提供素材（附件或文字、圖片內容）\n"
            "- Step2：明確告訴 AI 任務以及您的預期效果\n"
            "- Step3：AI 從內容中「理解上下文」，精準生成\n\n"
            "應用：\n"
            "- ✓ 讓 AI 讀資料 → 減少理解負擔\n"
            "- ✓ 讓 AI 代為萃取重點 → 找出潛在線索\n"
            "- ✓ 讓 AI 重組內容 → 形成可用的分析與敘事\n"
            "- ✓ 讓 AI 根據上下文生成 → 更精準、更有深度"
        ),
    },
    {
        "id": "Q4",
        "title": "先求廣度的完整性、再求深度的專業性",
        "prompt": "您希望 AI 從哪些面向深入分析？",
        "hint": (
            "例如：\n"
            "- 以執行者角度詳細說明內容（步驟、規劃、分析…）\n"
            "- 有什麼挑戰與風險？\n"
            "- 有什麼價值？\n"
            "- 有什麼隱性成本？\n"
            "- 有什麼策略？"
        ),
    },
    {
        "id": "Q5",
        "title": "給予範本，依套路回答",
        "prompt": "請提供您希望 AI 參考的範本或輸出格式（Few-shot 示例）",
        "hint": (
            "例如：\n"
            "- 提供一個您滿意的過去輸出範例\n"
            "- 指定結構：如「每個分析包含：現況 → 問題 → 建議 → 預期效益」\n"
            "- Few-shot 提示：給出 1~3 個輸入/輸出對照範例，讓 AI 學習套路"
        ),
    },
    {
        "id": "Q6",
        "title": "給予限制，約束範圍及輸出格式",
        "prompt": "請說明您的限制條件與輸出格式要求",
        "hint": (
            "**範疇限制**（例如）：\n"
            "- 僅限特定產業/情境，不討論法規以外的推測\n"
            "- 只針對目前公司規模，不代替使用者做最終決定\n"
            "- 不站在推銷立場，以一年期來評估，不增加人力編制\n\n"
            "**格式限制**（例如）：\n"
            "- 條列、表格、步驟；限制字數\n"
            "- 網路社群行銷風格、emoji；給投資人/主管/潛在客戶\n"
            "- 口語式翻譯、正式商務信件翻譯"
        ),
    },
    {
        "id": "Q7",
        "title": "分階段提問、再整合",
        "prompt": "您希望將任務拆解為哪幾個階段？請說明各階段的目標與順序",
        "hint": (
            "例如：\n"
            "- 第一階段：先整理現況與問題清單\n"
            "- 第二階段：針對每個問題提出解決方案\n"
            "- 第三階段：彙整成完整的行動計畫\n"
            "→ 最後再整合三個階段的輸出，產出最終報告"
        ),
    },
    {
        "id": "Q8",
        "title": "探究原因及過程",
        "prompt": "您希望 AI 針對哪些環節追問原因、探索背後邏輯或過程？",
        "hint": (
            "例如：\n"
            "- 為什麼這個做法會比其他方案更有效？\n"
            "- 這個結論是怎麼推導出來的？\n"
            "- 有哪些隱含假設？\n"
            "- 如果條件改變，結論會如何調整？\n"
            "- 請逐步說明推理過程（Chain of Thought）"
        ),
    },
]

META_PROMPT = """你是一個專業的提示詞工程專家。根據使用者提供的 8 個面向資訊，生成一個結構完整、高質量的 System Prompt。

生成的 Prompt 必須包含以下結構：
1. # Role: 角色定義
2. # Context: 背景資訊
3. # Goals: 任務目標
4. # Constraints: 約束條件
5. # Format: 輸出格式

請確保生成的 Prompt 完整涵蓋使用者提供的所有資訊，並以繁體中文輸出。
"""


def sanitize(text: str) -> str:
    return text.encode("utf-8", errors="ignore").decode("utf-8")


def format_question(q: dict, index: int) -> str:
    progress = f"*（進度：{index}/{len(QUESTIONS)} 已完成）*\n\n" if index > 0 else ""
    return (
        f"{progress}"
        f"### {q['id']}｜{q['title']}\n\n"
        f"{q['hint']}\n\n"
        f"✏️ **{q['prompt']}**（可輸入 `-` 略過）"
    )


def build_user_message(answers: dict) -> str:
    lines = ["以下是我提供的 8 個面向資訊，請根據這些內容生成高質量的 System Prompt：\n"]
    for q in QUESTIONS:
        qid = q["id"]
        lines.append(f"【{qid}｜{q['title']}】")
        lines.append(answers.get(qid, "（略過）"))
        lines.append("")
    return "\n".join(lines)


WELCOME_MSG = (
    "## ✨ 歡迎使用 提示詞大師 (LangGraph)\n\n"
    "請依序回答以下 **8 個問題**，協助 AI 為您生成精準的 System Prompt。  \n"
    "輸入 `-` 可略過任何問題。\n\n"
    "---\n\n"
    + format_question(QUESTIONS[0], 0)
)


def make_state():
    """Return a fresh session state dict with chat history pre-loaded."""
    return {
        "phase": "questions",
        "q_index": 0,
        "answers": {},
        "lc_history": [],
        # chat_history is the single source of truth for the Chatbot component
        "chat_history": [{"role": "assistant", "content": WELCOME_MSG}],
    }


def respond(user_message, state):
    """Generator — chatbot is OUTPUT-ONLY; all history lives in state["chat_history"]."""
    if state is None:
        state = make_state()

    if llm is None:
        state["chat_history"] = state["chat_history"] + [
            {"role": "assistant", "content": _KEY_MISSING_MSG}
        ]
        yield "", state["chat_history"], state
        return

    user_message = sanitize((user_message or "").strip())
    if not user_message:
        yield "", state["chat_history"], state
        return

    state["chat_history"] = state["chat_history"] + [
        {"role": "user", "content": user_message}
    ]

    # ── Question phase ──────────────────────────────────────────────────────
    if state["phase"] == "questions":
        q_index = state["q_index"]
        qid = QUESTIONS[q_index]["id"]
        state["answers"][qid] = user_message if user_message != "-" else "（略過）"
        state["q_index"] += 1

        if state["q_index"] < len(QUESTIONS):
            next_q = QUESTIONS[state["q_index"]]
            bot_msg = format_question(next_q, state["q_index"])
            state["chat_history"] = state["chat_history"] + [
                {"role": "assistant", "content": bot_msg}
            ]
            yield "", state["chat_history"], state
            return

        # All 8 answered — show "please wait" immediately, then generate
        wait_msg = "✅ 所有問題已回答完畢！正在為您生成 System Prompt，請稍候…"
        state["chat_history"] = state["chat_history"] + [
            {"role": "assistant", "content": wait_msg}
        ]
        yield "", state["chat_history"], state

        user_msg_content = build_user_message(state["answers"])
        messages = [SystemMessage(content=META_PROMPT), HumanMessage(content=user_msg_content)]
        response = llm.invoke(messages)
        generated = sanitize(response.content)

        state["phase"] = "refine"
        state["lc_history"] = [
            HumanMessage(content=user_msg_content),
            AIMessage(content=generated),
        ]

        result_msg = (
            "## 🤖 生成的 System Prompt\n\n"
            "---\n\n"
            f"{generated}\n\n"
            "---\n\n"
            "📝 您可以繼續輸入修改建議來優化 Prompt，或直接複製上面的結果使用。"
        )
        # Replace the "please wait" bubble with the actual result
        state["chat_history"] = state["chat_history"][:-1] + [
            {"role": "assistant", "content": result_msg}
        ]
        yield "", state["chat_history"], state
        return

    # ── Refinement phase ────────────────────────────────────────────────────
    if state["phase"] == "refine":
        state["chat_history"] = state["chat_history"] + [
            {"role": "assistant", "content": "⏳ 思考中…"}
        ]
        yield "", state["chat_history"], state

        state["lc_history"].append(HumanMessage(content=user_message))
        messages = [SystemMessage(content=META_PROMPT)] + state["lc_history"]
        response = llm.invoke(messages)
        reply = sanitize(response.content)
        state["lc_history"].append(AIMessage(content=reply))

        state["chat_history"] = state["chat_history"][:-1] + [
            {"role": "assistant", "content": reply}
        ]
        yield "", state["chat_history"], state
        return

    yield "", state["chat_history"], state


# ── UI ────────────────────────────────────────────────────────────────────────
with gr.Blocks(title="提示詞大師 (LangGraph)") as demo:
    gr.Markdown("# ✨ 提示詞大師 (LangGraph)")
    gr.Markdown("*Generate a tailored AI system/user prompt via guided questions*")

    # Chatbot is OUTPUT-ONLY — history format is always controlled by our state dict
    chatbot = gr.Chatbot(
        value=[{"role": "assistant", "content": WELCOME_MSG}],
        height=620,
        label="對話視窗",
    )
    state = gr.State(None)

    with gr.Row():
        msg = gr.Textbox(
            placeholder="請在此輸入您的回覆，按 Enter 或點擊「送出」…",
            show_label=False,
            scale=8,
            autofocus=True,
        )
        submit_btn = gr.Button("送出 ➤", scale=1, variant="primary")
        clear_btn = gr.Button("清除", scale=1, variant="secondary")

    with gr.Row():
        file_upload = gr.File(
            label="📎 上傳文件或圖片（PDF、Word、TXT、PNG、JPG、WEBP…）",
            file_types=[
                ".pdf", ".docx", ".txt", ".md", ".csv", ".json", ".xml", ".html",
                ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp",
            ],
            scale=1,
        )

    def clear():
        fresh = make_state()
        return "", fresh["chat_history"], None

    msg.submit(respond, [msg, state], [msg, chatbot, state])
    submit_btn.click(respond, [msg, state], [msg, chatbot, state])
    clear_btn.click(clear, outputs=[msg, chatbot, state])
    file_upload.upload(lambda f: extract_text(f), inputs=[file_upload], outputs=[msg])


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, theme=gr.themes.Soft())
