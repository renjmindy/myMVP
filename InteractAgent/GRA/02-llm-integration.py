# file: 02-llm-integration.py

from langgraph.graph import StateGraph, START, END
from typing_extensions import TypedDict
from dotenv import load_dotenv
from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI

# Initialize environment variables and the model
load_dotenv()
#llm = ChatDeepSeek(model="deepseek-chat")
llm = ChatOpenAI(
    model="gpt-4o-mini",
    # base_url is optional here; defaults to https://api.openai.com/v1
)

# Define state type
class State(TypedDict):
    message: str

# Define Node 1: Calling the LLM
def agent_node(state: State) -> State:
    print(f"[Agent Node] Thinking about input: {state['message']}")
    response = llm.invoke(state["message"])
    # We only return the message content
    return {"message": response.content}

# Define Node 2: Simple output processing
def post_process_node(state: State) -> State:
    return {"message": f"Agent replied: {state['message']}"}

# Build the graph (using StateGraph instead of the deprecated Graph)
workflow = StateGraph(State)

workflow.add_node("agent", agent_node)
workflow.add_node("post_process", post_process_node)

workflow.add_edge(START, "agent")
workflow.add_edge("agent", "post_process")
workflow.add_edge("post_process", END)

app = workflow.compile()

# Run
print("--- Starting 02-llm-integration ---")
# Ask a question
user_input = "Please introduce yourself in one sentence."
result = app.invoke({"message": user_input})
print(f"Final Result: {result['message']}")
print("--- Execution Finished ---")