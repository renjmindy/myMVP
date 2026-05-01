import os
from typing import Type
from dotenv import load_dotenv

# Core Integration: DeepSeek Model
from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI
# Core Tool Classes
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from langchain_classic import hub
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent

# 1. Environment Configuration
load_dotenv()

# --- Define Tool Input Schemas ---

class SimpleSearchInput(BaseModel):
    query: str = Field(description="Search query statement, should be specific keywords or questions")

class MultiplyNumbersArgs(BaseModel):
    x: float = Field(description="The first multiplier")
    y: float = Field(description="The second multiplier")

# --- Define Custom Tools by inheriting from BaseTool ---

class SimpleSearchTool(BaseTool):
    name: str = "simple_search"
    description: str = "Used to answer questions about current events, news, or topics requiring an online search."
    args_schema: Type[BaseModel] = SimpleSearchInput

    def _run(self, query: str) -> str:
        """Execute search logic"""
        # Local import to improve startup speed
        from tavily import TavilyClient
        
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            return "Error: TAVILY_API_KEY is not configured."
            
        try:
            client = TavilyClient(api_key=api_key)
            results = client.search(query=query)
            return f"Search results for '{query}' are as follows:\n\n{results}\n"
        except Exception as e:
            return f"An error occurred during the search: {str(e)}"

class MultiplyNumbersTool(BaseTool):
    name: str = "multiply_numbers"
    description: str = "Used to perform multiplication of two numbers."
    args_schema: Type[BaseModel] = MultiplyNumbersArgs

    def _run(self, x: float, y: float) -> str:
        """Execute calculation logic"""
        result = x * y
        return f"The calculation result of {x} multiplied by {y} is {result}."

# 2. Instantiate tools and package them into a list
tools = [SimpleSearchTool(), MultiplyNumbersTool()]

# 3. Initialize DeepSeek Model (The Brain)
#llm = ChatDeepSeek(
#    model="deepseek-chat", 
#    temperature=0  # Ensures certainty in tool parameter generation
#)
llm = ChatOpenAI(
    model="gpt-4o-mini",
    # base_url is optional here; defaults to https://api.openai.com/v1
)

# 4. Retrieve Prompt template (Compatible with DeepSeek's Tool Calling format)
prompt = hub.pull("hwchase17/openai-tools-agent")

# 5. Build the Tool Calling Agent
agent = create_tool_calling_agent(
    llm=llm,
    tools=tools,
    prompt=prompt,
)

# 6. Build the Executor
agent_executor = AgentExecutor.from_agent_and_tools(
    agent=agent,
    tools=tools,
    verbose=True,               # Enable detailed logs to observe reasoning and calling processes
    handle_parsing_errors=True, # Error handling
)

# 7. Interaction Testing
print("\n--- OpenAI Class Inheritance version Agent is online ---")

# Test web search
print("\n[Test 1: Web Search]")
res1 = agent_executor.invoke({"input": "Search for the latest progress of Apple Intelligence"})
print("AI Response:", res1["output"])

# Test math calculation
print("\n[Test 2: Math Calculation]")
res2 = agent_executor.invoke({"input": "What is 12.5 multiplied by 8?"})
print("AI Response:", res2["output"], '\n')