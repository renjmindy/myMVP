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
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import os

load_dotenv()

# 1. Define State Structure
class AgentState(TypedDict):
    # Annotated with operator.add to allow list merging in the state
    messages: Annotated[Sequence[HumanMessage], operator.add]

# 2. Define Tools
# Use the @tool decorator to define a simple mock weather tool
@tool
def get_weather(city: str):
    """Get weather information for a specified city"""
    # Simulate a weather query here
    return f"The weather in {city} is sunny, with a temperature of 28 degrees."

tools = [get_weather]

# 3. Initialize the model and bind tools
#llm = ChatDeepSeek(model="deepseek-chat")
llm = ChatOpenAI(
    model="gpt-4o-mini",
    # base_url is optional here; defaults to https://api.openai.com/v1
)
# Bind tools to the model (use bind_tools instead of deprecated bind_functions)
llm_with_tools = llm.bind_tools(tools)

# 4. Define node functions
def agent_node(state: AgentState) -> AgentState:
    messages = state["messages"]
    # Invoke the LLM with bound tools
    response = llm_with_tools.invoke(messages)
    # Return the updated message list
    return {"messages": [response]}

# Create tool node (using the new ToolNode class)
tool_node = ToolNode(tools)

# 5. Build the Conditional Graph
workflow = StateGraph(AgentState)

workflow.add_node("agent", agent_node)
workflow.add_node("tools", tool_node)

# Set the entry point (use START instead of set_entry_point)
workflow.add_edge(START, "agent")

# Add conditional edges
# Logic: After the agent node executes, call tools_condition to decide if a tool call is needed
# If a tool call is required, move to the "tools" node
# Otherwise, end the process (END)
workflow.add_conditional_edges(
    "agent",
    tools_condition,
    {
        "tools": "tools",
        "__end__": END
    }
)

# After tool execution, control must return to the agent for summarization or the next decision
workflow.add_edge('tools', 'agent')

# Compile
app = workflow.compile()

# Helper function: Format and print node output
def format_node_output(step: int, node_name: str, data: dict) -> None:
    """Formats and prints node output to make terminal output more readable"""
    print(f"\n{'='*60}")
    print(f"Step {step}: Node [{node_name}]")
    print('='*60)
    
    if "messages" not in data:
        print("Data:")
        pprint(data, indent=2, width=100)
        return
    
    for i, msg in enumerate(data["messages"]):
        print(f"\n  Message {i+1} [{type(msg).__name__}]:")
        print(f"  {'-'*50}")
        
        # Print content (truncate long text)
        content = str(msg.content)
        if len(content) > 200:
            print(f"  Content: {content[:200]}...")
        else:
            print(f"  Content: {content}")
        
        # Print tool call information (if any)
        if hasattr(msg, 'tool_calls') and msg.tool_calls:
            print(f"\n  Tool Calls:")
            for tc in msg.tool_calls:
                tool_name = tc.get('name', 'unknown')
                tool_args = tc.get('args', {})
                print(f"    ├── Function: {tool_name}")
                print(f"    └── Args: {json.dumps(tool_args, ensure_ascii=False)}")
        
        # Print other useful attributes
        if hasattr(msg, 'name') and msg.name:
            print(f"  Name: {msg.name}")


# 7. Run Tests
print("="*60)
print("Starting 04-conditional-agent")
print("="*60)

# Test Scenario 1: Tool call required
print("\n" + "📊 Scenario 1: Asking about weather")
print("-"*60)
inputs = {"messages": [HumanMessage(content="How is the weather in San Jose today?")]}
step = 1
final_value = None

for output in app.stream(inputs):
    for key, value in output.items():
        format_node_output(step, key, value)
        final_value = value
        step += 1

if final_value and "messages" in final_value:
    print(f"\n🎯 Final Answer: {final_value['messages'][-1].content}")

# Test Scenario 2: Chitchat, no tool needed
print("\n\n" + "💬 Scenario 2: Chitchat")
print("-"*60)
inputs = {"messages": [HumanMessage(content="Hello, who are you?")]}
result = app.invoke(inputs)
print(f"\n  Input: Hello, who are you?")
print(f"  🎯 Final Answer: {result['messages'][-1].content}")

print("\n" + "="*60)
print("Execution Finished")
print("="*60)