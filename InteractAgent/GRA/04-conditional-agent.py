# file: 04-conditional-agent.py

import json
from typing import TypedDict, Annotated, Sequence
import operator
from pprint import pprint
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import tool
from langchain_deepseek import ChatDeepSeek
from dotenv import load_dotenv
import os

load_dotenv()

# 1. 定义状态结构
class AgentState(TypedDict):
    messages: Annotated[Sequence[HumanMessage], operator.add]

# 2. 定义工具
# 使用 @tool 装饰器定义一个简单的模拟天气工具
@tool
def get_weather(city: str):
    """获取指定城市的天气信息"""
    # 这里模拟天气查询
    return f"{city}的天气是晴天，温度28度。"

tools = [get_weather]

# 3. 初始化模型并绑定工具
llm = ChatDeepSeek(model="deepseek-chat")
# 将工具绑定到模型（使用 bind_tools 替代 bind_functions）
llm_with_tools = llm.bind_tools(tools)

# 4. 定义节点函数
def agent_node(state: AgentState) -> AgentState:
    messages = state["messages"]
    # 调用绑定了工具的 LLM
    response = llm_with_tools.invoke(messages)
    # 返回更新后的消息列表
    return {"messages": [response]}

# 创建工具节点（使用新的 ToolNode）
tool_node = ToolNode(tools)

# 5. 构建条件图
workflow = StateGraph(AgentState)

workflow.add_node("agent", agent_node)
workflow.add_node("tools", tool_node)

# 设置入口（使用 START 替代 set_entry_point）
workflow.add_edge(START, "agent")

# 添加条件边
# 逻辑：agent 节点执行完后，调用 tools_condition 判断是否需要调用工具
# 如果需要调用工具，则进入 "tools" 节点
# 否则结束流程 (END)
workflow.add_conditional_edges(
    "agent",
    tools_condition,
    {
        "tools": "tools",
        "__end__": END
    }
)

# 工具执行完后，必须回到 agent 进行总结或下一步决策
workflow.add_edge('tools', 'agent')

# 编译
app = workflow.compile()

# 辅助函数：格式化打印节点输出
def format_node_output(step: int, node_name: str, data: dict) -> None:
    """格式化并打印节点输出，使终端输出更易读"""
    print(f"\n{'='*60}")
    print(f"Step {step}: 节点 [{node_name}]")
    print('='*60)
    
    if "messages" not in data:
        print("数据:")
        pprint(data, indent=2, width=100)
        return
    
    for i, msg in enumerate(data["messages"]):
        print(f"\n  消息 {i+1} [{type(msg).__name__}]:")
        print(f"  {'-'*50}")
        
        # 打印内容（截断长文本）
        content = str(msg.content)
        if len(content) > 200:
            print(f"  内容: {content[:200]}...")
        else:
            print(f"  内容: {content}")
        
        # 打印工具调用信息（如果有）
        if hasattr(msg, 'tool_calls') and msg.tool_calls:
            print(f"\n  工具调用:")
            for tc in msg.tool_calls:
                tool_name = tc.get('name', 'unknown')
                tool_args = tc.get('args', {})
                print(f"    ├── 函数: {tool_name}")
                print(f"    └── 参数: {json.dumps(tool_args, ensure_ascii=False)}")
        
        # 打印其他有用属性
        if hasattr(msg, 'name') and msg.name:
            print(f"  名称: {msg.name}")


# 7. 运行测试
print("="*60)
print("开始运行 04-conditional-agent")
print("="*60)

# 测试场景 1：需要调用工具
print("\n" + "📊 场景 1：询问天气")
print("-"*60)
inputs = {"messages": [HumanMessage(content="今天北京天气怎么样？")]}
step = 1
final_value = None

for output in app.stream(inputs):
    for key, value in output.items():
        format_node_output(step, key, value)
        final_value = value
        step += 1

if final_value and "messages" in final_value:
    print(f"\n🎯 最终回答: {final_value['messages'][-1].content}")

# 测试场景 2：闲聊，不需要工具
print("\n\n" + "💬 场景 2：闲聊")
print("-"*60)
inputs = {"messages": [HumanMessage(content="你好，你是谁？")]}
result = app.invoke(inputs)
print(f"\n  输入: 你好，你是谁？")
print(f"  🎯 最终回答: {result['messages'][-1].content}")

print("\n" + "="*60)
print("运行结束")
print("="*60)
