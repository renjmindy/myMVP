import os
from dotenv import load_dotenv
# Core replacement: using deepseek integration
from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from pydantic import BaseModel, Field
from langchain_classic import hub
from langchain.tools import tool

# 1. Load environment variables
load_dotenv()

# --- Define Pydantic models (corresponding to the Input Schema in the architecture diagram) ---

class ReverseStringArgs(BaseModel):
    text: str = Field(description="The text content that needs to be reversed")

class ConcatenateStringsArgs(BaseModel):
    a: str = Field(description="The first string")
    b: str = Field(description="The second string")

# --- Define tools using the @tool decorator ---

@tool()
def greet_user(name: str) -> str:
    """Greets the user by name."""
    return f"Hello, {name}!"

@tool(args_schema=ReverseStringArgs)
def reverse_string(text: str) -> str:
    """Reverses the given string."""
    return text[::-1]

@tool(args_schema=ConcatenateStringsArgs)
def concatenate_strings(a: str, b: str) -> str:
    """Concatenates two strings, a and b, together."""
    return a + b

# 2. Package the list of tools
tools = [greet_user, reverse_string, concatenate_strings]

# 3. Initialize the DeepSeek model
# DeepSeek has extremely high instruction-following for tool_calling
#llm = ChatDeepSeek(
#    model="deepseek-chat", 
#    temperature=0
#)
llm = ChatOpenAI(
    model="gpt-4o-mini",
    # base_url is optional here; defaults to https://api.openai.com/v1
)

# 4. Get the specialized Prompt template for tool calling from the Hub
prompt = hub.pull("hwchase17/openai-tools-agent")

# 5. Build the Agent logic
agent = create_tool_calling_agent(
    llm=llm,
    tools=tools,
    prompt=prompt,
)

# 6. Build the Agent Executor
agent_executor = AgentExecutor.from_agent_and_tools(
    agent=agent,
    tools=tools,
    verbose=True,               # Enable detailed logs to observe DeepSeek's Thought chain
    handle_parsing_errors=True, # Automatically fix minor formatting errors in model output
)

# 7. Execute interaction tests
print("\n--- OpenAI Decorator-based Agent Started ---")

# Test single parameter
res1 = agent_executor.invoke({"input": "Say hello to Mindy Jen"})
print("AI Response 1:", res1["output"])

# Test multiple parameters with Pydantic validation
res2 = agent_executor.invoke({"input": "Connect 'Open' and 'AI' together"})
print("AI Response 2:", res2["output"])

# Test combined logic
res3 = agent_executor.invoke({"input": "Reverse the string 'Agent', then greet the result"})
print("AI Response 3:", res3["output"], '\n')