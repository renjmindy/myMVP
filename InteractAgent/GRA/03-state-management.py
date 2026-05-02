# file: 03-state-management.py

from langgraph.graph import StateGraph, START, END
from typing_extensions import TypedDict
from dotenv import load_dotenv
from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI

load_dotenv()
#llm = ChatDeepSeek(model="deepseek-chat")
llm = ChatOpenAI(
    model="gpt-4o-mini",
    # base_url is optional here; defaults to https://api.openai.com/v1
)

# Define state type
class State(TypedDict):
    messages: list[str]

def extractor_node(state: State) -> State:
    """Extract city name from user input"""
    user_input = state["messages"][-1]
    prompt = f"Please extract the city name from the following sentence, returning only the city name and nothing else: '{user_input}'"
    city_name = llm.invoke(prompt).content
    print(f"[Extractor] Extracted city: {city_name}")
    # Append the extraction result to the state
    return {"messages": state["messages"] + [city_name]}

def weather_tool_node(state: State) -> State:
    """Simulate a weather query tool"""
    city_name = state["messages"][-1]
    # Simulated API return data
    mock_data = f"The weather in {city_name} today is sunny with a temperature of 25 degrees."
    print(f"[Tool] Query result: {mock_data}")
    return {"messages": state["messages"] + [mock_data]}

def responder_node(state: State) -> State:
    """Generate final response"""
    user_original_question = state["messages"][0]
    weather_info = state["messages"][-1]
    
    prompt = f"User's original question: '{user_original_question}'. Found weather information: '{weather_info}'. Please generate a friendly response based on this."
    final_response = llm.invoke(prompt).content
    return {"messages": state["messages"] + [final_response]}

# Build the graph (using StateGraph instead of the deprecated Graph)
workflow = StateGraph(State)

workflow.add_node("extractor", extractor_node)
workflow.add_node("weather_tool", weather_tool_node)
workflow.add_node("responder", responder_node)

workflow.add_edge(START, "extractor")
workflow.add_edge("extractor", "weather_tool")
workflow.add_edge("weather_tool", "responder")
workflow.add_edge("responder", END)

app = workflow.compile()

# Run
print("--- Starting 03-state-management ---")
# Note: The input format here must match the expectation of extractor_node (dictionary containing messages)
inputs = {"messages": ["How is the weather in San Jose today?"]}
result = app.invoke(inputs)
print(f"Final Result: {result['messages'][-1]}")
print("--- Execution Finished ---")