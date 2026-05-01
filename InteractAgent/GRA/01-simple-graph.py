# file: 01-simple-graph.py

from langgraph.graph import StateGraph, START, END
from typing_extensions import TypedDict

# 定义状态类型
class State(TypedDict):
    message: str

# 定义两个简单的节点函数
def function_1(state: State) -> State:
    return {"message": state["message"] + " Hello"}

def function_2(state: State) -> State:
    return {"message": state["message"] + " World"}

# 1. 定义一个图（使用 StateGraph 替代已废弃的 Graph）
workflow = StateGraph(State)

# 2. 添加节点
# 第一个参数是节点的名称，第二个参数是执行的函数
workflow.add_node("node_1", function_1)
workflow.add_node("node_2", function_2)

# 3. 添加边
# 定义节点之间的连接关系：START -> node_1 -> node_2 -> END
workflow.add_edge(START, "node_1")
workflow.add_edge("node_1", "node_2")
workflow.add_edge("node_2", END)

# 5. 编译图
app = workflow.compile()

# 6. 运行图
print("--- 开始运行 01-simple-graph ---")
result = app.invoke({"message": "LangGraph"})
print(f"最终结果: {result['message']}")
print("--- 运行结束 ---")
