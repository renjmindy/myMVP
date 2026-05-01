import os
from dotenv import load_dotenv
# Import the latest DeepSeek integration
from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI
from langchain_classic import hub
from langchain_classic.agents import AgentExecutor, create_structured_chat_agent
from langchain_classic.memory import ConversationBufferMemory
from langchain_core.messages import SystemMessage
from langchain_core.tools import Tool

# 1. Load environment variables (Ensure DEEPSEEK_API_KEY is in your .env)
load_dotenv()

# --- Define Tools (Tools Logic) ---

def get_current_time(*args, **kwargs):
    """Returns the current time in H:MM AM/PM format."""
    import datetime
    return datetime.datetime.now().strftime("%I:%M %p")

def search_wikipedia(query):
    """Searches Wikipedia and returns a summary of the first result."""
    from wikipedia import summary
    try:
        # Limit to two sentences to keep it concise
        return summary(query, sentences=2)
    except Exception as e:
        return f"Could not find relevant information on Wikipedia. Error details: {str(e)}"

# 2. Package the toolset
tools = [
    Tool(
        name="Time",
        func=get_current_time,
        description="Very useful when you need to query the current real-time.",
    ),
    Tool(
        name="Wikipedia",
        func=search_wikipedia,
        description="Use when you need to look up encyclopedic knowledge such as people, places, scientific concepts, or historical events. Input should be a keyword or phrase.",
    ),
]

# 3. Initialize core components (The Brain)
# Using the DeepSeek-V3 model (deepseek-chat)
#llm = ChatDeepSeek(
#    model="deepseek-chat",
#    temperature=0,      # Set to 0 to ensure stability of structured output
#    max_tokens=2048
#)
llm = ChatOpenAI(
    model="gpt-4o-mini",
    # base_url is optional here; defaults to https://api.openai.com/v1
)

# Pull the Prompt specific to structured chat agents
# This Prompt requires the model to reply in JSON format to invoke tools
prompt = hub.pull("hwchase17/structured-chat-agent")

# 4. Configure the Memory unit
# chat_history corresponds to the placeholder in the Prompt
memory = ConversationBufferMemory(
    memory_key="chat_history", 
    return_messages=True
)

# 5. Build Agent logic
agent = create_structured_chat_agent(llm=llm, tools=tools, prompt=prompt)

# 6. Build the Executor
agent_executor = AgentExecutor.from_agent_and_tools(
    agent=agent,
    tools=tools,
    verbose=True,               # Enable detailed logs to observe DeepSeek's reasoning process
    memory=memory,              # Automatically associate conversation context
    handle_parsing_errors=True, # Automatically handle JSON format fine-tuning
)

# 7. Inject System Instructions
initial_message = "You are an AI assistant capable of using tools to answer questions. You can look up the time and Wikipedia."
memory.chat_memory.add_message(SystemMessage(content=initial_message))

# 8. Interaction loop
print("--- OpenAI Structured Agent is online (type 'exit' to quit) ---")

while True:
    user_input = input("\nUser: ")
    if user_input.lower() == "exit":
        break

    # Run Agent: It will automatically retrieve history from memory and store new replies in memory
    try:
        response = agent_executor.invoke({"input": user_input})
        print("\nBot:", response["output"], '\n')
    except Exception as e:
        print(f"\n⚠️ Execution error: {e} \n")