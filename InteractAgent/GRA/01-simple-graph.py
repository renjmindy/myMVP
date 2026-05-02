# file: 01-simple-graph.py

from langgraph.graph import StateGraph, START, END
from typing_extensions import TypedDict

# Define state type
class State(TypedDict):
    message: str

# Define two simple node functions
def function_1(state: State) -> State:
    return {"message": state["message"] + " Hello"}

def function_2(state: State) -> State:
    return {"message": state["message"] + " World"}

# 1. Define a graph (use StateGraph instead of the deprecated Graph)
workflow = StateGraph(State)

# 2. Add nodes
# The first parameter is the node name, the second is the function to execute
workflow.add_node("node_1", function_1)
workflow.add_node("node_2", function_2)

# 3. Add edges
# Define the connection relationship between nodes: START -> node_1 -> node_2 -> END
workflow.add_edge(START, "node_1")
workflow.add_edge("node_1", "node_2")
workflow.add_edge("node_2", END)

# 5. Compile the graph
app = workflow.compile()

# 6. Run the graph
print("--- Starting 01-simple-graph ---")
result = app.invoke({"message": "LangGraph"})
print(f"Final Result: {result['message']}")
print("--- Execution Finished ---")