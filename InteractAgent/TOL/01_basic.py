import os
from dotenv import load_dotenv
from langchain_classic import hub
from langchain_classic.agents import (
    AgentExecutor,
    create_react_agent,
)
from langchain_core.tools import Tool
# Import DeepSeek driver
from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI

# 1. Load environment variables
load_dotenv()

# 2. Define tool function
def get_current_time(*args, **kwargs):
    """Returns the current time in H:MM AM/PM format"""
    import datetime
    now = datetime.datetime.now()
    return now.strftime("%I:%M %p")

# 3. List of tools
tools = [
    Tool(
        name="Time",
        func=get_current_time,
        description="Useful when you need to know the current time",
    ),
]

# 4. Pull the ReAct prompt template from the Hub
prompt = hub.pull("hwchase17/react")

# 5. Core Improvement: Initialize the DeepSeek model
# Use the deepseek-chat model and set temperature to 0 to ensure stability in tool calling
#llm = ChatDeepSeek(
#    model="deepseek-chat", 
#    temperature=0
#)
llm = ChatOpenAI(
    model="gpt-4o-mini",
    # base_url is optional here; defaults to https://api.openai.com/v1
)

# 6. Create the ReAct Agent
agent = create_react_agent(
    llm=llm,
    tools=tools,
    prompt=prompt,
    stop_sequence=True,
)

# 7. Create the Agent Executor (verbose=True allows you to see the AI's thought process)
agent_executor = AgentExecutor.from_agent_and_tools(
    agent=agent,
    tools=tools,
    verbose=True,
    handle_parsing_errors=True # Recommended: handle parsing errors
)

# 8. Run test
print("\n")
print("--- Starting OpenAI Agent ---")
response = agent_executor.invoke({"input": "What time is it now?"})

# 9. Print results
print("\nFinal Answer:", response["output"], '\n')