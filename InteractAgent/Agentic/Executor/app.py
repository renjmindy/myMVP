import os
import base64
import tempfile
from typing import List, Tuple, Annotated, TypedDict
import operator
import gradio as gr
import markdown as md

from openai import OpenAI
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from langgraph.graph import END, StateGraph

# ── Clients ────────────────────────────────────────────────────────────────────
_api_key = os.environ.get("OPENAI_API_KEY")
openai_client = OpenAI(api_key=_api_key)
llm_4o = ChatOpenAI(model="gpt-4o", temperature=0.7, api_key=_api_key)
llm_mini = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=_api_key)

# ── File extraction helpers ────────────────────────────────────────────────────
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff", ".svg"}
MIME_MAP = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "gif": "gif",
            "webp": "webp", "bmp": "bmp", "tiff": "tiff", "svg": "svg+xml"}

def _extract_pdf(path: str) -> str:
    from pypdf import PdfReader
    reader = PdfReader(path)
    return "\n\n".join(page.extract_text() or "" for page in reader.pages)

def _extract_docx(path: str) -> str:
    from docx import Document
    doc = Document(path)
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())

def _extract_pptx(path: str) -> str:
    from pptx import Presentation
    prs = Presentation(path)
    slides = []
    for i, slide in enumerate(prs.slides, 1):
        texts = [shape.text for shape in slide.shapes if shape.has_text_frame]
        slides.append(f"[投影片 {i}]\n" + "\n".join(texts))
    return "\n\n".join(slides)

def _extract_excel(path: str) -> str:
    import pandas as pd
    xl = pd.ExcelFile(path)
    parts = []
    for sheet in xl.sheet_names:
        df = xl.parse(sheet)
        parts.append(f"[工作表: {sheet}]\n{df.to_string(index=False)}")
    return "\n\n".join(parts)

def _extract_csv(path: str) -> str:
    import pandas as pd
    df = pd.read_csv(path)
    return df.to_string(index=False)

def _extract_image(path: str) -> str:
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    mime = f"image/{MIME_MAP.get(ext, 'png')}"
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    resp = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": "請詳細描述這張圖表或圖片的所有內容，包含數據、標題、標籤、趨勢與重要訊息，以便用於課程教材設計。"},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
            ],
        }],
        max_tokens=1500,
    )
    return f"[圖表內容分析]\n{resp.choices[0].message.content}"

def extract_file_text(file_obj) -> str:
    if file_obj is None:
        return ""
    path = file_obj.name if hasattr(file_obj, "name") else str(file_obj)
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == ".pdf":
            return _extract_pdf(path)
        elif ext == ".docx":
            return _extract_docx(path)
        elif ext in {".pptx", ".ppt"}:
            return _extract_pptx(path)
        elif ext in {".xlsx", ".xls"}:
            return _extract_excel(path)
        elif ext == ".csv":
            return _extract_csv(path)
        elif ext in IMAGE_EXTS:
            return _extract_image(path)
        else:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
    except Exception as e:
        return f"[文件讀取失敗：{e}]"

def extract_files_text(file_list) -> str:
    if not file_list:
        return ""
    if not isinstance(file_list, list):
        file_list = [file_list]
    parts = []
    for f in file_list:
        name = os.path.basename(f.name if hasattr(f, "name") else str(f))
        text = extract_file_text(f)
        parts.append(f"=== {name} ===\n{text}")
    return "\n\n".join(parts)

# ── HTML export helper ─────────────────────────────────────────────────────────
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-TW">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AI課程教材轉譯結果</title>
  <style>
    body {{ font-family: "Noto Sans TC", "Microsoft JhengHei", sans-serif;
            max-width: 960px; margin: 40px auto; padding: 0 24px;
            color: #1a1a1a; line-height: 1.8; background: #fafafa; }}
    h1, h2, h3 {{ color: #2563eb; margin-top: 2em; }}
    h2 {{ border-bottom: 2px solid #e5e7eb; padding-bottom: 6px; }}
    table {{ border-collapse: collapse; width: 100%; margin: 1em 0; }}
    th {{ background: #2563eb; color: white; padding: 10px 14px; text-align: left; }}
    td {{ padding: 8px 14px; border: 1px solid #d1d5db; }}
    tr:nth-child(even) {{ background: #f3f4f6; }}
    code {{ background: #f1f5f9; padding: 2px 6px; border-radius: 4px; font-size: 0.9em; }}
    pre {{ background: #1e293b; color: #e2e8f0; padding: 16px; border-radius: 8px; overflow-x: auto; }}
    hr {{ border: none; border-top: 1px solid #e5e7eb; margin: 2em 0; }}
    blockquote {{ border-left: 4px solid #2563eb; margin: 0; padding: 8px 16px;
                  background: #eff6ff; color: #1e40af; }}
  </style>
</head>
<body>
{body}
</body>
</html>"""

def generate_html_file(markdown_content: str):
    if not markdown_content or markdown_content.startswith("*送出資料後"):
        return None
    body = md.markdown(markdown_content, extensions=["tables", "fenced_code", "nl2br"])
    html = HTML_TEMPLATE.format(body=body)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".html",
                                      mode="w", encoding="utf-8")
    tmp.write(html)
    tmp.close()
    return tmp.name

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — AI課程教材轉譯與受眾案例設計Agent (Plan-Execute架構)
# ══════════════════════════════════════════════════════════════════════════════

COURSE_AGENT_SYSTEM = """
你是我的專屬課程教材設計助理，名稱為「AI課程教材轉譯與受眾案例設計Agent」。
你熟悉我的教學風格：先有趣，再理論，再實作；重視受眾痛點、實務案例、工作流程、AI工具操作、簡報呈現與課堂活動。
你的任務不是整理資料，而是根據我提供的資料，轉化成適合「企業與跨職能AI初學者」的課程案例、教材內容、實作活動、提示詞與簡報頁面。

## 確認受眾輪廓
這批學員多數已經聽過或使用過AI，但自評能力仍以新手與初階為主。
他們不是完全沒有動機，而是缺乏清楚的方法、範本、工作流程與實際操作經驗。
課程不能只介紹AI工具，也不能一開始就講太深的技術原理。
最有效的教學方式是從他們每天遇到的工作痛點切入，讓他們看到AI如何協助完成資料分析、文件整理、簡報製作、流程自動化與行銷內容產出。

**學員關鍵特徵：**
- 多數已有AI接觸經驗，但缺乏系統化方法
- 多數自評為新手或初階
- 幾乎全體對建立AI Agent有興趣
- 主要需求集中在資料分析、文書整理、流程自動化、提案簡報、會議紀錄、行銷文案
- 產業以製造業為最大宗，但也包含服務業、教育、資訊科技與其他產業
- 職能橫跨數據分析、業務、行銷、社群、主管、行政與教育訓練
- 常用文件包含PPT、Excel、Word、企劃書、會議紀錄、社群貼文與報價單

**教學涵義：**
這批學員最需要的不是AI概念介紹，而是「把AI放進工作流程」。
課程應該用簡報、Excel、報告、會議紀錄、業務資料、行銷文案等共同文件作為主要案例。
每個單元都要讓學員帶走一個可複製的模板、提示詞或小型SOP。

## 我的教學風格
- 先用痛點或有趣案例開場
- 再拆解背後概念
- 接著示範AI工具如何處理
- 最後讓學員自己操作
- 不只教工具功能，要教「什麼情境該怎麼用」
- 內容要好講、好理解、好練習
- 案例要貼近企業現場與跨職能工作
- 簡報內容不能只有圖多字少，也不能像密密麻麻的講義
- 每個概念都要能轉成案例、活動、提示詞或工作流程

## 課程設計定位
這門課要讓學員從「零散使用AI」進階到「用AI改造一個工作流程」。
教學重點不是炫技，而是讓學員知道：
- 我現在最耗時的工作，可以怎麼拆解？
- 哪些步驟適合交給AI？
- 怎麼下提示詞？
- 怎麼檢查AI產出？
- 怎麼把結果整理成簡報、報告或可交付成果？

## 五大優先主題
1. **AI資料整理與報告自動化** — 最大公約數需求，適合結合Excel、資料摘要、週報、主管報告與簡報初稿
   - 案例：Excel銷售資料整理成分析報告、客戶名單轉成分群建議、生產或業務數據轉成主管簡報、問卷資料轉成洞察與課程建議
2. **AI簡報與提案製作** — PPT是最高頻文件之一，適合所有職能，最容易讓學員快速有感
   - 案例：把企劃書轉成10頁簡報、把會議資料整理成主管簡報、把產品資料轉成業務提案、把課程內容轉成招生簡報
3. **個人AI Agent與工作流程設計** — 幾乎所有學員都想建立AI Agent，需用低門檻方式教
   - 案例：Email重點整理助理、客戶追蹤提醒助理、會議紀錄整理助理、競品資料蒐集與摘要助理、報價合約重點整理助理
4. **AI行銷文案與社群內容工廠** — 適合行銷、業務、創業與副業族群，可作為高需求應用模組
   - 案例：社群貼文批次生成、廣告文案改寫、產品賣點萃取、競品文案分析、SEO與AEO內容優化
5. **AI會議紀錄與文書整理** — 入門門檻低，立即見效，適合作為課程暖身或第一個實作
   - 案例：會議逐字稿轉成決議與待辦、客戶訪談紀錄轉成需求表、工作日誌轉成週報、合約或報價單轉成重點摘要

## 當使用者提供資料時
不要直接摘要。請先分析：
- 這份資料適合用來教哪個概念？
- 對這批學員而言，哪個工作場景最有感？
- 可以變成什麼案例？
- 可以安排什麼實作？
- 可以產出什麼簡報頁？

必須轉化成以下所有項目：受眾聽得懂的白話說法、企業現場案例、教師上課講解稿、學員實作任務、可直接使用的提示詞、簡報頁面內容、課堂提問、作業或延伸任務、檢查AI產出的標準。

## 案例設計規則
每個案例必須包含：案例名稱、適合職能、對應痛點、原始資料類型、AI協助方式、操作步驟、可使用提示詞、預期產出、教師講解重點、學員容易犯的錯、延伸應用。

## 輸出前品質檢查
產出前請確認：
- 是否符合企業與跨職能初學者
- 是否對應資料分析、簡報、文書、流程自動化或行銷需求
- 是否能讓學員當場操作
- 是否有可帶走的模板或SOP
- 是否避免只介紹AI工具
- 是否避免過度技術化
- 是否符合先有趣、再理論、再實作
- 是否適合拿來做簡報與上課

## 限制
- 不要只摘要資料
- 不要寫成泛用AI課程
- 不要把學員當成完全不懂AI的人
- 不要把課程設計得太技術導向
- 不要使用離企業工作太遠的案例
- 不要只給概念，要給案例、提示詞、活動與產出
- 不要一直反問，資訊不足時先做合理假設並標示

## 預設受眾（如未指定）
已接觸AI但仍屬新手到初階的企業學員，工作內容橫跨資料分析、業務、行銷、主管、行政與教育訓練。
產業以製造業為主要案例核心，再補充服務業、教育、資訊科技與創業副業情境。
"""

SECTION_FORMATS = {
    "一、這份資料適合怎麼教": """\
請用以下表格格式輸出：
| 判斷項目 | 內容 |
|---|---|
| 適合的課程單元 |  |
| 對應受眾痛點 |  |
| 最適合的職能族群 |  |
| 可轉成的案例 |  |
| 不適合直接教的地方 |  |""",

    "二、教材轉譯表": """\
請用以下表格格式輸出：
| 原始概念 | 學員聽得懂的說法 | 對應工作場景 | 教學重點 |
|---|---|---|---|""",

    "三、企業現場案例設計": """\
請用以下表格格式輸出，每個案例包含所有必填欄位：
| 案例名稱 | 適合職能 | 情境 | AI任務 | 預期產出 |
|---|---|---|---|---|
之後再逐一展開每個案例的完整設計（適合職能、對應痛點、原始資料類型、AI協助方式、操作步驟、可使用提示詞、預期產出、教師講解重點、學員容易犯的錯、延伸應用）。""",

    "四、課堂實作活動": """\
請用以下表格格式輸出：
| 階段 | 時間 | 教師做什麼 | 學員做什麼 | 產出 |
|---|---:|---|---|---|""",

    "五、學員可直接使用的提示詞": """\
請提供完整提示詞，包含角色、背景、任務、限制、輸出格式與檢查標準。每個提示詞單獨呈現，清楚標示使用場景。""",

    "六、教師講解稿": """\
請提供一段自然、可直接上課使用的講解內容，語氣口語、好講、有節奏，包含開場、概念說明、案例示範與小結。""",

    "七、簡報頁面建議": """\
請用以下表格格式輸出：
| 頁面 | 標題 | 核心訊息 | 畫面建議 | 講解重點 |
|---|---|---|---|---|""",

    "八、作業或延伸任務": """\
請用以下表格格式輸出：
| 類型 | 任務 | 評量重點 |
|---|---|---|""",
}

SECTIONS = [
    "一、這份資料適合怎麼教",
    "二、教材轉譯表",
    "三、企業現場案例設計",
    "四、課堂實作活動",
    "五、學員可直接使用的提示詞",
    "六、教師講解稿",
    "七、簡報頁面建議",
    "八、作業或延伸任務",
]

TOPIC_CHOICES = [
    "自動判斷",
    "AI資料整理與報告自動化",
    "AI簡報與提案製作",
    "個人AI Agent與工作流程設計",
    "AI行銷文案與社群內容工廠",
    "AI會議紀錄與文書整理",
]

# ── Course Design: State & Models ──────────────────────────────────────────────
class CourseState(TypedDict):
    input: str
    topic_focus: str
    plan: List[str]
    past_steps: Annotated[List[Tuple[str, str]], operator.add]
    response: str

class CoursePlan(BaseModel):
    """教材轉譯章節計畫"""
    steps: List[str] = Field(description="依序需要產出的章節名稱列表")

# ── Course Design: Nodes ───────────────────────────────────────────────────────
def course_planner(state: CourseState):
    topic_hint = f"\n聚焦主題：{state['topic_focus']}" if state.get("topic_focus") else ""
    prompt = ChatPromptTemplate.from_messages([
        ("system", COURSE_AGENT_SYSTEM),
        ("human",
         "請分析以下教材內容，決定最適合產出的章節順序。\n"
         "可選章節：" + "／".join(SECTIONS) + "\n"
         "請列出所有八個章節，依最佳教學邏輯排序。{topic_hint}\n\n"
         "教材內容：\n{input}")
    ])
    planner = prompt | llm_4o.with_structured_output(CoursePlan)
    result = planner.invoke({"input": state["input"], "topic_hint": topic_hint})
    return {"plan": result.steps}

def course_executor(state: CourseState):
    section = state["plan"][0]
    completed = "\n\n".join(
        f"### {s}\n{r}" for s, r in state["past_steps"]
    ) if state["past_steps"] else "（尚無已完成章節）"
    section_key = next((k for k in SECTION_FORMATS if k in section), None)
    format_hint = f"\n\n**格式要求：**\n{SECTION_FORMATS[section_key]}" if section_key else ""
    prompt = ChatPromptTemplate.from_messages([
        ("system", COURSE_AGENT_SYSTEM),
        ("human",
         "原始教材：\n{input}\n\n"
         "已完成章節（供參考，保持一致性）：\n{completed}\n\n"
         "請現在產出「{section}」的完整內容。內容要具體、可直接使用。{format_hint}")
    ])
    chain = prompt | llm_4o
    result = chain.invoke({
        "input": state["input"],
        "completed": completed,
        "section": section,
        "format_hint": format_hint,
    })
    return {"past_steps": [(section, result.content)]}

def course_replanner(state: CourseState):
    remaining = state["plan"][1:]
    if not remaining:
        full_output = "\n\n---\n\n".join(
            f"## {section}\n\n{content}"
            for section, content in state["past_steps"]
        )
        return {"response": full_output}
    return {"plan": remaining}

def course_should_end(state: CourseState):
    return "end" if state.get("response") else "continue"

def build_course_graph():
    wf = StateGraph(CourseState)
    wf.add_node("planner", course_planner)
    wf.add_node("executor", course_executor)
    wf.add_node("re_planner", course_replanner)
    wf.set_entry_point("planner")
    wf.add_edge("planner", "executor")
    wf.add_edge("executor", "re_planner")
    wf.add_conditional_edges("re_planner", course_should_end, {"continue": "executor", "end": END})
    return wf.compile()

course_graph = build_course_graph()

def run_course_design(materials: str, topic_focus: str):
    if not materials.strip():
        yield "⚠️ 請輸入教材內容後再送出。"
        return

    inputs = {
        "input": materials,
        "topic_focus": topic_focus if topic_focus != "自動判斷" else "",
    }

    output = ""
    plan_shown = False

    for event in course_graph.stream(inputs, {"recursion_limit": 30}):
        for node_name, value in event.items():
            if node_name == "planner" and "plan" in value and not plan_shown:
                plan_shown = True
                output = "### 📋 章節規劃\n" + "\n".join(
                    f"{i+1}. {s}" for i, s in enumerate(value["plan"])
                ) + "\n\n---\n\n*逐章節生成中……*\n\n"
                yield output
            elif node_name == "executor" and "past_steps" in value:
                for section, content in value["past_steps"]:
                    # Replace the "generating" notice and append completed section
                    output = output.replace("*逐章節生成中……*\n\n", "")
                    output += f"## {section}\n\n{content}\n\n---\n\n*逐章節生成中……*\n\n"
                    yield output
            elif node_name == "re_planner" and value.get("response"):
                # All sections done — show clean final output
                yield value["response"]


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — 行銷計畫執行工作流 (Plan-Execute)
# ══════════════════════════════════════════════════════════════════════════════

class PlanExecuteState(TypedDict):
    input: str
    plan: List[str]
    past_steps: Annotated[List[Tuple[str, str]], operator.add]
    response: str

class Plan(BaseModel):
    """計畫列表"""
    steps: List[str] = Field(description="需要執行的步驟列表")

class Response(BaseModel):
    """最終回覆"""
    response: str

def planner_node(state: PlanExecuteState):
    prompt = ChatPromptTemplate.from_template(
        "你是一個高級規劃助手。針對問題: {input}，拆解為詳細的執行步驟。不要回答問題，只需列出步驟。"
    )
    planner = prompt | llm_mini.with_structured_output(Plan)
    result = planner.invoke({"input": state["input"]})
    return {"plan": result.steps}

def executor_node(state: PlanExecuteState):
    task = state["plan"][0]
    prompt = ChatPromptTemplate.from_template(
        "你是一個執行助手。請針對以下任務給出具體的執行結果與分析：\n\n任務：{task}\n\n背景問題：{input}"
    )
    chain = prompt | llm_mini
    result = chain.invoke({"task": task, "input": state["input"]})
    return {"past_steps": [(task, result.content)]}

def replanner_node(state: PlanExecuteState):
    prompt = ChatPromptTemplate.from_template(
        "原始問題: {input}\n已完成步驟: {past_steps}\n當前計畫: {plan}\n"
        "如果任務已完成，請給出最終回答；如果未完成，請更新剩餘計畫。只回答最終結論或更新步驟。"
    )
    remaining = state["plan"][1:]
    if not remaining:
        chain = prompt | llm_mini
        result = chain.invoke({
            "input": state["input"],
            "past_steps": state["past_steps"],
            "plan": state["plan"],
        })
        return {"response": result.content}
    return {"plan": remaining}

def should_end(state: PlanExecuteState):
    return "end" if state.get("response") else "continue"

def build_graph():
    workflow = StateGraph(PlanExecuteState)
    workflow.add_node("planner", planner_node)
    workflow.add_node("executor", executor_node)
    workflow.add_node("re_planner", replanner_node)
    workflow.set_entry_point("planner")
    workflow.add_edge("planner", "executor")
    workflow.add_edge("executor", "re_planner")
    workflow.add_conditional_edges("re_planner", should_end, {"continue": "executor", "end": END})
    return workflow.compile()

app_graph = build_graph()

def run_workflow(question: str):
    if not question.strip():
        return "", "", ""

    plan_output = ""
    steps_output = ""
    final_output = ""

    for event in app_graph.stream({"input": question}, {"recursion_limit": 20}):
        for node_name, value in event.items():
            if node_name == "planner" and "plan" in value:
                plan_output = "\n".join(f"{i+1}. {s}" for i, s in enumerate(value["plan"]))
            elif node_name == "executor" and "past_steps" in value:
                for task, result in value["past_steps"]:
                    steps_output += f"**任務：** {task}\n\n**結果：** {result}\n\n---\n\n"
            elif node_name == "re_planner" and value.get("response"):
                final_output = value["response"]

    return plan_output, steps_output.strip(), final_output


# ══════════════════════════════════════════════════════════════════════════════
# Gradio UI
# ══════════════════════════════════════════════════════════════════════════════

with gr.Blocks(title="AI課程教材設計 & 計畫執行工作流", theme=gr.themes.Soft()) as demo:

    # ── Tab 1 ──────────────────────────────────────────────────────────────────
    with gr.Tab("📚 課程教材轉譯Agent"):
        gr.Markdown(
            "# AI課程教材轉譯與受眾案例設計Agent\n"
            "以 **Plan-Execute** 架構逐章節生成教材，適合企業跨職能AI初學者。"
        )

        # ── Upload section ──────────────────────────────────────────────────────
        with gr.Accordion("📂 上傳文件或圖表（選填）", open=False):
            gr.Markdown(
                "支援格式：**PDF、Word (.docx)、PowerPoint (.pptx)、"
                "Excel (.xlsx/.csv)、純文字 (.txt/.md/.json)、"
                "圖表圖片 (.png/.jpg/.jpeg/.gif/.webp/.svg)**\n\n"
                "上傳後將自動擷取內容並填入下方輸入框，可再手動補充。"
            )
            file_upload = gr.File(
                label="拖曳或點擊上傳（可選取多個檔案）",
                file_types=[
                    ".pdf", ".docx", ".pptx", ".xlsx", ".xls", ".csv",
                    ".txt", ".md", ".json",
                    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg",
                ],
                file_count="multiple",
            )

        # ── Main input / output row ─────────────────────────────────────────────
        with gr.Row():
            with gr.Column(scale=1):
                materials_input = gr.Textbox(
                    label="教材內容（可直接貼上或由上傳自動填入）",
                    placeholder="可以是文章、報告、數據、簡報內容、產品資訊、會議紀錄……任何原始素材",
                    lines=12,
                )
                topic_dropdown = gr.Dropdown(
                    choices=TOPIC_CHOICES,
                    value="自動判斷",
                    label="聚焦課程主題（選填）",
                )
                design_btn = gr.Button("開始轉譯教材", variant="primary", size="lg")
                clear_btn = gr.Button("清除", size="lg")
            with gr.Column(scale=2):
                design_output = gr.Markdown(
                    label="教材轉譯結果",
                    value="*送出資料後，Agent 將規劃章節並逐一生成，結果即時顯示於此……*",
                )
                # ── Download section ────────────────────────────────────────────
                with gr.Row():
                    download_btn = gr.Button("📥 下載 HTML", size="lg")
                    download_file = gr.File(
                        label="下載檔案",
                        visible=False,
                        interactive=False,
                    )

        gr.Examples(
            examples=[
                [
                    "我們公司每週要整理業務拜訪紀錄，從業務填寫的表單中，匯整成主管報告。"
                    "目前流程是：業務填Google表單 → 行政複製到Excel → 主管手動整理成PPT。"
                    "每週大約花3-4小時在這件事上，而且常常漏填或格式不一致。",
                    "AI資料整理與報告自動化",
                ],
                [
                    "我們公司推出了一款新的B2B SaaS產品，主要功能是幫助製造業廠商進行生產排程優化。"
                    "目標客戶是中小型製造業的生產主管與IT部門。"
                    "現有的業務提案都是用Word寫的，轉換率很低，客戶說看不懂。",
                    "AI簡報與提案製作",
                ],
                [
                    "我是行銷人員，每個月需要在Facebook、Instagram、LinkedIn發布30篇以上的貼文。"
                    "現在都是手寫，一篇大約花1-2小時。貼文風格要根據平台調整，但核心訊息要一致。"
                    "我們的產品是工業用清潔設備。",
                    "AI行銷文案與社群內容工廠",
                ],
            ],
            inputs=[materials_input, topic_dropdown],
        )

        # wire upload → auto-fill textarea
        file_upload.upload(
            fn=extract_files_text,
            inputs=[file_upload],
            outputs=[materials_input],
        )

        design_btn.click(
            fn=run_course_design,
            inputs=[materials_input, topic_dropdown],
            outputs=[design_output],
        )
        clear_btn.click(
            fn=lambda: (None, "", "自動判斷",
                        "*送出資料後，Agent 將規劃章節並逐一生成，結果即時顯示於此……*",
                        gr.update(visible=False)),
            outputs=[file_upload, materials_input, topic_dropdown,
                     design_output, download_file],
        )
        download_btn.click(
            fn=lambda content: (generate_html_file(content), gr.update(visible=True)),
            inputs=[design_output],
            outputs=[download_file, download_file],
        )

    # ── Tab 2 ──────────────────────────────────────────────────────────────────
    with gr.Tab("📋 行銷計畫執行工作流"):
        gr.Markdown(
            "# 行銷計畫執行工作流\n"
            "自動將複雜問題拆解為執行步驟，逐步執行並給出完整分析結果。"
        )

        with gr.Accordion("📂 上傳文件或圖表（選填）", open=False):
            gr.Markdown(
                "支援格式：**PDF、Word (.docx)、PowerPoint (.pptx)、"
                "Excel (.xlsx/.csv)、純文字 (.txt/.md/.json)、"
                "圖表圖片 (.png/.jpg/.jpeg/.gif/.webp/.svg)**\n\n"
                "上傳後將自動擷取內容並附加至下方問題輸入框。"
            )
            file_upload2 = gr.File(
                label="拖曳或點擊上傳（可選取多個檔案）",
                file_types=[
                    ".pdf", ".docx", ".pptx", ".xlsx", ".xls", ".csv",
                    ".txt", ".md", ".json",
                    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg",
                ],
                file_count="multiple",
            )

        question_input = gr.Textbox(
            label="輸入您的問題",
            placeholder="例如：如何通過三個步驟建立一個高效的 AI 自動化工作流？",
            lines=3,
        )
        run_btn = gr.Button("開始執行", variant="primary")
        with gr.Row():
            plan_box = gr.Textbox(label="📋 執行計畫", lines=8, interactive=False)
            steps_box = gr.Markdown(label="✅ 執行步驟與結果")
        final_box = gr.Textbox(label="🎯 最終答案", lines=5, interactive=False)

        file_upload2.upload(
            fn=extract_files_text,
            inputs=[file_upload2],
            outputs=[question_input],
        )

        run_btn.click(
            fn=run_workflow,
            inputs=[question_input],
            outputs=[plan_box, steps_box, final_box],
        )

        gr.Examples(
            examples=[
                ["如何通過三個步驟建立一個高效的 AI 自動化工作流？"],
                ["請規劃一個新產品上市的行銷策略，包含社群媒體、SEO 和廣告投放。"],
                ["如何在三個月內提升電商網站的轉換率？"],
            ],
            inputs=[question_input],
        )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
