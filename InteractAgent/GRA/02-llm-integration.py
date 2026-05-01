# file: 02-llm-integration.py

from langgraph.graph import StateGraph, START, END
from typing_extensions import TypedDict
from dotenv import load_dotenv
from langchain_deepseek import ChatDeepSeek

# 初始化环境变量和模型
load_dotenv()
llm = ChatDeepSeek(model="deepseek-chat")

# 定义状态类型
class State(TypedDict):
    message: str

# 定义节点 1：调用 LLM
def agent_node(state: State) -> State:
    print(f"[Agent Node] 正在思考输入: {state['message']}")
    response = llm.invoke(state["message"])
    # 我们只返回消息内容
    return {"message": response.content}

# 定义节点 2：简单处理输出
def post_process_node(state: State) -> State:
    return {"message": f"Agent 回复说: {state['message']}"}

# 构建图（使用 StateGraph 替代已废弃的 Graph）
workflow = StateGraph(State)

workflow.add_node("agent", agent_node)
workflow.add_node("post_process", post_process_node)

workflow.add_edge(START, "agent")
workflow.add_edge("agent", "post_process")
workflow.add_edge("post_process", END)

app = workflow.compile()

# 运行
print("--- 开始运行 02-llm-integration ---")
# 我们问一个问题
user_input = "请用一句话介绍你自己。"
result = app.invoke({"message": user_input})
print(f"最终结果: {result['message']}")
print("--- 运行结束 ---")
