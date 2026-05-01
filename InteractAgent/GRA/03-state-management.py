# file: 03-state-management.py

from langgraph.graph import StateGraph, START, END
from typing_extensions import TypedDict
from dotenv import load_dotenv
from langchain_deepseek import ChatDeepSeek

load_dotenv()
llm = ChatDeepSeek(model="deepseek-chat")

# 定义状态类型
class State(TypedDict):
    messages: list[str]

def extractor_node(state: State) -> State:
    """从用户输入中提取城市名称"""
    user_input = state["messages"][-1]
    prompt = f"请从下面的句子中提取城市名称，只返回城市名，不要其他内容：'{user_input}'"
    city_name = llm.invoke(prompt).content
    print(f"[Extractor] 提取到的城市: {city_name}")
    # 将提取结果追加到状态中
    return {"messages": state["messages"] + [city_name]}

def weather_tool_node(state: State) -> State:
    """模拟天气查询工具"""
    city_name = state["messages"][-1]
    # 模拟 API 返回的数据
    mock_data = f"{city_name}今天天气晴朗，气温25度。"
    print(f"[Tool] 查询结果: {mock_data}")
    return {"messages": state["messages"] + [mock_data]}

def responder_node(state: State) -> State:
    """生成最终回复"""
    user_original_question = state["messages"][0]
    weather_info = state["messages"][-1]
    
    prompt = f"用户原始问题是：'{user_original_question}'。查到的天气信息是：'{weather_info}'。请据此生成友好的回复。"
    final_response = llm.invoke(prompt).content
    return {"messages": state["messages"] + [final_response]}

# 构建图（使用 StateGraph 替代已废弃的 Graph）
workflow = StateGraph(State)

workflow.add_node("extractor", extractor_node)
workflow.add_node("weather_tool", weather_tool_node)
workflow.add_node("responder", responder_node)

workflow.add_edge(START, "extractor")
workflow.add_edge("extractor", "weather_tool")
workflow.add_edge("weather_tool", "responder")
workflow.add_edge("responder", END)

app = workflow.compile()

# 运行
print("--- 开始运行 03-state-management ---")
# 注意：这里输入的格式需要符合 extract_node 的预期（字典包含 messages）
inputs = {"messages": ["今天北京天气怎么样？"]}
result = app.invoke(inputs)
print(f"最终结果: {result['messages'][-1]}")
print("--- 运行结束 ---")
