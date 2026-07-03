import os
os.environ["GRADIO_MCP_SERVER"] = "false"
import base64
import tempfile
from typing import List, Tuple, Annotated, TypedDict
import operator
import gradio as gr
import markdown as md

from openai import OpenAI
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, SystemMessage
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

def generate_word_file(markdown_content: str):
    if not markdown_content or markdown_content.startswith("*送出資料後"):
        return None
    import re
    from docx import Document
    from docx.shared import RGBColor

    doc = Document()
    lines = markdown_content.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if line.startswith("### "):
            doc.add_heading(line[4:].strip(), level=3)
        elif line.startswith("## "):
            doc.add_heading(line[3:].strip(), level=2)
        elif line.startswith("# "):
            doc.add_heading(line[2:].strip(), level=1)
        elif line.startswith("|"):
            # collect contiguous table lines
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i])
                i += 1
            data_rows = [r for r in table_lines
                         if not re.match(r"^\|[-| :]+\|$", r.strip())]
            if data_rows:
                parsed = [[c.strip() for c in r.strip("|").split("|")]
                          for r in data_rows]
                ncols = max(len(r) for r in parsed)
                tbl = doc.add_table(rows=len(parsed), cols=ncols)
                tbl.style = "Table Grid"
                for ri, row in enumerate(parsed):
                    for ci, cell in enumerate(row):
                        if ci < ncols:
                            tbl.cell(ri, ci).text = cell
            continue
        elif line.startswith("---") or line == "":
            i += 1
            continue
        else:
            text = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
            text = re.sub(r"\*(.+?)\*", r"\1", text)
            if text.strip():
                doc.add_paragraph(text)
        i += 1

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
    tmp.close()
    doc.save(tmp.name)
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

def run_course_design(materials: str, topic_focus: str, user_prompt: str = ""):
    if user_prompt and user_prompt.strip():
        materials = materials + f"\n\n---\n使用者額外指示：\n{user_prompt.strip()}"
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
# TAB 2 — 客戶提案總監Agent (Plan-Execute架構)
# ══════════════════════════════════════════════════════════════════════════════

PROPOSAL_AGENT_SYSTEM = """
你是一位 B2B 製造業客戶提案總監Agent，名稱為「客戶提案總監Agent」。
你擅長整合商品型錄圖片、Excel 報價表、客戶需求、業務筆記與初步大綱，
產出圖文並茂、有深度、有邏輯、可交付給客戶的正式提案計畫書。

## 主要目標
協助使用者把零散資料整理成正式商務提案，
讓客戶快速理解問題、看見方案價值、降低採購疑慮，
並願意安排下一步會議、PoC 試點或下訂。

## 目標受眾
- 製造業客戶主管
- 採購決策者
- 廠務與品保主管
- 經營者
- 業務與提案團隊

## 輸入資料處理方式
- **商品型錄圖片**：整理產品名稱、功能重點、規格資訊與建議放置章節
- **Excel 報價表**：整理報價項目、金額摘要、付款條件，轉成客戶看得懂的投資說明
- **客戶需求**：分析客戶現況、痛點、決策因素與可能疑慮
- **業務筆記**：將零散想法轉成提案主軸、銷售論點與客戶利益
- **提案大綱**：補強原始大綱，建立正式商務提案架構

## 思考規則
- 先理解客戶痛點，再介紹產品
- 每一個產品功能都要對應一個客戶問題
- 每一個報價項目都要說明它帶來的價值
- 提案不能只是產品型錄重排，也不能只是報價單整理
- 必須有現況診斷、解決方案、導入流程、效益、風險配套與下一步行動
- 不得編造不存在的數字、成果、保證或客戶案例
- 資料不足時，請標示「需補充資料」，並列出建議補充問題
- 語氣要正式、清楚、具商務說服力，適合提供給企業客戶閱讀

## 銷售邏輯
- 先說明客戶目前可能承擔的風險或損失
- 再說明方案如何降低風險、提升效率或改善管理
- 將技術規格轉成客戶能理解的營運價值
- 將報價金額轉成投資項目與合作價值
- 建議採用「先 PoC 試點，再多線擴展」降低客戶疑慮
- 結尾必須給出明確下一步行動

## 寫作風格
語氣：正式、專業、清楚、有商務說服力
避免：空泛口號、過度誇張、制式模板語氣、只列規格不說價值、只列價格不說投資理由
偏好：客戶痛點導向、問題診斷導向、解決方案導向、低風險試點導向、成效驗證導向、下一步行動導向

## 輸出前品質檢查
- 是否清楚說明客戶痛點？
- 是否把產品規格轉成客戶價值？
- 是否把報價表轉成投資說明？
- 是否有圖片配置建議？
- 是否有必要表格？
- 是否有導入流程？
- 是否有風險配套？
- 是否有下一步行動？
- 是否避免誇大與亂編？
- 是否像一份可交付給客戶的正式商務提案？

若資料不足，請先列出不足處，但仍要依現有資料產出可用初稿。
"""

PROPOSAL_SECTIONS = [
    "提案封面資訊",
    "執行摘要",
    "客戶現況與問題診斷",
    "本次提案核心主張",
    "解決方案總覽",
    "商品型錄圖片整合說明",
    "產品與規格摘要",
    "客戶痛點與方案對應表",
    "導入流程與時程規劃",
    "報價與投資說明",
    "預期效益與驗證方式",
    "風險與配套措施",
    "為什麼選擇我們",
    "建議下一步",
    "附錄",
]

PROPOSAL_SECTION_FORMATS = {
    "提案封面資訊": "請列出：提案名稱、提案對象（公司名稱與聯絡人）、提案日期、提案單位、版本號。",
    "執行摘要": "用200字以內濃縮整份提案的核心價值主張、方案亮點與建議下一步行動。",
    "客戶現況與問題診斷": "說明客戶目前面臨的問題、風險與損失，以及不解決問題的代價。",
    "本次提案核心主張": "用一段話說明本次提案的核心主張與差異化價值。",
    "解決方案總覽": "概述提案的解決方案架構與模組，搭配圖表說明整體方案邏輯。",
    "商品型錄圖片整合說明": "針對每張圖片提供：建議放置章節、圖片標題、圖片說明文字、在提案中的說服作用。若無圖片資料，請標示需補充並說明建議拍攝或準備的圖片類型。",
    "產品與規格摘要": """\
請用以下表格格式輸出：
| 產品名稱 | 型號／規格 | 核心功能 | 適用場景 | 備註 |
|---|---|---|---|---|""",
    "客戶痛點與方案對應表": """\
請用以下表格格式輸出：
| 客戶痛點 | 目前影響 | 本方案如何解決 | 預期改善 |
|---|---|---|---|""",
    "導入流程與時程規劃": """\
請用以下表格格式輸出：
| 階段 | 工作項目 | 負責方 | 時程 | 交付物 |
|---|---|---|---|---|""",
    "報價與投資說明": """\
請用以下表格格式輸出：
| 項目 | 說明 | 數量 | 單價 | 小計 | 客戶獲得的價值 |
|---|---|---|---|---|---|
最後加上付款條件與合作期限說明。若無報價資料，請標示需補充。""",
    "預期效益與驗證方式": """\
請用以下表格格式輸出：
| 效益項目 | 目前狀況 | 導入後預期 | 驗證方式 | 衡量指標 |
|---|---|---|---|---|""",
    "風險與配套措施": """\
請用以下表格格式輸出：
| 潛在風險 | 風險等級 | 配套措施 | 責任方 |
|---|---|---|---|""",
    "為什麼選擇我們": "說明核心差異化優勢、過往經驗、服務保障與合作誠意，語氣正式有說服力。",
    "建議下一步": """\
請用以下表格格式輸出：
| 步驟 | 行動項目 | 建議時間 | 負責方 |
|---|---|---|---|
最後加上一段促成下一步會議或 PoC 試點的邀請語。""",
    "附錄": "放置補充資料、參考規格、詞彙說明，或列出「需補充資料」清單與建議補充問題。",
}

class ProposalState(TypedDict):
    input: str
    plan: List[str]
    past_steps: Annotated[List[Tuple[str, str]], operator.add]
    response: str

class ProposalPlan(BaseModel):
    """提案章節計畫"""
    steps: List[str] = Field(description="依序需要產出的提案章節名稱列表")

def proposal_planner(state: ProposalState):
    prompt = ChatPromptTemplate.from_messages([
        ("system", PROPOSAL_AGENT_SYSTEM),
        ("human",
         "請分析以下資料，決定最適合的提案章節順序。\n"
         "可選章節：" + "／".join(PROPOSAL_SECTIONS) + "\n"
         "請列出所有章節，依最佳商務提案邏輯排序。\n\n"
         "資料內容：\n{input}")
    ])
    planner = prompt | llm_4o.with_structured_output(ProposalPlan)
    result = planner.invoke({"input": state["input"]})
    return {"plan": result.steps}

def proposal_executor(state: ProposalState):
    section = state["plan"][0]
    completed = "\n\n".join(
        f"### {s}\n{r}" for s, r in state["past_steps"]
    ) if state["past_steps"] else "（尚無已完成章節）"
    section_key = next((k for k in PROPOSAL_SECTION_FORMATS if k in section), None)
    format_hint = f"\n\n**格式要求：**\n{PROPOSAL_SECTION_FORMATS[section_key]}" if section_key else ""
    prompt = ChatPromptTemplate.from_messages([
        ("system", PROPOSAL_AGENT_SYSTEM),
        ("human",
         "原始資料：\n{input}\n\n"
         "已完成章節（供參考，保持一致性）：\n{completed}\n\n"
         "請現在產出「{section}」的完整內容。內容要具體、正式、可直接交付給客戶。{format_hint}")
    ])
    chain = prompt | llm_4o
    result = chain.invoke({
        "input": state["input"],
        "completed": completed,
        "section": section,
        "format_hint": format_hint,
    })
    return {"past_steps": [(section, result.content)]}

def proposal_replanner(state: ProposalState):
    remaining = state["plan"][1:]
    if not remaining:
        full_output = "\n\n---\n\n".join(
            f"## {section}\n\n{content}"
            for section, content in state["past_steps"]
        )
        return {"response": full_output}
    return {"plan": remaining}

def proposal_should_end(state: ProposalState):
    return "end" if state.get("response") else "continue"

def build_proposal_graph():
    wf = StateGraph(ProposalState)
    wf.add_node("planner", proposal_planner)
    wf.add_node("executor", proposal_executor)
    wf.add_node("re_planner", proposal_replanner)
    wf.set_entry_point("planner")
    wf.add_edge("planner", "executor")
    wf.add_edge("executor", "re_planner")
    wf.add_conditional_edges("re_planner", proposal_should_end, {"continue": "executor", "end": END})
    return wf.compile()

proposal_graph = build_proposal_graph()

def run_proposal_design(materials: str, user_prompt: str = ""):
    if user_prompt and user_prompt.strip():
        materials = materials + f"\n\n---\n使用者額外指示：\n{user_prompt.strip()}"
    if not materials.strip():
        yield "⚠️ 請輸入資料後再送出。"
        return

    output = ""
    plan_shown = False

    for event in proposal_graph.stream({"input": materials}, {"recursion_limit": 40}):
        for node_name, value in event.items():
            if node_name == "planner" and "plan" in value and not plan_shown:
                plan_shown = True
                output = "### 📋 提案章節規劃\n" + "\n".join(
                    f"{i+1}. {s}" for i, s in enumerate(value["plan"])
                ) + "\n\n---\n\n*逐章節生成中……*\n\n"
                yield output
            elif node_name == "executor" and "past_steps" in value:
                for section, content in value["past_steps"]:
                    output = output.replace("*逐章節生成中……*\n\n", "")
                    output += f"## {section}\n\n{content}\n\n---\n\n*逐章節生成中……*\n\n"
                    yield output
            elif node_name == "re_planner" and value.get("response"):
                yield value["response"]


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Image to Commerce Decision Growth Agent (Plan-Execute架構)
# ══════════════════════════════════════════════════════════════════════════════

COMMERCE_AGENT_SYSTEM = """
你是一位品牌策略、商品定位、電商轉換、社群內容企劃、競品分析與高擴散內容設計專家，名稱為「Image to Commerce Decision Growth Agent」。
你擅長根據商品圖片，判斷商品類型、設計語言、情緒價值、使用情境、潛在客群、購買猶豫點、競品差異與市場切入位置。
你的工作是把商品圖片轉成一套可用於社群、電商頁、短影音與品牌企劃的內容策略。
每一次輸出都要讓品牌更容易被看見、被記住、被比較後選中。

## 核心原則
好文案的核心，是幫消費者更快做出選擇。每一段內容都要回答三個問題：
- 為什麼這個商品值得停下來看？
- 為什麼它值得被擁有？
- 為什麼它比其他類似選項更有記憶點？

請把商品特徵轉成具體情境、情緒價值與購買理由。
若文案偏向形容詞堆疊，請改成更具畫面感的生活場景。
若文案偏向一般商品介紹，請補上差異化觀點與消費者選擇理由。
若不同平台的內容太接近，請依平台任務重新調整語氣與結構。

## 任務清單
- 根據商品圖片判斷商品類型、設計風格、受眾與使用情境
- 將外觀特徵轉成情緒價值、購買理由、送禮理由與收藏理由
- 找出商品相對於替代品的差異化位置
- 預判消費者購買前的猶豫，並用文案自然處理
- 產出高吸引力標題、社群文案、商品頁文案與短影音腳本
- 設計具備停留、收藏、留言、分享潛力的高擴散內容
- 在沒有外部搜尋能力時，根據使用者提供的資料或圖片做保守判斷
- 維持品牌質感，讓內容有銷售力，也保有自然與可信度
- 在資訊不足時，清楚標示可見事實、合理推測與需要補充的資訊

## 圖片資訊分類原則
先整理圖片能支持的資訊，分成三類：
- **可見事實**：商品外觀、造型、色彩、比例、表面質感、包裝、情境元素、圖片中明確可見的文字或符號
- **合理推測**：可合理推測的商品風格、使用情境、情緒價值、目標客群、送禮或收藏可能性（請標示「從圖片推測」）
- **需要補充確認**：材質、尺寸、產地、耐用度、安全認證、品牌故事、銷售成績、使用者評價、實際功效

## 視覺分析原則
根據圖片進行視覺判讀，把外觀轉成消費者能感受到的語言。
重點放在商品如何進入生活，而非單純描述它長什麼樣子。
每一個視覺判斷都要連回消費者感受，推測內容請自然標示「從圖片推測」。
資訊不足處請留給使用者補充，以具體情境取代籠統形容。

## 消費者需求判斷
- 消費者為什麼會被這類商品吸引？
- 它滿足的是實用需求、情緒需求、送禮需求、收藏需求，還是空間風格需求？
- 消費者可能會拿它和哪些商品比較？
- 這個商品最適合佔據哪一個心智位置？
- 消費者滑到這張商品圖時，哪個理由會讓他停下來？

## 競品比較原則
目前無外部搜尋能力，請標示「未進行外部查找」。
可根據商品類型推測常見替代品，並標示為推測。
若要做精準比較，請提醒使用者提供競品連結、截圖或品牌名稱。
比較重點放在消費者選擇理由，以客觀比較取代攻擊語氣。

## 高擴散內容原則
高擴散內容要讓人有理由收藏、分享、標記朋友、留言或轉發，同時保有品牌質感。
以具體情境取代空泛情緒，以身份認同、生活場景、送禮時刻或實用收藏帶動擴散。

擴散觸發點類型：
- **身份認同觸發**：讓消費者覺得這很像自己、朋友、伴侶或某種生活狀態
- **情緒觸發**：放大療癒、陪伴、驚喜、可愛、幽默、儀式感、懷舊感或安全感
- **社交觸發**：讓人想標記朋友、分享給特定對象或引發互動
- **好奇觸發**：用反差、細節、造型、使用情境或意外感讓人停下來看
- **實用觸發**：讓內容具有收藏價值，例如送禮清單、佈置靈感、挑選指南

## 各平台文案任務
- **Instagram**：停留、收藏、分享；有情緒、有生活感；短句有節奏；含 hook、情境描寫、CTA、5-8個 hashtag
- **Threads**：引發共鳴與討論；像朋友聊天，真實有觀點；含 hook、延伸感受、可互動的問題或觀點
- **Facebook**：建立信任與互動；敘事完整帶溫度；含 hook、情境故事、商品價值、問句互動、CTA
- **小紅書**：分享推薦、收藏、搜尋；真實分享有體驗感；含吸睛標題、心得式描述、推薦理由、收藏導向語句
- **Pinkoi 商品頁**：設計價值與送禮理由；設計品牌感細膩；含商品亮點、使用情境、設計理念、送禮說明
- **電商商品頁**：降低購買決策成本；明確好懂購買導向；含賣點、情境、購買理由、行動引導
- **短影音腳本**：前三秒留住注意力；快節奏立刻抓住；含三秒開場畫面+台詞、商品亮點帶出、使用情境、CTA

## 語言風格規則
- 把「必買」改成具體擁有理由
- 把「很夯」改成可觀察的生活情境
- 把「超值」改成具體使用或送禮價值
- 把「很可愛」改成具體表情、細節或陪伴感
- 把「很有質感」改成材質感、色彩、線條或空間氛圍
- 文字自然、有生活感、有品牌感，也有銷售力
- 有行動引導，但不急迫

## 標題設計原則
產出十個高吸引力標題，涵蓋：好奇型、情境型、情緒型、問題型、利益型、送禮型、收藏型、設計感型、反差型、社交互動型。
標題要有生活感與記憶點，寫出想擁有的理由，貼合商品，不只追求聲量。
最後選出最推薦的標題並說明選擇理由與最適合的平台。

## 輸出品質標準
- 消費者能在三秒內知道商品值得看
- 消費者能理解商品和其他選項不同在哪裡
- 文案能把商品外觀轉成情緒、場景與購買理由
- 平台文案有明顯任務差異
- 高擴散內容有明確分享、收藏或互動理由
- 競品比較能反推我方切入位置
- 最終內容可直接交給品牌、社群或電商團隊使用
"""

COMMERCE_SECTIONS = [
    "商品圖片洞察",
    "消費者會想買的理由",
    "差異化定位",
    "競品與替代品比較",
    "高擴散內容角度",
    "十個標題候選與最佳推薦",
    "各平台文案",
    "關鍵字與 hashtag",
    "品質檢查與可補充資訊",
]

COMMERCE_SECTION_FORMATS = {
    "商品圖片洞察": """\
請分三部分輸出：
**1. 可見事實**：列出圖片中明確可見的商品外觀、造型、色彩、比例、表面質感、包裝與情境元素。
**2. 合理推測**：列出可合理推測的商品風格、使用情境、情緒價值、目標客群、送禮或收藏可能性（請標示「從圖片推測」）。
**3. 需要補充確認**：列出材質、尺寸、產地等需要使用者提供才能確認的資訊。""",

    "消費者會想買的理由": """\
請輸出：
- **情緒價值**：這個商品帶給消費者的情感滿足
- **使用情境**：最能觸發購買的具體生活場景（2-3個）
- **送禮或收藏理由**：為什麼有人會把它當禮物或收藏品
- **最強購買觸發點**：一句話說出讓人下單的核心理由
- **購買猶豫與處理**：預判主要猶豫點（2-3個）與對應的文案策略""",

    "差異化定位": """\
請輸出：
- **一句話市場定位**（說清楚這個商品在市場上的位置）
- **核心賣點**（1-2個，要比「好看」更具體）
- **和一般同類商品最大的不同之處**
- **文案應該放大的主軸**
- **文案應該避開的普通化角度**""",

    "競品與替代品比較": """\
請標示「本次未進行外部搜尋」，並：
- 推測消費者可能拿這個商品比較的替代品類型（標示為推測）
- 分析競品常見說法與我方可切入的差異化位置
- 說明消費者為什麼會選這個商品而非替代品
- 列出若要做精準競品比較，需要補充的資料""",

    "高擴散內容角度": """\
請提供五個高擴散內容角度，每個角度包含：觸發類型、最適合平台、Hook（開場句）、內容主軸、互動設計、CTA。

接著提供：
- 三則可直接使用的高擴散短文案（50-80字，每則適合不同觸發類型）
- 三個短影音開場腳本（含前三秒畫面描述與台詞）""",

    "十個標題候選與最佳推薦": """\
請提供十個不同角度的高吸引力標題（依序）：
1. 好奇型　2. 情境型　3. 情緒型　4. 問題型　5. 利益型
6. 送禮型　7. 收藏型　8. 設計感型　9. 反差型　10. 社交互動型

最後選出最推薦的標題，並說明：為什麼最有機會讓人停下來、最適合用在哪個平台或情境。""",

    "各平台文案": """\
請依序產出各平台文案：

**Instagram**（含：吸睛 hook、一段情境描寫、自然 CTA、5-8個 hashtag）

**Threads**（含：hook、一句延伸感受、可引發互動的問題或觀點）

**Facebook**（含：hook、情境故事、商品價值、問句互動、CTA）

**小紅書**（含：吸睛標題、使用心得式描述、推薦理由、收藏導向語句）

**Pinkoi 商品頁**（含：商品亮點、使用情境、設計理念、送禮說明）

**電商商品頁**（含：商品賣點、使用情境、購買理由、行動引導）

**短影音腳本**（含：三秒吸睛開場畫面+台詞、商品亮點帶出、使用情境展示、收尾 CTA）""",

    "關鍵字與 hashtag": """\
請提供：
- **社群 hashtag**（中英文混合，15-20個，分通用型與精準型）
- **搜尋關鍵字**（消費者實際會搜尋的語句，含描述詞、用途詞、送禮詞、風格詞）
- **電商導購關鍵字**（適合商品標題或描述的長尾關鍵字）
- **送禮情境關鍵字**
- **風格關鍵字**""",

    "品質檢查與可補充資訊": """\
請進行最終品質確認，以清單格式輸出各項是否達標：
- 是否有明確購買理由
- 是否有清楚差異化定位
- 是否有處理消費者猶豫
- 是否有平台文案差異
- 是否避開普通文案
- 是否具備高擴散誘因
- 是否有標示圖片無法確認的內容
- 是否把商品特徵轉成情緒與場景

最後列出：**最需要補充的商品資訊**（按優先順序排列）""",
}


class CommerceState(TypedDict):
    images: List[dict]
    extra_info: str
    plan: List[str]
    past_steps: Annotated[List[Tuple[str, str]], operator.add]
    response: str


class CommercePlan(BaseModel):
    """商品電商成長分析章節計畫"""
    steps: List[str] = Field(description="依序需要產出的分析章節名稱列表")


def _build_image_content(images: List[dict], text: str) -> list:
    content = [{"type": "text", "text": text}]
    for img in images:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:{img['mime']};base64,{img['b64']}"},
        })
    return content


def commerce_planner(state: CommerceState):
    text = (
        "請分析這些商品圖片，決定最適合產出的分析章節順序。\n"
        "可選章節：" + "／".join(COMMERCE_SECTIONS) + "\n"
        "請列出所有章節，依最佳分析邏輯排序。"
        + (f"\n\n補充商品資訊：\n{state['extra_info']}" if state.get("extra_info") else "")
    )
    messages = [
        SystemMessage(content=COMMERCE_AGENT_SYSTEM),
        HumanMessage(content=_build_image_content(state.get("images", []), text)),
    ]
    result = llm_4o.with_structured_output(CommercePlan).invoke(messages)
    return {"plan": result.steps}


def commerce_executor(state: CommerceState):
    section = state["plan"][0]
    completed = "\n\n".join(
        f"### {s}\n{r}" for s, r in state["past_steps"]
    ) if state["past_steps"] else "（尚無已完成章節）"
    section_key = next((k for k in COMMERCE_SECTION_FORMATS if k in section), None)
    format_hint = f"\n\n**格式要求：**\n{COMMERCE_SECTION_FORMATS[section_key]}" if section_key else ""
    text = (
        (f"補充商品資訊：\n{state['extra_info']}\n\n" if state.get("extra_info") else "")
        + f"已完成章節（供參考，保持一致性）：\n{completed}\n\n"
        + f"請現在產出「{section}」的完整內容。內容要具體、可直接使用。{format_hint}"
    )
    messages = [
        SystemMessage(content=COMMERCE_AGENT_SYSTEM),
        HumanMessage(content=_build_image_content(state.get("images", []), text)),
    ]
    result = llm_4o.invoke(messages)
    return {"past_steps": [(section, result.content)]}


def commerce_replanner(state: CommerceState):
    remaining = state["plan"][1:]
    if not remaining:
        full_output = "\n\n---\n\n".join(
            f"## {section}\n\n{content}"
            for section, content in state["past_steps"]
        )
        return {"response": full_output}
    return {"plan": remaining}


def commerce_should_end(state: CommerceState):
    return "end" if state.get("response") else "continue"


def build_commerce_graph():
    wf = StateGraph(CommerceState)
    wf.add_node("planner", commerce_planner)
    wf.add_node("executor", commerce_executor)
    wf.add_node("re_planner", commerce_replanner)
    wf.set_entry_point("planner")
    wf.add_edge("planner", "executor")
    wf.add_edge("executor", "re_planner")
    wf.add_conditional_edges("re_planner", commerce_should_end, {"continue": "executor", "end": END})
    return wf.compile()


commerce_graph = build_commerce_graph()

VISION_EXTS = IMAGE_EXTS - {".svg"}


def _images_from_files(file_list) -> List[dict]:
    if not file_list:
        return []
    if not isinstance(file_list, list):
        file_list = [file_list]
    images = []
    for f in file_list:
        path = f.name if hasattr(f, "name") else str(f)
        ext = os.path.splitext(path)[1].lower()
        if ext not in VISION_EXTS:
            continue
        ext_key = ext.lstrip(".")
        mime = f"image/{MIME_MAP.get(ext_key, 'png')}"
        with open(path, "rb") as fh:
            b64 = base64.b64encode(fh.read()).decode()
        images.append({"mime": mime, "b64": b64})
    return images


def run_commerce_analysis(file_list, extra_info: str, user_prompt: str = ""):
    images = _images_from_files(file_list)
    if not images:
        yield "⚠️ 請上傳至少一張商品圖片後再送出。"
        return

    info = extra_info.strip() if extra_info else ""
    if user_prompt and user_prompt.strip():
        info = (info + "\n\n" if info else "") + f"使用者額外指示：\n{user_prompt.strip()}"

    output = ""
    plan_shown = False

    for event in commerce_graph.stream(
        {"images": images, "extra_info": info}, {"recursion_limit": 30}
    ):
        for node_name, value in event.items():
            if node_name == "planner" and "plan" in value and not plan_shown:
                plan_shown = True
                output = "### 📋 分析章節規劃\n" + "\n".join(
                    f"{i+1}. {s}" for i, s in enumerate(value["plan"])
                ) + "\n\n---\n\n*逐章節生成中……*\n\n"
                yield output
            elif node_name == "executor" and "past_steps" in value:
                for section, content in value["past_steps"]:
                    output = output.replace("*逐章節生成中……*\n\n", "")
                    output += f"## {section}\n\n{content}\n\n---\n\n*逐章節生成中……*\n\n"
                    yield output
            elif node_name == "re_planner" and value.get("response"):
                yield value["response"]


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — 業務智能分析Agent Agent (Plan-Execute架構)
# ══════════════════════════════════════════════════════════════════════════════

SALES_AGENT_SYSTEM = """
你是一位擁有50年經驗的大數據分析大師、金牌業務以及產業顧問，對各行業都非常熟悉。
使用者是一位業務員，希望你協助他進行精準提案。

你的核心能力：
- 對資料進行深度分析，涵蓋質性與量化兩個維度
- 能看出潛在、容易被忽略的特性與隱藏信號
- 快速識別客戶輪廓、痛點、決策邏輯與購買動機
- 模擬不同業務策略的效果並給出具體建議
- 把數據轉成業務員可以直接使用的洞察與行動

你的分析原則：
- 每個分析都要連回業務行動，不只是觀察
- 數字要有意義，要說明背後的業務啟示
- 洞察要可操作，不只是描述現象
- 建議要具體，不只是給方向
- 客戶輪廓要生動，像是真實描述一個人
- 痛點要有優先級排序與解決建議
- 策略模擬要有具體執行步驟與成功機率估算

資訊不足時的處理：
- 先分析現有資料，盡力提供有用洞察
- 標示「資訊不足」的地方
- 列出建議補充的問題與資料

輸出語言：繁體中文，語氣專業但清晰，避免過度學術化。
"""

SALES_SECTIONS = [
    "資料總覽與執行摘要",
    "客戶輪廓與行為分析",
    "痛點偵測與影響量化",
    "深度量化分析",
    "深度質性分析",
    "潛在特性與隱藏洞察",
    "競爭態勢與市場定位",
    "策略模擬與情境分析",
    "精準提案行動計畫",
]

SALES_SECTION_FORMATS = {
    "資料總覽與執行摘要": (
        "用3-5句話說明資料類型、資料品質、最重要的3個發現，以及本次分析的業務價值。"
    ),
    "客戶輪廓與行為分析": """\
請識別並輸出所有關鍵利害關係人（若有多人請分別列出），每位格式如下：

**[姓名或代稱] / [職稱]**
- 角色類型：Champion（內部倡導者）/ Blocker（阻礙者）/ Gatekeeper（把關者）/ Influencer（影響者）/ Decision Maker（決策者）
- 屬性痛點：[顯性需求或問題，1-2句]
- 屬性需求：[功能性或流程性需求，1-2句]
- 隱性恐懼 (Deep Fear)：[說出或未說出的深層恐懼，最關鍵的心理障礙，1句核心描述]
- 決策邏輯：[如何做決定，1句]
- 最佳應對策略：[業務員如何針對此人的心理調整策略，1-2句]

最後列出：影響成交最關鍵的利害關係人與理由。""",
    "痛點偵測與影響量化": """\
請用表格輸出痛點清單：
| 痛點 | 類型（顯性/隱性） | 嚴重程度（1-10） | 業務影響 | 處理策略 |
|---|---|---|---|---|
最後說明：最高優先處理的痛點與理由。""",
    "深度量化分析": """\
提取所有可量化的指標，用表格整理：
| 指標 | 數值 | 意義 | 業務行動 |
|---|---|---|---|
並說明數字背後最重要的3個業務洞察。""",
    "深度質性分析": """\
請分析：
- **語氣與態度**（對方溝通語氣透露什麼訊號？）
- **優先級排序**（對方最在意什麼？次要考量是什麼？）
- **決策邏輯**（對方如何做決定？）
- **未說出口的需求**（從資料推測的潛在期望）
- **合作意願信號**（哪些跡象顯示合作意願高/低？）""",
    "潛在特性與隱藏洞察": """\
找出5-7個容易被忽略但對業務非常關鍵的特性，每個包含：
- **信號名稱**
- **觀察到的跡象**（具體指出資料中的哪個細節）
- **為什麼重要**（對業務的影響）
- **建議行動**（業務員應如何利用這個洞察）""",
    "競爭態勢與市場定位": """\
請分析：
- 客戶目前的選擇與替代方案
- 我方優勢與可能的弱點
- 競爭者的可能策略
- 我方最佳差異化切入點
- 一句話說明我方應如何定位""",
    "策略模擬與情境分析": """\
請模擬三種業務策略（每個包含：策略描述、風險等級、成功機率估算、4個執行步驟、預期效益）：

**策略A：快速成交型**

**策略B：關係建立型**

**策略C：顧問式提案型**

最後給出：根據本次分析，最推薦哪種策略組合及理由。""",
    "精準提案行動計畫": """\
請輸出：
**本週行動（Week 1）**（3個具體行動，含預期回應）
**短期計畫（Week 2-4）**（推進步驟與里程碑）
**中期計畫（Month 2-3）**（深化關係與方案）
**關鍵成功因子**（本次提案最需要掌握的3個要素）
**風險預警**（可能失敗的原因與預防策略）""",
}

# ── Tab 4 HTML dashboard: Python-rendered template (responsive) ────────────

_DASH_EXTRACT_SYSTEM = "你是資料結構化助理。只輸出符合要求的 JSON，不輸出任何說明。"

_DASH_EXTRACT_PROMPT = """\
請從以下業務分析報告提取資料，輸出 JSON（繁體中文）。

Schema：
{
  "subtitle": "案例或專案名稱（15字以內）",
  "data_source": "資料來源或檔案名稱（精簡）",
  "target_client": "客戶公司名稱",
  "est_value": "High（戰略級客戶）| Medium（一般客戶）| Low（觀察中）",
  "stakeholders": [
    {
      "name": "姓名或代稱",
      "title": "職稱",
      "role_type": "Champion|Blocker|Gatekeeper|Influencer|Decision Maker",
      "role_label": "中文角色說明，如 內部倡導者 (Champion)",
      "pain_points": "屬性痛點或需求，1-2句",
      "deep_fear": "隱性恐懼，1句核心描述"
    }
  ],
  "radar_dimensions": ["5個維度名稱"],
  "radar_customer": [5個數字 1-10，代表客戶期望值],
  "radar_traditional": [5個數字 1-10，傳統方案覆蓋度，通常偏低],
  "key_factor": "關鍵決定因素",
  "top_risk": "最高風險點",
  "strategies": [
    {
      "label_type": "主打|加值|商務",
      "name": "策略名稱",
      "description": "一句說明",
      "boost": 5到20之間的整數
    }
  ],
  "insights": [{"title": "洞察標題", "description": "1-2句說明"}],
  "action_plan": [
    {"phase": "Week 1", "tasks": ["任務1", "任務2"], "milestone": "里程碑說明"}
  ]
}

只輸出 JSON，不要任何說明。

---
分析報告：
{analysis}
"""

_DASH_CSS = """
:root{--bg:#0d1117;--card:#161b22;--card2:#1a2035;--gold:#f0b429;--cyan:#21d4fd;
--red:#ff6b6b;--purple:#8b5cf6;--blue:#3b82f6;--orange:#f97316;
--text:#e6edf3;--muted:#8b949e;--border:rgba(33,212,253,.15)}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{background:var(--bg);color:var(--text);font-family:'Noto Sans TC','Inter',sans-serif;font-size:14px;line-height:1.6}
img,canvas{max-width:100%;height:auto}
.topnav{display:flex;justify-content:space-between;align-items:center;padding:0 24px;min-height:70px;background:#0d1117;border-bottom:1px solid var(--border);position:sticky;top:0;z-index:100;gap:12px;flex-wrap:wrap}
.nav-left{display:flex;flex-direction:column;gap:2px}
.nav-row1{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.nav-icon{color:var(--cyan);font-size:18px;font-weight:700}
.nav-title{font-size:16px;font-weight:700;color:var(--text)}
.nav-sep{width:1px;height:18px;background:var(--border);flex-shrink:0}
.nav-sub{font-size:13px;color:var(--muted)}
.nav-src{font-size:11px;color:var(--muted);margin-top:1px}
.nav-right{display:flex;gap:24px;flex-shrink:0}
.nav-kpi{text-align:right}
.nav-kpi-lbl{font-size:10px;color:var(--muted);letter-spacing:1px;text-transform:uppercase}
.nav-kpi-val{font-size:13px;font-weight:700;color:var(--gold)}
.page{max-width:1400px;margin:0 auto;padding:20px 16px}
.main-grid{display:grid;grid-template-columns:1fr 1.3fr 1fr;gap:16px;margin-bottom:16px;align-items:start}
.bottom-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.sec-title{font-size:13px;font-weight:700;color:var(--text);margin-bottom:12px;padding-bottom:6px;border-bottom:2px solid var(--gold);display:inline-block}
.s-card{background:var(--card);border-radius:10px;padding:14px;margin-bottom:10px;border:1px solid var(--border)}
.s-header{display:flex;align-items:center;gap:10px;margin-bottom:6px}
.avatar{width:44px;height:44px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:16px;font-weight:700;flex-shrink:0}
.av-c{background:linear-gradient(135deg,#ff6b6b,#ee0979);color:#fff}
.av-b{background:linear-gradient(135deg,#8b5cf6,#6d28d9);color:#fff}
.av-i{background:linear-gradient(135deg,#3b82f6,#1d4ed8);color:#fff}
.av-d{background:linear-gradient(135deg,#f0b429,#d97706);color:#000}
.av-x{background:linear-gradient(135deg,#64748b,#475569);color:#fff}
.s-name{font-size:14px;font-weight:700;color:var(--text)}
.s-ttl{font-size:11px;color:var(--muted)}
.badge{display:inline-block;padding:2px 10px;border-radius:20px;font-size:11px;font-weight:600;margin-bottom:8px}
.bC{background:#ff6b6b;color:#fff}.bB{background:#8b5cf6;color:#fff}
.bI{background:#3b82f6;color:#fff}.bD{background:#f0b429;color:#000}.bX{background:#64748b;color:#fff}
.pain-lbl{font-size:11px;color:var(--muted);margin-bottom:3px}
.pain-txt{font-size:12px;color:var(--text);margin-bottom:8px;line-height:1.5}
.fear-box{background:rgba(249,115,22,.08);border-left:3px solid var(--orange);border-radius:4px;padding:8px 10px}
.fear-title{font-size:11px;font-weight:700;color:var(--orange);margin-bottom:2px}
.fear-txt{font-size:12px;color:var(--orange);font-style:italic;line-height:1.4}
.radar-wrap{background:var(--card);border-radius:12px;padding:16px;border:1px solid var(--border)}
.radar-canvas-box{position:relative;height:270px;margin-bottom:12px}
.radar-meta{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.rmeta-card{background:var(--card2);border-radius:8px;padding:10px 12px}
.rmeta-lbl{font-size:10px;color:var(--muted);margin-bottom:2px}
.rmeta-val{font-size:13px;font-weight:700;color:var(--text)}
.rmeta-val.risk{color:var(--red)}
.sim-wrap{background:var(--card);border-radius:12px;padding:16px;border:1px solid var(--border);display:flex;flex-direction:column}
.sim-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:4px}
.sim-title{font-size:14px;font-weight:700;color:var(--text)}
.sim-btn{font-size:11px;border:1px solid var(--gold);background:transparent;color:var(--gold);padding:3px 10px;border-radius:4px}
.sim-desc{font-size:11px;color:var(--muted);margin-bottom:14px;line-height:1.4}
.st-item{display:flex;align-items:flex-start;gap:8px;margin-bottom:12px;cursor:pointer}
.st-item input{width:16px;height:16px;margin-top:2px;accent-color:var(--cyan);flex-shrink:0;cursor:pointer}
.st-tag{font-size:10px;padding:1px 7px;border-radius:10px;font-weight:600;white-space:nowrap;margin-top:3px;flex-shrink:0}
.tag-m{background:rgba(240,180,41,.2);color:var(--gold)}
.tag-p{background:rgba(59,130,246,.2);color:var(--blue)}
.tag-b{background:rgba(100,116,139,.2);color:#94a3b8}
.st-name{font-size:13px;font-weight:700;color:var(--text)}
.st-desc{font-size:11px;color:var(--muted);line-height:1.4}
.win-card{background:var(--bg);border-radius:10px;padding:14px 16px;margin-top:auto;border:1px solid var(--border)}
.win-row{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}
.win-lbl{font-size:12px;color:var(--muted)}
.win-pct{font-size:2rem;font-weight:800;color:var(--gold);line-height:1}
.win-track{height:8px;background:#1e293b;border-radius:4px;overflow:hidden;margin-bottom:6px}
.win-bar{height:100%;border-radius:4px;background:linear-gradient(90deg,#ff6b6b,#f97316,#f0b429,#22c55e);transition:width .4s}
.win-note{font-size:11px;color:var(--muted);line-height:1.4}
.ins-card{border:1px solid var(--gold);background:rgba(240,180,41,.04);border-radius:12px;padding:20px}
.ins-title{font-size:14px;font-weight:700;color:var(--gold);margin-bottom:14px}
.ins-item{display:flex;gap:10px;margin-bottom:12px}
.ins-dot{width:8px;height:8px;border-radius:50%;background:var(--cyan);flex-shrink:0;margin-top:5px}
.ins-name{font-size:13px;font-weight:700;color:var(--text);margin-bottom:2px}
.ins-desc{font-size:12px;color:var(--muted);line-height:1.5}
.act-card{background:var(--card);border-radius:12px;padding:20px;border:1px solid var(--border)}
.act-title{font-size:14px;font-weight:700;color:var(--text);margin-bottom:16px}
.tl{display:flex;gap:0;overflow-x:auto}
.tl-col{flex:1;min-width:110px;position:relative;padding-top:24px;padding-right:8px}
.tl-col::before{content:'';position:absolute;top:7px;left:0;right:0;height:2px;background:var(--border)}
.tl-col:first-child::before{left:50%}.tl-col:last-child::before{right:50%}
.tl-dot{width:16px;height:16px;border-radius:50%;background:var(--gold);border:3px solid var(--bg);position:absolute;top:0;left:50%;transform:translateX(-50%)}
.tl-phase{font-size:10px;font-weight:700;color:var(--gold);text-align:center;margin-bottom:6px}
.tl-tasks{font-size:11px;color:var(--text);line-height:1.6}
.tl-ms{font-size:10px;color:var(--muted);margin-top:4px;font-style:italic}
@media(max-width:1100px){
  .main-grid{grid-template-columns:1fr 1fr}
  .main-grid>:last-child{grid-column:1/-1}
}
@media(max-width:768px){
  .main-grid,.bottom-grid{grid-template-columns:1fr}
  .main-grid>:last-child{grid-column:auto}
  .topnav{min-height:auto;padding:12px 16px;flex-direction:column;align-items:flex-start}
  .nav-right{width:100%;justify-content:flex-start;gap:20px}
}
@media(max-width:480px){
  .page{padding:10px 8px}
  .win-pct{font-size:1.5rem}
  .tl{flex-direction:column;gap:8px}
  .tl-col{padding-top:0;padding-left:16px;border-left:2px solid var(--border);margin-left:8px}
  .tl-col::before,.tl-dot{display:none}
}
"""


def _role_cls(role_type: str):
    r = role_type.lower()
    if "champion" in r or "倡導" in r:
        return "av-c", "bC"
    if any(x in r for x in ("blocker", "gatekeeper", "阻礙", "把關", "風險控制")):
        return "av-b", "bB"
    if "influencer" in r or "影響" in r:
        return "av-i", "bI"
    if "decision" in r or "決策" in r:
        return "av-d", "bD"
    return "av-x", "bX"


def _render_stakeholders(items: list) -> str:
    if not items:
        return '<div class="s-card"><p style="color:var(--muted)">（未識別到明確利害關係人）</p></div>'
    out = []
    for s in items:
        av, bv = _role_cls(s.get("role_type", ""))
        out.append(
            f'<div class="s-card">'
            f'<div class="s-header">'
            f'<div class="avatar {av}">{s.get("name","?")[:1]}</div>'
            f'<div><div class="s-name">{s.get("name","")}</div>'
            f'<div class="s-ttl">{s.get("title","")}</div></div></div>'
            f'<span class="badge {bv}">{s.get("role_label", s.get("role_type",""))}</span>'
            f'<div class="pain-lbl">⊕ 屬性痛點</div>'
            f'<div class="pain-txt">{s.get("pain_points","")}</div>'
            f'<div class="fear-box">'
            f'<div class="fear-title">🔮 隱性恐懼 (Deep Fear)</div>'
            f'<div class="fear-txt">{s.get("deep_fear","")}</div></div></div>'
        )
    return "".join(out)


def _render_strategies(items: list):
    if not items:
        items = [{"label_type": "主打", "name": "顧問式提案", "description": "深度理解需求後提出完整解決方案。", "boost": 15}]
    out, prob = [], 35
    for i, s in enumerate(items):
        checked = "checked" if i == 0 else ""
        if i == 0:
            prob = min(35 + s.get("boost", 0), 92)
        lt = s.get("label_type", "主打")
        tc = "tag-m" if lt == "主打" else ("tag-p" if lt == "加值" else "tag-b")
        out.append(
            f'<label class="st-item">'
            f'<input type="checkbox" class="strategy-check" '
            f'data-boost="{s.get("boost",10)}" data-note="{s.get("name","")}" {checked}>'
            f'<span class="st-tag {tc}">{lt}</span>'
            f'<div><div class="st-name">{s.get("name","")}</div>'
            f'<div class="st-desc">{s.get("description","")}</div></div></label>'
        )
    return "".join(out), prob


def _render_insights(items: list) -> str:
    return "".join(
        f'<div class="ins-item"><div class="ins-dot"></div>'
        f'<div><div class="ins-name">{i.get("title","")}</div>'
        f'<div class="ins-desc">{i.get("description","")}</div></div></div>'
        for i in items
    ) if items else '<p style="color:var(--muted);font-size:12px">（無隱藏洞察資料）</p>'


def _render_timeline(items: list) -> str:
    if not items:
        items = [
            {"phase": "Week 1", "tasks": ["初步接觸", "需求確認"], "milestone": "建立信任"},
            {"phase": "Week 2-4", "tasks": ["提案準備", "方案調整"], "milestone": "提案送出"},
            {"phase": "Month 2", "tasks": ["PoC 試點", "效益驗證"], "milestone": "初步成效"},
            {"phase": "Month 3+", "tasks": ["正式合作", "擴展計畫"], "milestone": "簽約落地"},
        ]
    return "".join(
        f'<div class="tl-col"><div class="tl-dot"></div>'
        f'<div class="tl-phase">{p.get("phase","")}</div>'
        f'<div class="tl-tasks">{"".join(f"・{t}<br>" for t in p.get("tasks",[]))}</div>'
        f'<div class="tl-ms">{p.get("milestone","")}</div></div>'
        for p in items
    )


def _extract_dashboard_json(analysis: str) -> dict:
    import json as _j
    try:
        resp = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": _DASH_EXTRACT_SYSTEM},
                {"role": "user", "content": _DASH_EXTRACT_PROMPT.format(analysis=analysis[:10000])},
            ],
            response_format={"type": "json_object"},
            max_tokens=2000,
            temperature=0,
        )
        return _j.loads(resp.choices[0].message.content)
    except Exception:
        return {}


def _render_dashboard_html(data: dict) -> str:
    import json as _j
    subtitle    = data.get("subtitle", "業務智能分析")
    data_source = data.get("data_source", "業務分析資料")
    target_client = data.get("target_client", "目標客戶")
    est_value   = data.get("est_value", "High（戰略級客戶）")
    key_factor  = data.get("key_factor", "—")
    top_risk    = data.get("top_risk", "—")

    dims   = data.get("radar_dimensions", ["客戶需求", "整合難度", "操作性", "導入風險", "效益價值"])
    r_cust = data.get("radar_customer",   [8, 7, 6, 9, 8])
    r_trad = data.get("radar_traditional",[5, 4, 6, 3, 5])
    n = max(len(dims), len(r_cust), len(r_trad))
    dims   = (dims   + ["—"] * n)[:n]
    r_cust = (r_cust + [5]   * n)[:n]
    r_trad = (r_trad + [5]   * n)[:n]

    s_html           = _render_stakeholders(data.get("stakeholders", []))
    strategies_html, init_prob = _render_strategies(data.get("strategies", []))
    ins_html         = _render_insights(data.get("insights", []))
    tl_html          = _render_timeline(data.get("action_plan", []))

    parts = [
        "<!DOCTYPE html>",
        "<html lang='zh-TW'>",
        "<head>",
        '<meta charset="UTF-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
        "<title>B2B 戰略情報室</title>",
        '<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@300;400;500;700'
        '&family=Inter:wght@300;400;500;700&display=swap" rel="stylesheet">',
        '<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>',
        f"<style>{_DASH_CSS}</style>",
        "</head>",
        "<body>",
        # ── Nav ──
        '<nav class="topnav">',
        '<div class="nav-left">',
        '<div class="nav-row1">',
        '<span class="nav-icon">≈</span>',
        '<span class="nav-title">B2B 戰略情報室</span>',
        '<div class="nav-sep"></div>',
        f'<span class="nav-sub">{subtitle}</span>',
        '</div>',
        f'<div class="nav-src">基於「{data_source}」之大數據與心理學深度解析</div>',
        '</div>',
        '<div class="nav-right">',
        f'<div class="nav-kpi"><div class="nav-kpi-lbl">TARGET CLIENT</div><div class="nav-kpi-val">{target_client}</div></div>',
        f'<div class="nav-kpi"><div class="nav-kpi-lbl">EST. VALUE</div><div class="nav-kpi-val">{est_value}</div></div>',
        '</div></nav>',
        # ── Page ──
        '<div class="page">',
        '<div class="main-grid">',
        # Col 1: Stakeholders
        f'<div><div class="sec-title">利害關係人矩陣</div>{s_html}</div>',
        # Col 2: Radar
        '<div class="radar-wrap">',
        '<div class="sec-title">專案需求維度解析</div>',
        '<div class="radar-canvas-box"><canvas id="radarChart"></canvas></div>',
        '<div class="radar-meta">',
        f'<div class="rmeta-card"><div class="rmeta-lbl">關鍵決定因素</div><div class="rmeta-val">{key_factor}</div></div>',
        f'<div class="rmeta-card"><div class="rmeta-lbl">最高風險點</div><div class="rmeta-val risk">{top_risk}</div></div>',
        '</div></div>',
        # Col 3: Strategy sim
        '<div class="sim-wrap">',
        '<div class="sim-top"><span class="sim-title">🏆 提案策略模擬器</span><span class="sim-btn">互動測試</span></div>',
        '<div class="sim-desc">勾選您預計在提案書中主打的策略，預測「贏單機率」與「客戶決策阻力」。</div>',
        strategies_html,
        '<div class="win-card">',
        '<div class="win-row"><span class="win-lbl">預測贏單機率 (Win Probability)</span>',
        f'<span class="win-pct" id="win-prob">{init_prob}%</span></div>',
        f'<div class="win-track"><div class="win-bar" id="win-bar" style="width:{init_prob}%"></div></div>',
        '<div class="win-note" id="win-note">已強化優勢：請勾選策略以啟動預測。</div>',
        '</div></div>',
        '</div>',  # end main-grid
        # ── Bottom ──
        '<div class="bottom-grid">',
        f'<div class="ins-card"><div class="ins-title">⚡ 潛在機會：容易被忽略的關鍵信號</div>{ins_html}</div>',
        f'<div class="act-card"><div class="act-title">精準行動計畫</div><div class="tl">{tl_html}</div></div>',
        '</div>',  # end bottom-grid
        '</div>',  # end page
        # ── JS ──
        "<script>",
        "function updateWinProb(){",
        "var base=35,total=base,notes=[];",
        "document.querySelectorAll('.strategy-check:checked').forEach(function(cb){",
        "total+=parseInt(cb.dataset.boost||0);",
        "if(cb.dataset.note)notes.push(cb.dataset.note);});",
        "total=Math.min(total,92);",
        "document.getElementById('win-prob').textContent=total+'%';",
        "document.getElementById('win-bar').style.width=total+'%';",
        "document.getElementById('win-note').textContent=notes.length",
        "?'已強化優勢：'+notes.join('、')+'。'",
        ":'請勾選策略以啟動預測。';}",
        "document.querySelectorAll('.strategy-check').forEach(function(cb){cb.addEventListener('change',updateWinProb);});",
        "updateWinProb();",
        f"var dims={_j.dumps(dims,ensure_ascii=False)};",
        f"var cust={_j.dumps(r_cust)};",
        f"var trad={_j.dumps(r_trad)};",
        "new Chart(document.getElementById('radarChart'),{type:'radar',",
        "data:{labels:dims,datasets:[",
        "{label:'客戶期望值（痛點強烈度）',data:cust,borderColor:'#21d4fd',",
        "backgroundColor:'rgba(33,212,253,.15)',pointBackgroundColor:'#21d4fd',borderWidth:2},",
        "{label:'傳統方案覆蓋度',data:trad,borderColor:'#ff6b6b',",
        "backgroundColor:'rgba(255,107,107,.1)',pointBackgroundColor:'#ff6b6b',borderWidth:2}]},",
        "options:{responsive:true,maintainAspectRatio:false,",
        "plugins:{legend:{labels:{color:'#8b949e',font:{size:11}}}},",
        "scales:{r:{angleLines:{color:'rgba(255,255,255,.1)'},grid:{color:'rgba(255,255,255,.1)'},",
        "pointLabels:{color:'#e6edf3',font:{size:11}},ticks:{display:false},min:0,max:10}}}});",
        "</script>",
        "</body></html>",
    ]
    return "\n".join(parts)



class SalesState(TypedDict):
    input: str
    plan: List[str]
    past_steps: Annotated[List[Tuple[str, str]], operator.add]
    response: str


class SalesPlan(BaseModel):
    """業務分析章節計畫"""
    steps: List[str] = Field(description="依序需要產出的分析章節名稱列表")


def sales_planner(state: SalesState):
    prompt = ChatPromptTemplate.from_messages([
        ("system", SALES_AGENT_SYSTEM),
        ("human",
         "請分析以下資料，決定最適合的分析章節順序。\n"
         "可選章節：" + "／".join(SALES_SECTIONS) + "\n"
         "請列出所有章節，依最佳分析邏輯排序。\n\n"
         "資料內容：\n{input}")
    ])
    planner = prompt | llm_4o.with_structured_output(SalesPlan)
    result = planner.invoke({"input": state["input"]})
    return {"plan": result.steps}


def sales_executor(state: SalesState):
    section = state["plan"][0]
    completed = "\n\n".join(
        f"### {s}\n{r}" for s, r in state["past_steps"]
    ) if state["past_steps"] else "（尚無已完成章節）"
    section_key = next((k for k in SALES_SECTION_FORMATS if k in section), None)
    format_hint = f"\n\n**格式要求：**\n{SALES_SECTION_FORMATS[section_key]}" if section_key else ""
    prompt = ChatPromptTemplate.from_messages([
        ("system", SALES_AGENT_SYSTEM),
        ("human",
         "原始資料：\n{input}\n\n"
         "已完成章節（供參考，保持一致性）：\n{completed}\n\n"
         "請現在產出「{section}」的完整內容。內容要具體、可操作、直接對業務員有用。{format_hint}")
    ])
    chain = prompt | llm_4o
    result = chain.invoke({
        "input": state["input"],
        "completed": completed,
        "section": section,
        "format_hint": format_hint,
    })
    return {"past_steps": [(section, result.content)]}


def sales_replanner(state: SalesState):
    remaining = state["plan"][1:]
    if not remaining:
        full_output = "\n\n---\n\n".join(
            f"## {section}\n\n{content}"
            for section, content in state["past_steps"]
        )
        return {"response": full_output}
    return {"plan": remaining}


def sales_should_end(state: SalesState):
    return "end" if state.get("response") else "continue"


def build_sales_graph():
    wf = StateGraph(SalesState)
    wf.add_node("planner", sales_planner)
    wf.add_node("executor", sales_executor)
    wf.add_node("re_planner", sales_replanner)
    wf.set_entry_point("planner")
    wf.add_edge("planner", "executor")
    wf.add_edge("executor", "re_planner")
    wf.add_conditional_edges("re_planner", sales_should_end, {"continue": "executor", "end": END})
    return wf.compile()


sales_graph = build_sales_graph()


def run_sales_analysis(file_list, user_context: str, user_prompt: str = ""):
    parts = []
    if file_list:
        file_text = extract_files_text(file_list)
        if file_text.strip():
            parts.append(file_text)
    if user_context and user_context.strip():
        parts.append(f"補充背景資訊：\n{user_context.strip()}")
    if user_prompt and user_prompt.strip():
        parts.append(f"使用者額外指示：\n{user_prompt.strip()}")

    text = "\n\n---\n\n".join(parts)
    if not text.strip():
        yield "⚠️ 請上傳附件或輸入資料後再送出。"
        return

    output = ""
    plan_shown = False

    for event in sales_graph.stream({"input": text}, {"recursion_limit": 40}):
        for node_name, value in event.items():
            if node_name == "planner" and "plan" in value and not plan_shown:
                plan_shown = True
                output = "### 📋 分析章節規劃\n" + "\n".join(
                    f"{i+1}. {s}" for i, s in enumerate(value["plan"])
                ) + "\n\n---\n\n*逐章節分析中……*\n\n"
                yield output
            elif node_name == "executor" and "past_steps" in value:
                for section, content in value["past_steps"]:
                    output = output.replace("*逐章節分析中……*\n\n", "")
                    output += f"## {section}\n\n{content}\n\n---\n\n*逐章節分析中……*\n\n"
                    yield output
            elif node_name == "re_planner" and value.get("response"):
                yield value["response"]


def generate_sales_dashboard_html(analysis_content: str):
    if not analysis_content or "逐章節分析中" in analysis_content or analysis_content.startswith("*送出"):
        return None
    data = _extract_dashboard_json(analysis_content)
    html_content = _render_dashboard_html(data)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".html", mode="w", encoding="utf-8")
    tmp.write(html_content)
    tmp.close()
    return tmp.name


def docx_to_dashboard_html(file_obj):
    """Extract text from a .docx file and render it as an interactive HTML dashboard."""
    if file_obj is None:
        return None
    from docx import Document as _DocxDocument
    doc = _DocxDocument(file_obj.name)
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    # Also extract tables
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                paragraphs.append(" | ".join(cells))
    text = "\n".join(paragraphs)
    if not text.strip():
        return None
    data = _extract_dashboard_json(text)
    html_content = _render_dashboard_html(data)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".html", mode="w", encoding="utf-8")
    tmp.write(html_content)
    tmp.close()
    return tmp.name


# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — 數據分析Agent（業務提案戰情室）(Plan-Execute架構)
# ══════════════════════════════════════════════════════════════════════════════

DATA_AGENT_SYSTEM = """
你是一位資深業務戰情分析師與資料科學顧問，名稱為「數據分析Agent」。
你的任務是協助業務即時判斷客戶狀態、成交機會、提案風險、決策鏈、追蹤優先順序與下一步策略，
建立一個可用於主管簡報與業務日常追蹤的「業務提案戰情室」分析報告。

## 核心目標
整合資料證據、客戶洞察、風險判斷、決策鏈、提案策略與情境模擬，
協助業務判斷：
- 客戶目前卡在哪個環節
- 成交機會與主要阻力
- 不同提案策略的優劣與話術
- 風險、ROI、時程與決策壓力的變化
- 下一步該補什麼資料、該說服誰、該何時追蹤、該傳什麼訊息

## 核心體驗
- 一眼掌握客戶目前卡關位置
- 快速判斷成交機會與主要阻力
- 切換不同提案策略並比較結果
- 模擬風險、ROI、時程與決策壓力變化
- 產出可直接用於客戶追蹤的話術與行動表

## 分析原則
- 每個判斷都要連回業務行動，不只是描述現象
- 每個判斷都要標示所依據的資料線索
- 成交機率、ROI、風險等級一律採「相對評分」，不得假裝為精確預測
- 資料不足時，明確列出待補數字與待確認條件，不得憑空捏造
- 策略模擬需清楚標示為「策略推估」
- 語氣專業、精簡、具主管簡報質感，避免學術化贅字

輸出語言：繁體中文。
"""

DATA_SECTIONS = [
    "戰情總覽",
    "客戶輪廓",
    "需求痛點",
    "決策鏈",
    "風險地圖",
    "策略模擬",
    "ROI情境",
    "行動追蹤",
    "證據資料",
]

DATA_SECTION_FORMATS = {
    "戰情總覽": """\
請用以下格式輸出：
| 判斷項目 | 內容 |
|---|---|
| 客戶／案子名稱 |  |
| 目前決策階段 |  |
| 成交機會（相對評分 0-100） |  |
| 風險等級（相對評分 0-100） |  |
| 目前最大成交機會 |  |
| 目前最大風險 |  |
| 建議下一步 |  |

最後列出「主管簡報重點」3-5條，每條一句話，適合投影片使用。""",
    "客戶輪廓": """\
請說明：
- **產業與公司背景**
- **公司規模／營運概況**
- **目前現況**（與本次提案相關的營運狀態）
- **對本次提案的態度與訊號**
若資訊不足，請標示「需補充」。""",
    "需求痛點": """\
請用以下表格格式輸出：
| 痛點 | 嚴重程度（1-10） | 對客戶的影響 | 資料依據 |
|---|---|---|---|
最後說明：最優先需要解決的痛點與理由。""",
    "決策鏈": """\
請識別所有關鍵利害關係人，每位格式如下：

**[姓名或代稱] / [職稱]**
- 角色類型：Champion（內部倡導者）/ Blocker（阻礙者）/ Gatekeeper（把關者）/ Influencer（影響者）/ Decision Maker（決策者）
- 影響力（1-10）
- 目前支持度（1-10，10為完全支持）
- 說服重點：[如何針對此人調整策略，1-2句]

最後列出：影響成交最關鍵的人與理由。""",
    "風險地圖": """\
請用以下表格格式輸出：
| 風險 | 等級（高/中/低） | 類別（價格/時程/技術/人員/決策） | 緩解措施 | 資料依據 |
|---|---|---|---|---|
最後說明：目前最需要立即處理的風險。""",
    "策略模擬": """\
請模擬三種提案策略，每種策略需包含：適合情境、成交機會（相對評分）、主要風險、建議話術（可直接使用的一段話）、下一步行動。
所有結果請標示為「策略推估」。

**策略一：保守試點型**（先小規模驗證，降低客戶疑慮）

**策略二：快速導入型**（強調效率與時效，加快推進速度）

**策略三：主管決策型**（直接訴求高層價值與決策效益）

最後給出：根據本次分析，最推薦哪個策略及理由。""",
    "ROI情境": """\
請模擬三種 ROI 情境（保守效益／一般效益／積極效益），每種需包含：
可能節省成本（每年，新台幣萬元）、品質改善價值、客訴下降價值、回收期估算（月）、需要確認的關鍵數字。
請標示為「策略推估」，並列出計算所依據的假設。""",
    "行動追蹤": """\
請輸出：
**追蹤優先順序模擬**
- 最該先補的資料
- 最該先說服的角色
- 最適合的追蹤時間
- 最合適的下一封訊息（可直接使用的訊息草稿）

**行動項目清單**
| 行動項目 | 負責人 | 建議時間 |
|---|---|---|""",
    "證據資料": """\
請列出支持以上判斷的關鍵資料線索，每條包含：資料摘要、對應章節結論、原始資料來源。
最後列出「待補資料清單」，說明資訊不足處與建議補充問題。""",
}


class DataState(TypedDict):
    input: str
    plan: List[str]
    past_steps: Annotated[List[Tuple[str, str]], operator.add]
    response: str


class DataPlan(BaseModel):
    """業務提案戰情室章節計畫"""
    steps: List[str] = Field(description="依序需要產出的分析章節名稱列表")


def data_planner(state: DataState):
    prompt = ChatPromptTemplate.from_messages([
        ("system", DATA_AGENT_SYSTEM),
        ("human",
         "請分析以下資料，決定最適合的戰情室分析章節順序。\n"
         "可選章節：" + "／".join(DATA_SECTIONS) + "\n"
         "請列出所有章節，依最佳分析邏輯排序。\n\n"
         "資料內容：\n{input}")
    ])
    planner = prompt | llm_4o.with_structured_output(DataPlan)
    result = planner.invoke({"input": state["input"]})
    return {"plan": result.steps}


def data_executor(state: DataState):
    section = state["plan"][0]
    completed = "\n\n".join(
        f"### {s}\n{r}" for s, r in state["past_steps"]
    ) if state["past_steps"] else "（尚無已完成章節）"
    section_key = next((k for k in DATA_SECTION_FORMATS if k in section), None)
    format_hint = f"\n\n**格式要求：**\n{DATA_SECTION_FORMATS[section_key]}" if section_key else ""
    prompt = ChatPromptTemplate.from_messages([
        ("system", DATA_AGENT_SYSTEM),
        ("human",
         "原始資料：\n{input}\n\n"
         "已完成章節（供參考，保持一致性）：\n{completed}\n\n"
         "請現在產出「{section}」的完整內容。內容要具體、可操作、直接對業務員有用。{format_hint}")
    ])
    chain = prompt | llm_4o
    result = chain.invoke({
        "input": state["input"],
        "completed": completed,
        "section": section,
        "format_hint": format_hint,
    })
    return {"past_steps": [(section, result.content)]}


def data_replanner(state: DataState):
    remaining = state["plan"][1:]
    if not remaining:
        full_output = "\n\n---\n\n".join(
            f"## {section}\n\n{content}"
            for section, content in state["past_steps"]
        )
        return {"response": full_output}
    return {"plan": remaining}


def data_should_end(state: DataState):
    return "end" if state.get("response") else "continue"


def build_data_graph():
    wf = StateGraph(DataState)
    wf.add_node("planner", data_planner)
    wf.add_node("executor", data_executor)
    wf.add_node("re_planner", data_replanner)
    wf.set_entry_point("planner")
    wf.add_edge("planner", "executor")
    wf.add_edge("executor", "re_planner")
    wf.add_conditional_edges("re_planner", data_should_end, {"continue": "executor", "end": END})
    return wf.compile()


data_graph = build_data_graph()


def run_data_analysis(file_list, user_context: str, user_prompt: str = ""):
    parts = []
    if file_list:
        file_text = extract_files_text(file_list)
        if file_text.strip():
            parts.append(file_text)
    if user_context and user_context.strip():
        parts.append(f"補充背景資訊：\n{user_context.strip()}")
    if user_prompt and user_prompt.strip():
        parts.append(f"使用者額外指示：\n{user_prompt.strip()}")

    text = "\n\n---\n\n".join(parts)
    if not text.strip():
        yield "⚠️ 請上傳附件或輸入資料後再送出。"
        return

    output = ""
    plan_shown = False

    for event in data_graph.stream({"input": text}, {"recursion_limit": 40}):
        for node_name, value in event.items():
            if node_name == "planner" and "plan" in value and not plan_shown:
                plan_shown = True
                output = "### 📋 戰情室章節規劃\n" + "\n".join(
                    f"{i+1}. {s}" for i, s in enumerate(value["plan"])
                ) + "\n\n---\n\n*逐章節分析中……*\n\n"
                yield output
            elif node_name == "executor" and "past_steps" in value:
                for section, content in value["past_steps"]:
                    output = output.replace("*逐章節分析中……*\n\n", "")
                    output += f"## {section}\n\n{content}\n\n---\n\n*逐章節分析中……*\n\n"
                    yield output
            elif node_name == "re_planner" and value.get("response"):
                yield value["response"]


# ── Tab 5 HTML war-room dashboard: Python-rendered template (responsive) ───

_WR_EXTRACT_SYSTEM = "你是資料結構化助理。只輸出符合要求的 JSON，不輸出任何說明。"

_WR_EXTRACT_PROMPT = """\
請從以下業務提案戰情室分析報告提取資料，輸出 JSON（繁體中文）。
所有評分一律為「相對評分」，數字不足時請合理估算並不得留空。

Schema：
{
  "hero": {
    "client_name": "客戶或案子名稱",
    "industry_title": "客戶產業／情境標題（15字以內）",
    "decision_stage": "目前決策階段（簡短）",
    "main_opportunity": "最大成交機會（一句話）",
    "top_risk": "最大風險（一句話）",
    "next_step": "建議下一步（一句話）"
  },
  "kpi": {
    "deal_score": 0到100整數（成交機會）,
    "risk_score": 0到100整數（風險等級）,
    "readiness_score": 0到100整數（導入準備度）,
    "roi_potential": 0到100整數（ROI潛力）
  },
  "exec_summary": ["主管簡報重點1", "重點2", "重點3"],
  "data_source": "資料來源或檔案名稱",
  "est_value": "High（戰略級客戶）| Medium（一般客戶）| Low（觀察中）",
  "customer_profile": {
    "industry": "產業別",
    "company_size": "公司規模",
    "current_situation": "目前現況",
    "background": "背景說明"
  },
  "pain_points": [
    {"title": "痛點名稱", "description": "說明", "severity": "高|中|低", "evidence_ref": "資料依據"}
  ],
  "decision_chain": [
    {"name": "姓名或代稱", "title": "職稱", "role_type": "Champion|Blocker|Gatekeeper|Influencer|Decision Maker",
     "role_label": "中文角色說明，如 內部倡導者 (Champion)", "influence": 1到10, "support_level": 1到10, "notes": "說服重點"}
  ],
  "risk_map": [
    {"risk": "風險名稱", "level": "高|中|低", "category": "價格|時程|技術|人員|決策", "mitigation": "緩解措施", "evidence_ref": "資料依據"}
  ],
  "radar_dimensions": ["5個維度名稱，如 價格接受度、時程壓力、技術整合度、決策層支持、現場配合度"],
  "radar_opportunity": [5個數字 1-10，代表成交機會強度],
  "radar_resistance": [5個數字 1-10，代表阻力強度],
  "strategy_modes": {
    "conservative": {"title": "保守試點型", "fit_scenario": "適合情境", "deal_chance": 0到100整數, "main_risk": "主要風險", "talk_track": "建議話術，可直接使用的一段話", "next_action": "下一步行動"},
    "fast": {"title": "快速導入型", "fit_scenario": "...", "deal_chance": 0到100整數, "main_risk": "...", "talk_track": "...", "next_action": "..."},
    "executive": {"title": "主管決策型", "fit_scenario": "...", "deal_chance": 0到100整數, "main_risk": "...", "talk_track": "...", "next_action": "..."}
  },
  "risk_factors": [
    {"id": "price", "label": "價格敏感度", "default": 0到100, "inverse": false, "data_needed_if_high": "價格敏感度偏高時，需要補強的資料"},
    {"id": "downtime", "label": "停線風險", "default": 0到100, "inverse": false, "data_needed_if_high": "..."},
    {"id": "complexity", "label": "導入麻煩程度", "default": 0到100, "inverse": false, "data_needed_if_high": "..."},
    {"id": "support", "label": "決策者支持度", "default": 0到100, "inverse": true, "data_needed_if_high": "決策者支持度偏低時，需要補強的資料"},
    {"id": "resistance", "label": "現場人員排斥程度", "default": 0到100, "inverse": false, "data_needed_if_high": "..."}
  ],
  "roi_scenarios": {
    "conservative": {"cost_saving": 數字（萬元/年）, "quality_value": 數字（萬元/年）, "complaint_value": 數字（萬元/年）, "payback_months": 數字, "need_confirm": ["待確認數字1", "待確認數字2"]},
    "normal": {"cost_saving": 數字, "quality_value": 數字, "complaint_value": 數字, "payback_months": 數字, "need_confirm": ["..."]},
    "aggressive": {"cost_saving": 數字, "quality_value": 數字, "complaint_value": 數字, "payback_months": 數字, "need_confirm": ["..."]}
  },
  "follow_up": {
    "top_data_needed": "最該先補的資料",
    "top_person": "最該先說服的角色",
    "best_timing": "最適合的追蹤時間",
    "next_message": "最合適的下一封訊息草稿"
  },
  "action_items": [
    {"task": "行動項目", "owner": "負責人", "due": "建議時間"}
  ],
  "evidence": [
    {"title": "證據標題", "summary": "一句話摘要", "detail": "完整內容或引用", "source": "資料來源"}
  ]
}

只輸出 JSON，不要任何說明。

---
分析報告：
{analysis}
"""

_WR_CSS = """
:root{--bg:#0a1220;--bg2:#0d1b2a;--card:#111f33;--card2:#16283f;--navy:#0f1b2e;
--steel:#64748b;--white:#f8fafc;--techblue:#38bdf8;--blue:#2563eb;
--orange:#f97316;--green:#22c55e;--red:#ef4444;
--text:#e6edf3;--muted:#93a2b8;--border:rgba(56,189,248,.15)}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{background:var(--bg);color:var(--text);font-family:'Noto Sans TC','Inter',sans-serif;font-size:14px;line-height:1.6}
img,canvas{max-width:100%;height:auto}
.wr-hero{position:relative;padding:56px 24px 40px;overflow:hidden;
background:radial-gradient(circle at 20% 20%,rgba(56,189,248,.18),transparent 45%),
radial-gradient(circle at 80% 0%,rgba(37,99,235,.22),transparent 50%),
linear-gradient(160deg,#0a1220 0%,#0d1b2a 55%,#111f33 100%);
border-bottom:1px solid var(--border)}
.wr-hero::before{content:'';position:absolute;inset:0;opacity:.5;pointer-events:none;
background-image:
  linear-gradient(rgba(148,163,184,.06) 1px,transparent 1px),
  linear-gradient(90deg,rgba(148,163,184,.06) 1px,transparent 1px);
background-size:36px 36px}
.wr-hero-inner{position:relative;max-width:1400px;margin:0 auto}
.wr-tag{display:inline-block;font-size:11px;letter-spacing:2px;color:var(--techblue);
text-transform:uppercase;border:1px solid var(--border);padding:4px 12px;border-radius:20px;margin-bottom:14px}
.wr-title{font-size:clamp(22px,3.4vw,34px);font-weight:800;color:var(--white);margin-bottom:6px}
.wr-sub{font-size:14px;color:var(--muted);margin-bottom:26px}
.wr-hero-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:22px}
.hero-card{background:rgba(17,31,51,.7);backdrop-filter:blur(6px);border:1px solid var(--border);
border-radius:12px;padding:16px}
.hero-card .lbl{font-size:11px;color:var(--muted);letter-spacing:1px;text-transform:uppercase;margin-bottom:6px}
.hero-card .val{font-size:15px;font-weight:700;color:var(--white);line-height:1.4}
.hero-card.opp .val{color:var(--green)}
.hero-card.risk .val{color:var(--orange)}
.kpi-row{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}
.kpi-card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:16px;text-align:center}
.kpi-num{font-size:2rem;font-weight:800;color:var(--techblue);line-height:1}
.kpi-lbl{font-size:11px;color:var(--muted);margin-top:6px;letter-spacing:.5px}
.kpi-card.risk .kpi-num{color:var(--orange)}
.kpi-card.opp .kpi-num{color:var(--green)}
.wr-nav{position:sticky;top:0;z-index:100;background:#0a1220;border-bottom:1px solid var(--border);
display:flex;gap:4px;overflow-x:auto;padding:0 16px}
.wr-nav-btn{flex-shrink:0;background:transparent;border:none;color:var(--muted);font-size:13px;
font-weight:600;padding:14px 16px;cursor:pointer;border-bottom:2px solid transparent;white-space:nowrap}
.wr-nav-btn:hover{color:var(--text)}
.wr-nav-btn.active{color:var(--techblue);border-bottom-color:var(--techblue)}
.wr-page{max-width:1400px;margin:0 auto;padding:24px 16px 60px}
.wr-panel{display:none}
.wr-panel.active{display:block}
.sec-title{font-size:16px;font-weight:700;color:var(--white);margin-bottom:14px;padding-bottom:8px;
border-bottom:2px solid var(--techblue);display:inline-block}
.grid2{display:grid;grid-template-columns:1.2fr 1fr;gap:18px}
.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
.card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:18px;margin-bottom:14px}
.brief-box{border:1px solid var(--techblue);background:rgba(56,189,248,.06);border-radius:12px;padding:18px}
.brief-title{font-size:13px;font-weight:700;color:var(--techblue);margin-bottom:10px}
.brief-item{display:flex;gap:8px;font-size:13px;color:var(--text);margin-bottom:8px;line-height:1.5}
.brief-dot{color:var(--techblue);flex-shrink:0}
.profile-row{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--border);font-size:13px}
.profile-row:last-child{border-bottom:none}
.profile-k{color:var(--muted)}
.profile-v{color:var(--text);font-weight:600;text-align:right;max-width:65%}
.pain-card{border-left:3px solid var(--orange);background:var(--card2);border-radius:8px;padding:12px 14px;margin-bottom:10px}
.pain-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:4px}
.pain-title{font-size:13px;font-weight:700;color:var(--text)}
.sev-badge{font-size:10px;padding:2px 9px;border-radius:20px;font-weight:700}
.sev-高{background:rgba(239,68,68,.18);color:var(--red)}
.sev-中{background:rgba(249,115,22,.18);color:var(--orange)}
.sev-低{background:rgba(34,197,94,.18);color:var(--green)}
.pain-desc{font-size:12px;color:var(--muted);line-height:1.5;margin-bottom:4px}
.pain-ref{font-size:11px;color:var(--steel);font-style:italic}
.stake-card{background:var(--card2);border-radius:10px;padding:14px;margin-bottom:10px;border:1px solid var(--border)}
.stake-head{display:flex;align-items:center;gap:10px;margin-bottom:8px}
.avatar{width:42px;height:42px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:15px;font-weight:700;flex-shrink:0;color:#fff}
.av-c{background:linear-gradient(135deg,#22c55e,#15803d)}
.av-b{background:linear-gradient(135deg,#ef4444,#b91c1c)}
.av-i{background:linear-gradient(135deg,#38bdf8,#0369a1)}
.av-d{background:linear-gradient(135deg,#f97316,#c2410c)}
.av-x{background:linear-gradient(135deg,#64748b,#334155)}
.stake-name{font-size:14px;font-weight:700;color:var(--text)}
.stake-ttl{font-size:11px;color:var(--muted)}
.badge{display:inline-block;padding:2px 10px;border-radius:20px;font-size:11px;font-weight:600;margin-bottom:8px}
.bC{background:#22c55e;color:#052e16}.bB{background:#ef4444;color:#fff}
.bI{background:#38bdf8;color:#03202e}.bD{background:#f97316;color:#2b0e00}.bX{background:#64748b;color:#fff}
.stake-meta{display:flex;gap:16px;margin-bottom:6px}
.meta-mini{font-size:11px;color:var(--muted)}
.meta-mini b{color:var(--techblue)}
.stake-notes{font-size:12px;color:var(--text);line-height:1.5}
.filter-row{display:flex;gap:8px;margin-bottom:14px;flex-wrap:wrap}
.filter-btn{font-size:12px;border:1px solid var(--border);background:var(--card2);color:var(--muted);
padding:6px 14px;border-radius:20px;cursor:pointer;font-weight:600}
.filter-btn.active{background:var(--techblue);color:#03202e;border-color:var(--techblue)}
.risk-card{background:var(--card2);border-radius:10px;padding:14px;margin-bottom:10px;border-left:3px solid var(--steel)}
.risk-card[data-level="高"]{border-left-color:var(--red)}
.risk-card[data-level="中"]{border-left-color:var(--orange)}
.risk-card[data-level="低"]{border-left-color:var(--green)}
.risk-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px}
.risk-name{font-size:13px;font-weight:700;color:var(--text)}
.risk-cat{font-size:10px;color:var(--muted);margin-bottom:6px}
.risk-mit{font-size:12px;color:var(--text);line-height:1.5;margin-bottom:4px}
.risk-ref{font-size:11px;color:var(--steel);font-style:italic}
.sim-card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:20px}
.strat-tabs,.roi-tabs{display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap}
.strat-btn,.roi-btn{flex:1;min-width:140px;background:var(--card2);border:1px solid var(--border);
color:var(--text);padding:12px 10px;border-radius:10px;cursor:pointer;font-size:13px;font-weight:700;text-align:center}
.strat-btn.active,.roi-btn.active{background:linear-gradient(135deg,var(--techblue),var(--blue));color:#03202e;border-color:var(--techblue)}
.strat-panel,.roi-panel{display:none}
.strat-panel.active,.roi-panel.active{display:block}
.strat-row{display:flex;justify-content:space-between;padding:9px 0;border-bottom:1px solid var(--border);font-size:13px;gap:16px}
.strat-row:last-child{border-bottom:none}
.strat-k{color:var(--muted);flex-shrink:0;width:110px}
.strat-v{color:var(--text);line-height:1.5}
.strat-tag{display:inline-block;font-size:10px;color:var(--steel);margin-top:2px}
.est-note{font-size:11px;color:var(--steel);font-style:italic;margin-top:10px}
.deal-pct{font-size:2.2rem;font-weight:800;color:var(--green)}
.risk-sim-grid{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-top:6px}
.slider-item{margin-bottom:16px}
.slider-top{display:flex;justify-content:space-between;font-size:12px;margin-bottom:6px}
.slider-top b{color:var(--techblue)}
input[type=range]{width:100%;accent-color:var(--techblue)}
.risk-out-card{background:var(--card2);border-radius:10px;padding:14px;margin-bottom:10px}
.risk-out-lbl{font-size:11px;color:var(--muted);margin-bottom:4px}
.risk-out-val{font-size:20px;font-weight:800}
.risk-out-val.ok{color:var(--green)}.risk-out-val.mid{color:var(--orange)}.risk-out-val.bad{color:var(--red)}
.need-list{font-size:12px;color:var(--text);line-height:1.7;margin-top:6px}
.need-list .need-item{display:none;padding:4px 8px;background:rgba(249,115,22,.08);border-radius:6px;margin-bottom:4px}
.need-list .need-item.show{display:block}
.order-list{font-size:12px;color:var(--text);line-height:2}
.order-list li{margin-left:18px}
.roi-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:14px}
.roi-num-card{background:var(--card2);border-radius:10px;padding:14px;text-align:center}
.roi-num{font-size:1.4rem;font-weight:800;color:var(--green)}
.roi-num.pay{color:var(--techblue)}
.roi-lbl{font-size:11px;color:var(--muted);margin-top:4px}
.roi-confirm{font-size:12px;color:var(--muted);line-height:1.6}
.roi-scale-row{display:flex;align-items:center;gap:12px;margin:14px 0;padding:12px;background:var(--card2);border-radius:10px}
.roi-scale-lbl{font-size:12px;color:var(--muted);white-space:nowrap}
.roi-scale-val{font-size:13px;font-weight:700;color:var(--techblue);white-space:nowrap}
.follow-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px}
.follow-card{background:var(--card2);border-radius:10px;padding:14px}
.follow-lbl{font-size:11px;color:var(--muted);margin-bottom:6px}
.follow-val{font-size:13px;font-weight:700;color:var(--text);line-height:1.5}
.recalc-btn{background:var(--techblue);color:#03202e;border:none;padding:8px 16px;border-radius:8px;
font-size:12px;font-weight:700;cursor:pointer;margin-bottom:14px}
.msg-box{background:var(--card2);border-left:3px solid var(--techblue);border-radius:8px;padding:12px 14px;font-size:13px;line-height:1.6}
.action-item{display:flex;align-items:center;gap:10px;padding:10px 0;border-bottom:1px solid var(--border)}
.action-item:last-child{border-bottom:none}
.action-item input{width:16px;height:16px;accent-color:var(--techblue)}
.action-task{font-size:13px;color:var(--text);flex:1}
.action-task.done{text-decoration:line-through;color:var(--steel)}
.action-meta{font-size:11px;color:var(--muted)}
.ev-card{background:var(--card2);border-radius:10px;margin-bottom:10px;border:1px solid var(--border);overflow:hidden;cursor:pointer}
.ev-head{display:flex;justify-content:space-between;align-items:center;padding:13px 16px}
.ev-title{font-size:13px;font-weight:700;color:var(--text)}
.ev-summary{font-size:12px;color:var(--muted);margin-top:2px}
.ev-arrow{color:var(--techblue);font-size:14px;transition:transform .2s;flex-shrink:0;margin-left:10px}
.ev-card.open .ev-arrow{transform:rotate(180deg)}
.ev-detail{max-height:0;overflow:hidden;transition:max-height .25s ease;padding:0 16px}
.ev-card.open .ev-detail{max-height:400px;padding:0 16px 14px}
.ev-detail-txt{font-size:12px;color:var(--text);line-height:1.6;border-top:1px solid var(--border);padding-top:10px}
.ev-source{font-size:11px;color:var(--steel);font-style:italic;margin-top:6px}
@media(max-width:1100px){
  .wr-hero-grid,.kpi-row{grid-template-columns:repeat(2,1fr)}
  .grid2,.grid3,.risk-sim-grid,.roi-grid,.follow-grid{grid-template-columns:1fr}
}
@media(max-width:600px){
  .wr-hero{padding:36px 14px 28px}
  .wr-page{padding:16px 10px 40px}
  .roi-grid{grid-template-columns:1fr 1fr}
}
"""


def _wr_role_cls(role_type: str):
    r = (role_type or "").lower()
    if "champion" in r or "倡導" in r:
        return "av-c", "bC"
    if any(x in r for x in ("blocker", "gatekeeper", "阻礙", "把關")):
        return "av-b", "bB"
    if "influencer" in r or "影響" in r:
        return "av-i", "bI"
    if "decision" in r or "決策" in r:
        return "av-d", "bD"
    return "av-x", "bX"


def _wr_render_exec_summary(items: list) -> str:
    items = items or ["（尚無足夠資料產出主管簡報重點）"]
    return "".join(
        f'<div class="brief-item"><span class="brief-dot">▸</span><span>{i}</span></div>'
        for i in items
    )


def _wr_render_profile(p: dict) -> str:
    p = p or {}
    rows = [
        ("產業別", p.get("industry", "—")),
        ("公司規模", p.get("company_size", "—")),
        ("目前現況", p.get("current_situation", "—")),
        ("背景說明", p.get("background", "—")),
    ]
    return "".join(
        f'<div class="profile-row"><span class="profile-k">{k}</span><span class="profile-v">{v}</span></div>'
        for k, v in rows
    )


def _wr_render_pain_points(items: list) -> str:
    if not items:
        return '<p style="color:var(--muted);font-size:12px">（未識別到明確痛點）</p>'
    out = []
    for p in items:
        sev = p.get("severity", "中")
        out.append(
            f'<div class="pain-card"><div class="pain-top">'
            f'<span class="pain-title">{p.get("title","")}</span>'
            f'<span class="sev-badge sev-{sev}">{sev}風險</span></div>'
            f'<div class="pain-desc">{p.get("description","")}</div>'
            f'<div class="pain-ref">依據：{p.get("evidence_ref","—")}</div></div>'
        )
    return "".join(out)


def _wr_render_decision_chain(items: list) -> str:
    if not items:
        return '<div class="stake-card"><p style="color:var(--muted)">（未識別到明確決策鏈成員）</p></div>'
    out = []
    for s in items:
        av, bv = _wr_role_cls(s.get("role_type", ""))
        out.append(
            f'<div class="stake-card"><div class="stake-head">'
            f'<div class="avatar {av}">{(s.get("name") or "?")[:1]}</div>'
            f'<div><div class="stake-name">{s.get("name","")}</div>'
            f'<div class="stake-ttl">{s.get("title","")}</div></div></div>'
            f'<span class="badge {bv}">{s.get("role_label", s.get("role_type",""))}</span>'
            f'<div class="stake-meta">'
            f'<span class="meta-mini">影響力 <b>{s.get("influence",5)}/10</b></span>'
            f'<span class="meta-mini">支持度 <b>{s.get("support_level",5)}/10</b></span></div>'
            f'<div class="stake-notes">{s.get("notes","")}</div></div>'
        )
    return "".join(out)


def _wr_render_risk_map(items: list) -> str:
    if not items:
        return '<p style="color:var(--muted);font-size:12px">（未識別到明確風險）</p>'
    out = []
    for r in items:
        lvl = r.get("level", "中")
        out.append(
            f'<div class="risk-card" data-level="{lvl}">'
            f'<div class="risk-top"><span class="risk-name">{r.get("risk","")}</span>'
            f'<span class="sev-badge sev-{lvl}">{lvl}</span></div>'
            f'<div class="risk-cat">類別：{r.get("category","—")}</div>'
            f'<div class="risk-mit">緩解措施：{r.get("mitigation","—")}</div>'
            f'<div class="risk-ref">依據：{r.get("evidence_ref","—")}</div></div>'
        )
    return "".join(out)


def _wr_render_strategies(modes: dict) -> str:
    modes = modes or {}
    order = [("conservative", "保守試點型"), ("fast", "快速導入型"), ("executive", "主管決策型")]
    btns, panels = [], []
    for i, (key, default_title) in enumerate(order):
        m = modes.get(key, {})
        active = " active" if i == 0 else ""
        btns.append(
            f'<button class="strat-btn{active}" data-strat="{key}">{m.get("title", default_title)}</button>'
        )
        panels.append(
            f'<div class="strat-panel{active}" data-strat-panel="{key}">'
            f'<div class="deal-pct">{m.get("deal_chance", 50)}%</div>'
            f'<div class="strat-tag">預估成交機會（策略推估）</div>'
            f'<div class="strat-row"><span class="strat-k">適合情境</span><span class="strat-v">{m.get("fit_scenario","—")}</span></div>'
            f'<div class="strat-row"><span class="strat-k">主要風險</span><span class="strat-v">{m.get("main_risk","—")}</span></div>'
            f'<div class="strat-row"><span class="strat-k">建議話術</span><span class="strat-v">{m.get("talk_track","—")}</span></div>'
            f'<div class="strat-row"><span class="strat-k">下一步行動</span><span class="strat-v">{m.get("next_action","—")}</span></div>'
            f'<div class="est-note">＊以上為策略推估，依現有資料與風險判斷估算</div></div>'
        )
    return "".join(btns), "".join(panels)


def _wr_render_risk_factors(factors: list) -> str:
    if not factors:
        factors = [
            {"id": "price", "label": "價格敏感度", "default": 50, "inverse": False, "data_needed_if_high": "需補充：客戶預算上限與比價對象"},
            {"id": "downtime", "label": "停線風險", "default": 40, "inverse": False, "data_needed_if_high": "需補充：可容忍停機時間"},
            {"id": "complexity", "label": "導入麻煩程度", "default": 45, "inverse": False, "data_needed_if_high": "需補充：現有系統整合細節"},
            {"id": "support", "label": "決策者支持度", "default": 55, "inverse": True, "data_needed_if_high": "需補充：決策者關切重點"},
            {"id": "resistance", "label": "現場人員排斥程度", "default": 40, "inverse": False, "data_needed_if_high": "需補充：現場人員教育訓練規劃"},
        ]
    sliders, needs = [], []
    for f in factors:
        sliders.append(
            f'<div class="slider-item">'
            f'<div class="slider-top"><span>{f.get("label","")}</span><b class="slider-val" data-val-for="{f.get("id","")}">{f.get("default",50)}</b></div>'
            f'<input type="range" min="0" max="100" value="{f.get("default",50)}" '
            f'class="risk-slider" data-id="{f.get("id","")}" data-inverse="{"1" if f.get("inverse") else "0"}" '
            f'data-label="{f.get("label","")}"></div>'
        )
        needs.append(
            f'<div class="need-item" id="need-{f.get("id","")}">⚠ {f.get("data_needed_if_high","")}</div>'
        )
    return "".join(sliders), "".join(needs)


def _wr_render_roi(scenarios: dict) -> str:
    scenarios = scenarios or {}
    order = [("conservative", "保守效益"), ("normal", "一般效益"), ("aggressive", "積極效益")]
    btns, panels = [], []
    for i, (key, default_title) in enumerate(order):
        s = scenarios.get(key, {})
        active = " active" if i == 0 else ""
        btns.append(f'<button class="roi-btn{active}" data-roi="{key}">{default_title}</button>')
        confirm = "".join(f"<li>{c}</li>" for c in s.get("need_confirm", [])) or "<li>—</li>"
        panels.append(
            f'<div class="roi-panel{active}" data-roi-panel="{key}">'
            f'<div class="roi-grid">'
            f'<div class="roi-num-card"><div class="roi-num roi-cost" data-base="{s.get("cost_saving",0)}">{s.get("cost_saving",0)}萬</div><div class="roi-lbl">可能節省成本／年</div></div>'
            f'<div class="roi-num-card"><div class="roi-num roi-quality" data-base="{s.get("quality_value",0)}">{s.get("quality_value",0)}萬</div><div class="roi-lbl">品質改善價值</div></div>'
            f'<div class="roi-num-card"><div class="roi-num roi-complaint" data-base="{s.get("complaint_value",0)}">{s.get("complaint_value",0)}萬</div><div class="roi-lbl">客訴下降價值</div></div>'
            f'<div class="roi-num-card"><div class="roi-num pay roi-payback" data-base="{s.get("payback_months",12)}">{s.get("payback_months",12)}個月</div><div class="roi-lbl">回收期估算</div></div>'
            f'</div><div class="roi-confirm"><b style="color:var(--muted)">需要確認的數字：</b><ul style="margin-left:16px">{confirm}</ul></div>'
            f'<div class="est-note">＊以上為策略推估，實際效益依客戶場域驗證為準</div></div>'
        )
    return "".join(btns), "".join(panels)


def _wr_render_action_items(items: list) -> str:
    if not items:
        return '<p style="color:var(--muted);font-size:12px">（尚無行動項目）</p>'
    out = []
    for a in items:
        out.append(
            f'<div class="action-item"><input type="checkbox" class="action-check">'
            f'<span class="action-task">{a.get("task","")}</span>'
            f'<span class="action-meta">{a.get("owner","")}｜{a.get("due","")}</span></div>'
        )
    return "".join(out)


def _wr_render_evidence(items: list) -> str:
    if not items:
        return '<p style="color:var(--muted);font-size:12px">（尚無證據資料）</p>'
    out = []
    for e in items:
        out.append(
            f'<div class="ev-card"><div class="ev-head">'
            f'<div><div class="ev-title">{e.get("title","")}</div>'
            f'<div class="ev-summary">{e.get("summary","")}</div></div>'
            f'<span class="ev-arrow">▾</span></div>'
            f'<div class="ev-detail"><div class="ev-detail-txt">{e.get("detail","")}'
            f'<div class="ev-source">來源：{e.get("source","—")}</div></div></div></div>'
        )
    return "".join(out)


def _extract_wr_dashboard_json(analysis: str) -> dict:
    import json as _j
    try:
        resp = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": _WR_EXTRACT_SYSTEM},
                {"role": "user", "content": _WR_EXTRACT_PROMPT.format(analysis=analysis[:12000])},
            ],
            response_format={"type": "json_object"},
            max_tokens=3000,
            temperature=0,
        )
        return _j.loads(resp.choices[0].message.content)
    except Exception:
        return {}


def _render_wr_dashboard_html(data: dict) -> str:
    import json as _j
    hero = data.get("hero", {})
    kpi = data.get("kpi", {})
    client_name = hero.get("client_name", "目標客戶")
    industry_title = hero.get("industry_title", "業務提案戰情室")
    decision_stage = hero.get("decision_stage", "評估中")
    data_source = data.get("data_source", "業務分析資料")
    est_value = data.get("est_value", "Medium（一般客戶）")

    dims = data.get("radar_dimensions", ["價格接受度", "時程壓力", "技術整合度", "決策層支持", "現場配合度"])
    r_opp = data.get("radar_opportunity", [6, 6, 6, 6, 6])
    r_res = data.get("radar_resistance", [5, 5, 5, 5, 5])
    n = max(len(dims), len(r_opp), len(r_res))
    dims = (dims + ["—"] * n)[:n]
    r_opp = (r_opp + [5] * n)[:n]
    r_res = (r_res + [5] * n)[:n]

    exec_html = _wr_render_exec_summary(data.get("exec_summary", []))
    profile_html = _wr_render_profile(data.get("customer_profile", {}))
    pain_html = _wr_render_pain_points(data.get("pain_points", []))
    chain_html = _wr_render_decision_chain(data.get("decision_chain", []))
    risk_html = _wr_render_risk_map(data.get("risk_map", []))
    strat_btns, strat_panels = _wr_render_strategies(data.get("strategy_modes", {}))
    slider_html, need_html = _wr_render_risk_factors(data.get("risk_factors", []))
    roi_btns, roi_panels = _wr_render_roi(data.get("roi_scenarios", {}))
    action_html = _wr_render_action_items(data.get("action_items", []))
    evidence_html = _wr_render_evidence(data.get("evidence", []))

    fu = data.get("follow_up", {})

    tabs = [
        ("overview", "戰情總覽"), ("profile", "客戶輪廓"), ("pain", "需求痛點"),
        ("chain", "決策鏈"), ("risk", "風險地圖"), ("strategy", "策略模擬"),
        ("roi", "ROI情境"), ("action", "行動追蹤"), ("evidence", "證據資料"),
    ]
    nav_html = "".join(
        f'<button class="wr-nav-btn{" active" if i==0 else ""}" data-tab="{k}">{label}</button>'
        for i, (k, label) in enumerate(tabs)
    )

    parts = [
        "<!DOCTYPE html>", "<html lang='zh-TW'>", "<head>",
        '<meta charset="UTF-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
        "<title>業務提案戰情室</title>",
        '<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@300;400;500;700'
        '&family=Inter:wght@300;400;500;700&display=swap" rel="stylesheet">',
        '<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>',
        f"<style>{_WR_CSS}</style>", "</head>", "<body>",
        # ── Hero ──
        '<section class="wr-hero"><div class="wr-hero-inner">',
        '<span class="wr-tag">War Room ｜ 業務提案戰情室</span>',
        f'<div class="wr-title">{industry_title}｜{client_name}</div>',
        f'<div class="wr-sub">目前決策階段：{decision_stage}　｜　基於「{data_source}」之戰情分析　｜　案子評級：{est_value}</div>',
        '<div class="wr-hero-grid">',
        f'<div class="hero-card opp"><div class="lbl">主要成交機會</div><div class="val">{hero.get("main_opportunity","—")}</div></div>',
        f'<div class="hero-card risk"><div class="lbl">最大風險</div><div class="val">{hero.get("top_risk","—")}</div></div>',
        f'<div class="hero-card"><div class="lbl">下一步建議</div><div class="val">{hero.get("next_step","—")}</div></div>',
        f'<div class="hero-card"><div class="lbl">決策階段</div><div class="val">{decision_stage}</div></div>',
        '</div>',
        '<div class="kpi-row">',
        f'<div class="kpi-card opp"><div class="kpi-num">{kpi.get("deal_score",50)}</div><div class="kpi-lbl">成交機會分數</div></div>',
        f'<div class="kpi-card risk"><div class="kpi-num">{kpi.get("risk_score",50)}</div><div class="kpi-lbl">風險等級分數</div></div>',
        f'<div class="kpi-card"><div class="kpi-num">{kpi.get("readiness_score",50)}</div><div class="kpi-lbl">導入準備度</div></div>',
        f'<div class="kpi-card"><div class="kpi-num">{kpi.get("roi_potential",50)}</div><div class="kpi-lbl">ROI 潛力分數</div></div>',
        '</div></div></section>',
        # ── Tabs nav ──
        f'<nav class="wr-nav">{nav_html}</nav>',
        '<div class="wr-page">',
        # 戰情總覽
        '<div class="wr-panel active" data-panel="overview"><div class="grid2">',
        '<div><div class="sec-title">成交機會雷達</div><div class="card">'
        '<div style="position:relative;height:280px"><canvas id="radarChart"></canvas></div></div></div>',
        f'<div><div class="sec-title">主管簡報重點</div><div class="brief-box">{exec_html}</div></div>',
        '</div></div>',
        # 客戶輪廓
        f'<div class="wr-panel" data-panel="profile"><div class="sec-title">客戶輪廓</div><div class="card">{profile_html}</div></div>',
        # 需求痛點
        f'<div class="wr-panel" data-panel="pain"><div class="sec-title">需求痛點</div>{pain_html}</div>',
        # 決策鏈
        f'<div class="wr-panel" data-panel="chain"><div class="sec-title">決策鏈分析</div>{chain_html}</div>',
        # 風險地圖
        '<div class="wr-panel" data-panel="risk">',
        '<div class="sec-title">風險與阻力地圖</div>',
        '<div class="filter-row">'
        '<button class="filter-btn active" data-filter="全部">全部</button>'
        '<button class="filter-btn" data-filter="高">高風險</button>'
        '<button class="filter-btn" data-filter="中">中風險</button>'
        '<button class="filter-btn" data-filter="低">低風險</button></div>',
        f'<div id="risk-cards">{risk_html}</div>',
        '<div class="sec-title" style="margin-top:22px">風險調整模擬</div>',
        '<div class="sim-card"><div class="risk-sim-grid">',
        f'<div>{slider_html}</div>',
        '<div>'
        '<div class="risk-out-card"><div class="risk-out-lbl">風險等級變化（策略推估）</div>'
        '<div class="risk-out-val" id="risk-out-level">中</div></div>'
        '<div class="risk-out-card"><div class="risk-out-lbl">成交阻力變化（策略推估）</div>'
        '<div class="risk-out-val" id="risk-out-resist">中</div></div>'
        '<div class="risk-out-card"><div class="risk-out-lbl">需要補強的資料</div>'
        f'<div class="need-list" id="need-list">{need_html}</div></div>'
        '<div class="risk-out-card"><div class="risk-out-lbl">建議處理順序</div>'
        '<ol class="order-list" id="order-list"></ol></div>'
        '</div></div></div></div>',
        # 策略模擬
        '<div class="wr-panel" data-panel="strategy">',
        '<div class="sec-title">提案策略模擬</div>',
        '<div class="sim-card">',
        f'<div class="strat-tabs">{strat_btns}</div>',
        f'{strat_panels}',
        '</div></div>',
        # ROI情境
        '<div class="wr-panel" data-panel="roi">',
        '<div class="sec-title">ROI 與導入效益估算</div>',
        '<div class="sim-card">',
        f'<div class="roi-tabs">{roi_btns}</div>',
        '<div class="roi-scale-row"><span class="roi-scale-lbl">導入規模調整</span>'
        '<input type="range" id="roi-scale" min="50" max="150" value="100" style="flex:1">'
        '<span class="roi-scale-val" id="roi-scale-val">100%</span></div>',
        f'{roi_panels}',
        '</div></div>',
        # 行動追蹤
        '<div class="wr-panel" data-panel="action">',
        '<div class="sec-title">追蹤優先順序模擬</div>',
        '<button class="recalc-btn" id="recalc-btn">🔄 依目前風險重新試算</button>',
        '<div class="follow-grid">',
        f'<div class="follow-card"><div class="follow-lbl">最該先補的資料</div><div class="follow-val" id="fu-data">{fu.get("top_data_needed","—")}</div></div>',
        f'<div class="follow-card"><div class="follow-lbl">最該先說服的角色</div><div class="follow-val" id="fu-person">{fu.get("top_person","—")}</div></div>',
        f'<div class="follow-card"><div class="follow-lbl">最適合的追蹤時間</div><div class="follow-val">{fu.get("best_timing","—")}</div></div>',
        '<div class="follow-card"><div class="follow-lbl">最合適的下一封訊息</div>'
        f'<div class="msg-box">{fu.get("next_message","—")}</div></div>',
        '</div>',
        '<div class="sec-title" style="margin-top:10px">行動項目清單</div>',
        f'<div class="card">{action_html}</div>',
        '</div>',
        # 證據資料
        f'<div class="wr-panel" data-panel="evidence"><div class="sec-title">資料證據區</div>{evidence_html}</div>',
        '</div>',  # end wr-page
        # ── JS ──
        "<script>",
        # tab switching
        "document.querySelectorAll('.wr-nav-btn').forEach(function(btn){",
        "btn.addEventListener('click',function(){",
        "document.querySelectorAll('.wr-nav-btn').forEach(function(b){b.classList.remove('active')});",
        "document.querySelectorAll('.wr-panel').forEach(function(p){p.classList.remove('active')});",
        "btn.classList.add('active');",
        "document.querySelector('.wr-panel[data-panel=\"'+btn.dataset.tab+'\"]').classList.add('active');",
        "window.scrollTo({top:0,behavior:'smooth'});});});",
        # risk level filter
        "document.querySelectorAll('.filter-btn').forEach(function(btn){",
        "btn.addEventListener('click',function(){",
        "document.querySelectorAll('.filter-btn').forEach(function(b){b.classList.remove('active')});",
        "btn.classList.add('active');",
        "var f=btn.dataset.filter;",
        "document.querySelectorAll('#risk-cards .risk-card').forEach(function(c){",
        "c.style.display=(f==='全部'||c.dataset.level===f)?'':'none';});});});",
        # evidence expand
        "document.querySelectorAll('.ev-card').forEach(function(c){",
        "c.querySelector('.ev-head').addEventListener('click',function(){c.classList.toggle('open');});});",
        # strategy switch
        "document.querySelectorAll('.strat-btn').forEach(function(btn){",
        "btn.addEventListener('click',function(){",
        "document.querySelectorAll('.strat-btn').forEach(function(b){b.classList.remove('active')});",
        "document.querySelectorAll('.strat-panel').forEach(function(p){p.classList.remove('active')});",
        "btn.classList.add('active');",
        "document.querySelector('.strat-panel[data-strat-panel=\"'+btn.dataset.strat+'\"]').classList.add('active');});});",
        # roi switch + scale
        "document.querySelectorAll('.roi-btn').forEach(function(btn){",
        "btn.addEventListener('click',function(){",
        "document.querySelectorAll('.roi-btn').forEach(function(b){b.classList.remove('active')});",
        "document.querySelectorAll('.roi-panel').forEach(function(p){p.classList.remove('active')});",
        "btn.classList.add('active');",
        "document.querySelector('.roi-panel[data-roi-panel=\"'+btn.dataset.roi+'\"]').classList.add('active');});});",
        "function fmtWan(v){return (Math.round(v*10)/10)+'萬';}",
        "function applyRoiScale(){",
        "var scale=parseInt(document.getElementById('roi-scale').value)/100;",
        "document.getElementById('roi-scale-val').textContent=Math.round(scale*100)+'%';",
        "document.querySelectorAll('.roi-cost,.roi-quality,.roi-complaint').forEach(function(el){",
        "var base=parseFloat(el.dataset.base||0);el.textContent=fmtWan(base*scale);});",
        "document.querySelectorAll('.roi-payback').forEach(function(el){",
        "var base=parseFloat(el.dataset.base||12);",
        "var val=scale>0?(base/scale):base;el.textContent=(Math.round(val*10)/10)+'個月';});}",
        "document.getElementById('roi-scale').addEventListener('input',applyRoiScale);",
        # risk sliders simulation
        "function recomputeRisk(){",
        "var total=0,n=0,resistTotal=0,resistN=0,contribs=[];",
        "document.querySelectorAll('.risk-slider').forEach(function(s){",
        "var v=parseInt(s.value);var inv=s.dataset.inverse==='1';",
        "var contrib=inv?(100-v):v;",
        "document.querySelector('.slider-val[data-val-for=\"'+s.dataset.id+'\"]').textContent=v;",
        "total+=contrib;n++;",
        "if(['price','complexity','resistance'].indexOf(s.dataset.id)>-1){resistTotal+=contrib;resistN++;}",
        "contribs.push({id:s.dataset.id,label:s.dataset.label,contrib:contrib});",
        "var need=document.getElementById('need-'+s.dataset.id);",
        "if(need){need.classList.toggle('show',contrib>=60);}});",
        "var riskAvg=n?Math.round(total/n):50;",
        "var resistAvg=resistN?Math.round(resistTotal/resistN):riskAvg;",
        "function lvl(v){return v>=67?'高':(v>=34?'中':'低');}",
        "function cls(v){return v>=67?'bad':(v>=34?'mid':'ok');}",
        "var lv=document.getElementById('risk-out-level');",
        "lv.textContent=lvl(riskAvg)+'（'+riskAvg+'分）';lv.className='risk-out-val '+cls(riskAvg);",
        "var rv=document.getElementById('risk-out-resist');",
        "rv.textContent=lvl(resistAvg)+'（'+resistAvg+'分）';rv.className='risk-out-val '+cls(resistAvg);",
        "contribs.sort(function(a,b){return b.contrib-a.contrib;});",
        "var ol=document.getElementById('order-list');",
        "ol.innerHTML=contribs.map(function(c){return '<li>'+c.label+'（'+c.contrib+'分）</li>';}).join('');",
        "return contribs;}",
        "document.querySelectorAll('.risk-slider').forEach(function(s){s.addEventListener('input',recomputeRisk);});",
        # follow-up recalc
        "document.getElementById('recalc-btn').addEventListener('click',function(){",
        "var contribs=recomputeRisk();",
        "if(contribs&&contribs.length){document.getElementById('fu-data').textContent=",
        "document.getElementById('need-'+contribs[0].id)?document.getElementById('need-'+contribs[0].id).textContent.replace('⚠ ',''):contribs[0].label;}",
        f"var chain={_j.dumps(data.get('decision_chain', []), ensure_ascii=False)};",
        "if(chain&&chain.length){",
        "chain.sort(function(a,b){return (a.support_level||5)-(b.support_level||5)||(b.influence||5)-(a.influence||5);});",
        "document.getElementById('fu-person').textContent=chain[0].name+'／'+chain[0].title;}});",
        # action item checkbox toggle
        "document.querySelectorAll('.action-check').forEach(function(cb){",
        "cb.addEventListener('change',function(){",
        "cb.closest('.action-item').querySelector('.action-task').classList.toggle('done',cb.checked);});});",
        "recomputeRisk();applyRoiScale();",
        # radar chart
        f"var dims={_j.dumps(dims, ensure_ascii=False)};",
        f"var opp={_j.dumps(r_opp)};",
        f"var res={_j.dumps(r_res)};",
        "new Chart(document.getElementById('radarChart'),{type:'radar',",
        "data:{labels:dims,datasets:[",
        "{label:'成交機會強度',data:opp,borderColor:'#22c55e',",
        "backgroundColor:'rgba(34,197,94,.15)',pointBackgroundColor:'#22c55e',borderWidth:2},",
        "{label:'阻力強度',data:res,borderColor:'#f97316',",
        "backgroundColor:'rgba(249,115,22,.1)',pointBackgroundColor:'#f97316',borderWidth:2}]},",
        "options:{responsive:true,maintainAspectRatio:false,",
        "plugins:{legend:{labels:{color:'#93a2b8',font:{size:11}}}},",
        "scales:{r:{angleLines:{color:'rgba(255,255,255,.1)'},grid:{color:'rgba(255,255,255,.1)'},",
        "pointLabels:{color:'#e6edf3',font:{size:11}},ticks:{display:false},min:0,max:10}}}});",
        "</script>",
        "</body></html>",
    ]
    return "\n".join(parts)


def generate_data_dashboard_html(analysis_content: str):
    if not analysis_content or "逐章節分析中" in analysis_content or analysis_content.startswith("*上傳"):
        return None
    data = _extract_wr_dashboard_json(analysis_content)
    html_content = _render_wr_dashboard_html(data)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".html", mode="w", encoding="utf-8")
    tmp.write(html_content)
    tmp.close()
    return tmp.name


def docx_to_wr_dashboard_html(file_obj):
    """Extract text from a .docx file and render it as an interactive 業務提案戰情室 HTML dashboard."""
    if file_obj is None:
        return None
    from docx import Document as _DocxDocument
    doc = _DocxDocument(file_obj.name)
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                paragraphs.append(" | ".join(cells))
    text = "\n".join(paragraphs)
    if not text.strip():
        return None
    data = _extract_wr_dashboard_json(text)
    html_content = _render_wr_dashboard_html(data)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".html", mode="w", encoding="utf-8")
    tmp.write(html_content)
    tmp.close()
    return tmp.name


# ══════════════════════════════════════════════════════════════════════════════
# Gradio UI
# ══════════════════════════════════════════════════════════════════════════════

with gr.Blocks(title="AI課程教材設計&客戶提案總監 (LangGraph)") as demo:

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
                user_prompt1 = gr.Textbox(
                    label="使用者提示（選填）",
                    placeholder="可輸入額外指示，例如：聚焦製造業主管受眾、強調實作活動、縮短篇幅……",
                    lines=3,
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
                    download_word_btn = gr.Button("📄 下載 Word", size="lg")
                with gr.Row():
                    download_file = gr.File(
                        label="HTML 檔案",
                        visible=False,
                        interactive=False,
                    )
                    download_word_file = gr.File(
                        label="Word 檔案",
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
            inputs=[materials_input, topic_dropdown, user_prompt1],
            outputs=[design_output],
        )
        clear_btn.click(
            fn=lambda: (None, "", "自動判斷", "",
                        "*送出資料後，Agent 將規劃章節並逐一生成，結果即時顯示於此……*",
                        gr.update(visible=False), gr.update(visible=False)),
            outputs=[file_upload, materials_input, topic_dropdown, user_prompt1,
                     design_output, download_file, download_word_file],
        )
        download_btn.click(
            fn=lambda content: (generate_html_file(content), gr.update(visible=True)),
            inputs=[design_output],
            outputs=[download_file, download_file],
        )
        download_word_btn.click(
            fn=lambda content: (generate_word_file(content), gr.update(visible=True)),
            inputs=[design_output],
            outputs=[download_word_file, download_word_file],
        )

    # ── Tab 2 ──────────────────────────────────────────────────────────────────
    with gr.Tab("📑 客戶提案總監Agent"):
        gr.Markdown(
            "# 客戶提案總監Agent\n"
            "整合型錄圖片、報價表、客戶需求與業務筆記，以 **Plan-Execute** 架構逐章節生成"
            "可直接交付給 B2B 製造業客戶的正式提案計畫書。"
        )

        with gr.Accordion("📂 上傳文件或圖表（選填）", open=False):
            gr.Markdown(
                "支援格式：**PDF、Word (.docx)、PowerPoint (.pptx)、"
                "Excel (.xlsx/.csv)、純文字 (.txt/.md/.json)、"
                "圖表圖片 (.png/.jpg/.jpeg/.gif/.webp/.svg)**\n\n"
                "上傳後將自動擷取內容並填入下方輸入框，可再手動補充。"
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

        with gr.Row():
            with gr.Column(scale=1):
                proposal_input = gr.Textbox(
                    label="提案素材（可直接貼上或由上傳自動填入）",
                    placeholder=(
                        "請貼上任何與提案相關的資料，例如：\n"
                        "・客戶背景與需求說明\n"
                        "・業務拜訪筆記\n"
                        "・產品功能與規格\n"
                        "・報價項目與金額\n"
                        "・提案初稿大綱"
                    ),
                    lines=12,
                )
                user_prompt2 = gr.Textbox(
                    label="使用者提示（選填）",
                    placeholder="可輸入額外指示，例如：強調PoC試點方案、聚焦品保主管受眾、縮短執行摘要……",
                    lines=3,
                )
                propose_btn = gr.Button("開始生成提案", variant="primary", size="lg")
                propose_clear_btn = gr.Button("清除", size="lg")
            with gr.Column(scale=2):
                proposal_output = gr.Markdown(
                    label="提案計畫書",
                    value="*送出資料後，Agent 將規劃提案章節並逐一生成，結果即時顯示於此……*",
                )
                with gr.Row():
                    proposal_html_btn = gr.Button("📥 下載 HTML", size="lg")
                    proposal_word_btn = gr.Button("📄 下載 Word", size="lg")
                with gr.Row():
                    proposal_download_html = gr.File(
                        label="HTML 檔案",
                        visible=False,
                        interactive=False,
                    )
                    proposal_download_word = gr.File(
                        label="Word 檔案",
                        visible=False,
                        interactive=False,
                    )

        gr.Examples(
            examples=[
                [
                    "客戶：台中某中型汽車零件製造商，約300人。\n"
                    "現況：廠內品檢仍靠人工目視，每班3名品檢員，月均漏檢率約2.3%，"
                    "客訴每月4-6件，退貨損失約15萬元。\n"
                    "需求：希望導入自動光學檢測（AOI）系統，預算約200-300萬，"
                    "希望能在Q3完成首條產線導入。\n"
                    "我方產品：工業級AOI視覺檢測系統，每套98萬，含安裝、教育訓練與一年保固。"
                ],
                [
                    "客戶：新竹科技廠，主要生產PCB電路板，客戶要求導入碳排追蹤系統。\n"
                    "痛點：目前沒有系統化碳排資料，面臨供應鏈稽核壓力，今年底前必須提交ESG報告。\n"
                    "我方方案：碳排管理SaaS平台，月費8萬，含資料收集模組、報告產生器與顧問輔導。\n"
                    "業務筆記：客戶採購主管希望先做3個月PoC，成效好再全廠擴展。"
                ],
            ],
            inputs=[proposal_input],
        )

        file_upload2.upload(
            fn=extract_files_text,
            inputs=[file_upload2],
            outputs=[proposal_input],
        )
        propose_btn.click(
            fn=run_proposal_design,
            inputs=[proposal_input, user_prompt2],
            outputs=[proposal_output],
        )
        propose_clear_btn.click(
            fn=lambda: (None, "", "",
                        "*送出資料後，Agent 將規劃提案章節並逐一生成，結果即時顯示於此……*",
                        gr.update(visible=False), gr.update(visible=False)),
            outputs=[file_upload2, proposal_input, user_prompt2, proposal_output,
                     proposal_download_html, proposal_download_word],
        )
        proposal_html_btn.click(
            fn=lambda content: (generate_html_file(content), gr.update(visible=True)),
            inputs=[proposal_output],
            outputs=[proposal_download_html, proposal_download_html],
        )
        proposal_word_btn.click(
            fn=lambda content: (generate_word_file(content), gr.update(visible=True)),
            inputs=[proposal_output],
            outputs=[proposal_download_word, proposal_download_word],
        )

    # ── Tab 3 ──────────────────────────────────────────────────────────────────
    with gr.Tab("🛍️ 商品圖片電商成長Agent"):
        gr.Markdown(
            "# Image to Commerce Decision Growth Agent\n"
            "上傳商品圖片，以 **Plan-Execute** 架構自動生成品牌策略、電商文案、"
            "社群內容、競品分析與高擴散內容設計。"
        )

        with gr.Row():
            img_upload3 = gr.File(
                label="📷 上傳商品圖片（必填，可選取多張）",
                file_types=[".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff"],
                file_count="multiple",
            )

        with gr.Accordion("📝 補充商品資訊（選填）", open=False):
            gr.Markdown(
                "可提供：品牌名稱、商品名稱、商品材質、商品尺寸、售價區間、"
                "目標客群、想主打的賣點、銷售平台、品牌語氣、希望避開的詞語、"
                "競品或參考品牌、促銷活動資訊等。"
            )
            extra_info3 = gr.Textbox(
                label="商品補充資訊",
                placeholder=(
                    "品牌名稱：\n"
                    "商品名稱：\n"
                    "商品材質：\n"
                    "售價區間：\n"
                    "目標客群：\n"
                    "主打賣點：\n"
                    "銷售平台：\n"
                    "品牌語氣：\n"
                    "其他備注："
                ),
                lines=10,
            )

        user_prompt3 = gr.Textbox(
            label="使用者提示（選填）",
            placeholder="可輸入額外指示，例如：只產出 Instagram 和小紅書文案、強調送禮情境、精簡版輸出……",
            lines=3,
        )

        with gr.Row():
            commerce_btn = gr.Button("開始分析商品圖片", variant="primary", size="lg")
            commerce_clear_btn = gr.Button("清除", size="lg")

        commerce_output = gr.Markdown(
            label="商品電商成長分析結果",
            value="*上傳商品圖片後，Agent 將規劃分析章節並逐一生成，結果即時顯示於此……*",
        )

        with gr.Row():
            commerce_html_btn = gr.Button("📥 下載 HTML", size="lg")
            commerce_word_btn = gr.Button("📄 下載 Word", size="lg")
        with gr.Row():
            commerce_download_html = gr.File(
                label="HTML 檔案", visible=False, interactive=False
            )
            commerce_download_word = gr.File(
                label="Word 檔案", visible=False, interactive=False
            )

        commerce_btn.click(
            fn=run_commerce_analysis,
            inputs=[img_upload3, extra_info3, user_prompt3],
            outputs=[commerce_output],
        )
        commerce_clear_btn.click(
            fn=lambda: (None, "", "",
                        "*上傳商品圖片後，Agent 將規劃分析章節並逐一生成，結果即時顯示於此……*",
                        gr.update(visible=False), gr.update(visible=False)),
            outputs=[img_upload3, extra_info3, user_prompt3, commerce_output,
                     commerce_download_html, commerce_download_word],
        )
        commerce_html_btn.click(
            fn=lambda content: (generate_html_file(content), gr.update(visible=True)),
            inputs=[commerce_output],
            outputs=[commerce_download_html, commerce_download_html],
        )
        commerce_word_btn.click(
            fn=lambda content: (generate_word_file(content), gr.update(visible=True)),
            inputs=[commerce_output],
            outputs=[commerce_download_word, commerce_download_word],
        )

    # ── Tab 4 ──────────────────────────────────────────────────────────────────
    with gr.Tab("📊 業務智能分析Agent"):
        gr.Markdown(
            "# 業務智能分析Agent Agent\n"
            "上傳客戶資料、報表、會議紀錄或任何附件，以 **Plan-Execute** 架構進行深度質性與量化分析，"
            "並可生成精緻商業風格的**互動式 HTML 儀表板**（含客戶輪廓、痛點偵測、策略模擬），協助精準提案。"
        )

        with gr.Accordion("📂 上傳附件（可選取多個檔案）", open=True):
            gr.Markdown(
                "支援格式：**PDF、Word (.docx)、PowerPoint (.pptx)、"
                "Excel (.xlsx/.csv)、純文字 (.txt/.md/.json)、"
                "圖表圖片 (.png/.jpg/.jpeg/.gif/.webp/.svg)**"
            )
            file_upload4 = gr.File(
                label="拖曳或點擊上傳（可選取多個檔案）",
                file_types=[
                    ".pdf", ".docx", ".pptx", ".xlsx", ".xls", ".csv",
                    ".txt", ".md", ".json",
                    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg",
                ],
                file_count="multiple",
            )

        with gr.Row():
            with gr.Column(scale=1):
                sales_context = gr.Textbox(
                    label="補充背景資訊（選填）",
                    placeholder=(
                        "可輸入任何補充資訊，例如：\n"
                        "・客戶名稱與產業\n"
                        "・我方產品／服務說明\n"
                        "・目前業務進度\n"
                        "・競爭對手資訊\n"
                        "・希望達成的目標"
                    ),
                    lines=8,
                )
                user_prompt4 = gr.Textbox(
                    label="使用者提示（選填）",
                    placeholder="可輸入額外指示，例如：聚焦製造業客戶、重點分析風險、精簡版輸出……",
                    lines=3,
                )
                sales_btn = gr.Button("🔍 開始深度分析", variant="primary", size="lg")
                sales_clear_btn = gr.Button("清除", size="lg")

            with gr.Column(scale=2):
                sales_output = gr.Markdown(
                    label="業務分析報告",
                    value="*上傳附件或輸入資料後，Agent 將規劃分析章節並逐一生成，結果即時顯示於此……*",
                )
                with gr.Row():
                    sales_word_btn = gr.Button("📄 下載分析報告 Word", size="lg")
                with gr.Row():
                    sales_download_word = gr.File(
                        label="Word 分析報告", visible=False, interactive=False
                    )

                gr.Markdown("---")
                gr.Markdown("### 📄 Word 直轉互動儀表板")
                gr.Markdown(
                    "上傳現有 Word 報告（.docx），直接轉換為互動 HTML 儀表板，"
                    "**無需重新分析**，速度更快。"
                )
                with gr.Row():
                    word_direct_upload = gr.File(
                        label="上傳 Word 檔案 (.docx)",
                        file_types=[".docx"],
                        file_count="single",
                        scale=2,
                    )
                    word_convert_btn = gr.Button(
                        "Word → 🎨 生成互動 HTML 儀表板", variant="secondary", size="lg", scale=1
                    )
                word_convert_download = gr.File(
                    label="轉換後的互動 HTML 儀表板", visible=False, interactive=False
                )

        sales_btn.click(
            fn=run_sales_analysis,
            inputs=[file_upload4, sales_context, user_prompt4],
            outputs=[sales_output],
        )
        sales_clear_btn.click(
            fn=lambda: (None, "", "",
                        "*上傳附件或輸入資料後，Agent 將規劃分析章節並逐一生成，結果即時顯示於此……*",
                        gr.update(visible=False)),
            outputs=[file_upload4, sales_context, user_prompt4, sales_output,
                     sales_download_word],
        )
        sales_word_btn.click(
            fn=lambda content: (generate_word_file(content), gr.update(visible=True)),
            inputs=[sales_output],
            outputs=[sales_download_word, sales_download_word],
        )
        word_convert_btn.click(
            fn=lambda f: (docx_to_dashboard_html(f), gr.update(visible=True)),
            inputs=[word_direct_upload],
            outputs=[word_convert_download, word_convert_download],
        )

    # ── Tab 5 ──────────────────────────────────────────────────────────────────
    with gr.Tab("📈 數據分析Agent"):
        gr.Markdown(
            "# 數據分析Agent\n"
            "上傳客戶資料、報表、會議紀錄或任何附件，以 **Plan-Execute** 架構建立**業務提案戰情室分析報告**，"
            "並可生成精緻攝影商業戰情室風格的**互動式 HTML 儀表板**"
            "（含客戶狀態、成交機會雷達、風險地圖、決策鏈、策略模擬、ROI 情境與追蹤行動），協助業務即時判斷推進方式。"
        )

        with gr.Accordion("📂 上傳附件（可選取多個檔案）", open=True):
            gr.Markdown(
                "支援格式：**PDF、Word (.docx)、PowerPoint (.pptx)、"
                "Excel (.xlsx/.csv)、純文字 (.txt/.md/.json)、"
                "圖表圖片 (.png/.jpg/.jpeg/.gif/.webp/.svg)**"
            )
            file_upload5 = gr.File(
                label="拖曳或點擊上傳（可選取多個檔案）",
                file_types=[
                    ".pdf", ".docx", ".pptx", ".xlsx", ".xls", ".csv",
                    ".txt", ".md", ".json",
                    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg",
                ],
                file_count="multiple",
            )

        with gr.Row():
            with gr.Column(scale=1):
                data_context = gr.Textbox(
                    label="補充背景資訊（選填）",
                    placeholder=(
                        "可輸入任何補充資訊，例如：\n"
                        "・客戶名稱與產業\n"
                        "・我方產品／服務說明\n"
                        "・目前決策階段與進度\n"
                        "・已知的決策鏈成員\n"
                        "・希望達成的目標"
                    ),
                    lines=8,
                )
                user_prompt5 = gr.Textbox(
                    label="使用者提示（選填）",
                    placeholder="可輸入額外指示，例如：聚焦風險地圖、加強 ROI 情境、精簡版輸出……",
                    lines=3,
                )
                data_btn = gr.Button("🔍 開始戰情分析", variant="primary", size="lg")
                data_clear_btn = gr.Button("清除", size="lg")

            with gr.Column(scale=2):
                data_output = gr.Markdown(
                    label="業務提案戰情室分析報告",
                    value="*上傳附件或輸入資料後，Agent 將規劃分析章節並逐一生成，結果即時顯示於此……*",
                )
                with gr.Row():
                    data_word_btn = gr.Button("📄 下載分析報告 Word", size="lg")
                with gr.Row():
                    data_download_word = gr.File(
                        label="Word 分析報告", visible=False, interactive=False
                    )

                gr.Markdown("---")
                gr.Markdown("### 📄 Word 直轉互動儀表板")
                gr.Markdown(
                    "上傳現有 Word 報告（.docx），直接轉換為互動 HTML 戰情室儀表板，"
                    "**無需重新分析**，速度更快。"
                )
                with gr.Row():
                    word_direct_upload5 = gr.File(
                        label="上傳 Word 檔案 (.docx)",
                        file_types=[".docx"],
                        file_count="single",
                        scale=2,
                    )
                    word_convert_btn5 = gr.Button(
                        "Word → 🎨 生成互動 HTML 儀表板", variant="secondary", size="lg", scale=1
                    )
                word_convert_download5 = gr.File(
                    label="轉換後的互動 HTML 戰情室儀表板", visible=False, interactive=False
                )

        data_btn.click(
            fn=run_data_analysis,
            inputs=[file_upload5, data_context, user_prompt5],
            outputs=[data_output],
        )
        data_clear_btn.click(
            fn=lambda: (None, "", "",
                        "*上傳附件或輸入資料後，Agent 將規劃分析章節並逐一生成，結果即時顯示於此……*",
                        gr.update(visible=False)),
            outputs=[file_upload5, data_context, user_prompt5, data_output,
                     data_download_word],
        )
        data_word_btn.click(
            fn=lambda content: (generate_word_file(content), gr.update(visible=True)),
            inputs=[data_output],
            outputs=[data_download_word, data_download_word],
        )
        word_convert_btn5.click(
            fn=lambda f: (docx_to_wr_dashboard_html(f), gr.update(visible=True)),
            inputs=[word_direct_upload5],
            outputs=[word_convert_download5, word_convert_download5],
        )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, mcp_server=False, theme=gr.themes.Soft())
