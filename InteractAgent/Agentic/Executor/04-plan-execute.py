from typing import List, Tuple, Annotated, TypedDict
import operator
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from langgraph.graph import END, StateGraph

# 1. 環境與模型初始化
load_dotenv()
llm = ChatOpenAI(model="gpt-4o", temperature=0.7)

# ── 課程教材設計Agent系統提示 ───────────────────────────────────────────────────
COURSE_AGENT_SYSTEM = """
你是「AI課程教材轉譯與受眾案例設計Agent」，一個專屬課程教材設計助理。

## 你的角色
你熟悉以下教學風格：先有趣，再理論，再實作。
你重視受眾痛點、實務案例、工作流程、AI工具操作、簡報呈現與課堂活動。
你的任務不是整理資料，而是根據使用者提供的資料，轉化成適合「企業與跨職能AI初學者」的課程案例、教材內容、實作活動、提示詞與簡報頁面。

## 確認受眾輪廓
這批學員多數已經聽過或使用過AI，但自評能力仍以新手與初階為主。
他們不是完全沒有動機，而是缺乏清楚的方法、範本、工作流程與實際操作經驗。
最有效的教學方式是從他們每天遇到的工作痛點切入。

**學員關鍵特徵：**
- 多數已有AI接觸經驗，但缺乏系統化方法；多數自評為新手或初階
- 主要需求：資料分析、文書整理、流程自動化、提案簡報、會議紀錄、行銷文案
- 產業以製造業為最大宗，也包含服務業、教育、資訊科技
- 職能：數據分析、業務、行銷、社群、主管、行政、教育訓練
- 常用文件：PPT、Excel、Word、企劃書、會議紀錄、社群貼文、報價單

## 我的教學風格
先用痛點或有趣案例開場 → 拆解背後概念 → 示範AI工具 → 學員自己操作。
每個概念都要能轉成案例、活動、提示詞或工作流程。

## 五大優先主題
1. AI資料整理與報告自動化
2. AI簡報與提案製作
3. 個人AI Agent與工作流程設計
4. AI行銷文案與社群內容工廠
5. AI會議紀錄與文書整理

## 案例設計規則
每個案例必須包含：案例名稱、適合職能、對應痛點、原始資料類型、AI協助方式、操作步驟、可使用提示詞、預期產出、教師講解重點、學員容易犯的錯、延伸應用。

## 限制
- 不要只摘要資料；不要寫成泛用AI課程
- 不要把學員當成完全不懂AI的人；不要過度技術導向
- 不要使用離企業工作太遠的案例
- 不要只給概念，要給案例、提示詞、活動與產出
- 資訊不足時先做合理假設並標示
"""

# 2. 定義狀態結構
class PlanExecuteState(TypedDict):
    input: str                                                      # 原始教材內容
    topic_focus: str                                                # 聚焦主題（可空）
    plan: List[str]                                                 # 待產出的章節列表
    past_steps: Annotated[List[Tuple[str, str]], operator.add]     # 已完成章節與內容
    response: str                                                   # 最終彙整輸出

# 3. 定義資料結構
class Plan(BaseModel):
    """教材轉譯章節計畫"""
    steps: List[str] = Field(description="依序需要產出的章節名稱列表（從八大章節中選取最適合的）")

class Response(BaseModel):
    """最終彙整回覆"""
    response: str

# 4. 定義節點邏輯

def planner_node(state: PlanExecuteState):
    """【規劃者】分析教材，決定需要產出哪些章節及順序"""
    topic_hint = f"\n聚焦主題：{state['topic_focus']}" if state.get("topic_focus") else ""
    prompt = ChatPromptTemplate.from_messages([
        ("system", COURSE_AGENT_SYSTEM),
        ("human",
         "請分析以下教材內容，決定最適合產出的章節順序。\n"
         "可選章節：一、這份資料適合怎麼教／二、教材轉譯表／三、企業現場案例設計／"
         "四、課堂實作活動／五、學員可直接使用的提示詞／六、教師講解稿／"
         "七、簡報頁面建議／八、作業或延伸任務\n"
         "請列出所有八個章節，依最佳教學邏輯排序。{topic_hint}\n\n"
         "教材內容：\n{input}")
    ])
    planner = prompt | llm.with_structured_output(Plan)
    result = planner.invoke({"input": state["input"], "topic_hint": topic_hint})
    return {"plan": result.steps}

def executor_node(state: PlanExecuteState):
    """【執行者】根據課程教材設計Agent規則，產出當前章節內容"""
    section = state["plan"][0]
    completed = "\n\n".join(
        f"### {s}\n{r}" for s, r in state["past_steps"]
    ) if state["past_steps"] else "（尚無已完成章節）"

    prompt = ChatPromptTemplate.from_messages([
        ("system", COURSE_AGENT_SYSTEM),
        ("human",
         "原始教材：\n{input}\n\n"
         "已完成章節（供參考，保持一致性）：\n{completed}\n\n"
         "請現在產出「{section}」的完整內容。"
         "嚴格依照該章節的格式要求（表格、講解稿、提示詞等），內容要具體、可直接使用。")
    ])
    chain = prompt | llm
    result = chain.invoke({
        "input": state["input"],
        "completed": completed,
        "section": section,
    })
    return {"past_steps": [(section, result.content)]}

def replanner_node(state: PlanExecuteState):
    """【重規劃者】檢查是否所有章節已完成；若是則彙整最終輸出"""
    remaining = state["plan"][1:]
    if not remaining:
        full_output = "\n\n---\n\n".join(
            f"## {section}\n\n{content}"
            for section, content in state["past_steps"]
        )
        return {"response": full_output}
    return {"plan": remaining}

# 5. 路由邏輯
def should_end(state: PlanExecuteState):
    return "end" if state.get("response") else "continue"

# 6. 格式化輸出
def format_node_output(step: int, node_name: str, data: dict) -> None:
    print(f"\n{'='*60}")
    print(f"Step {step}: 節點 [{node_name}]")
    print('='*60)

    if "plan" in data and data["plan"]:
        print(f"\n  📋 章節計畫:")
        print(f"  {'-'*50}")
        for i, s in enumerate(data["plan"], 1):
            print(f"    {i}. {s}")

    if "past_steps" in data and data["past_steps"]:
        print(f"\n  ✅ 已完成章節:")
        print(f"  {'-'*50}")
        for section, content in data["past_steps"]:
            print(f"    • {section}")
            preview = content[:150].replace("\n", " ")
            print(f"      {preview}{'...' if len(content) > 150 else ''}")

    if "response" in data and data["response"]:
        print(f"\n  🎯 最終彙整輸出:")
        print(f"  {'-'*50}")
        print(data["response"])

# 7. 構建圖
def build_plan_and_execute():
    workflow = StateGraph(PlanExecuteState)
    workflow.add_node("planner", planner_node)
    workflow.add_node("executor", executor_node)
    workflow.add_node("re_planner", replanner_node)
    workflow.set_entry_point("planner")
    workflow.add_edge("planner", "executor")
    workflow.add_edge("executor", "re_planner")
    workflow.add_conditional_edges(
        "re_planner",
        should_end,
        {"continue": "executor", "end": END}
    )
    return workflow.compile()

# 執行
if __name__ == "__main__":
    print("="*60)
    print("AI課程教材轉譯與受眾案例設計Agent — Plan-Execute工作流")
    print("="*60)

    # 替換為您的教材內容
    materials = (
        "我們公司每週要整理業務拜訪紀錄，從業務填寫的表單中，匯整成主管報告。"
        "目前流程是：業務填Google表單 → 行政複製到Excel → 主管手動整理成PPT。"
        "每週大約花3-4小時在這件事上，而且常常漏填或格式不一致。"
    )
    topic_focus = "AI資料整理與報告自動化"  # 可設為空字串讓規劃者自動判斷

    app = build_plan_and_execute()
    inputs = {"input": materials, "topic_focus": topic_focus}

    step = 1
    final_value = None

    for event in app.stream(inputs, {"recursion_limit": 30}):
        for key, value in event.items():
            format_node_output(step, key, value)
            final_value = value
            step += 1

    if final_value and final_value.get("response"):
        print(f"\n{'='*60}")
        print("✅ 教材轉譯完成!")
        print("="*60)

    print("\n" + "="*60)
    print("運行結束")
    print("="*60)
