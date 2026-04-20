import os
from dotenv import load_dotenv
#from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

# 1. Load environment variables
load_dotenv()

# 2. Initialize DeepSeek model (using the specific package requested)
#model = ChatDeepSeek(model="deepseek-chat")
model = ChatOpenAI(
    model="gpt-4o-mini",
    # base_url is optional here; defaults to https://api.openai.com/v1
)

# --- Part 1: Simple String Template ---
print("\n----- Part 1: Simple Template Call -----\n")
template = "Please tell me a joke about {topic}."
prompt_template = ChatPromptTemplate.from_template(template)

# Format the Prompt
prompt = prompt_template.invoke({"topic": "puppies"})
# Print the formatted object
print(f"Generated Prompt: {prompt}\n")
# Call the model
result = model.invoke(prompt)
print(f"AI Response: {result.content}\n")


# --- Part 2: Multiple Placeholder Template ---
print("\n----- Part 2: Multiple Placeholder Template Call -----\n")
template_multiple = """You are a helpful assistant.
User: Please tell me a {adjective} short story about {animal}.
Assistant:"""
prompt_multiple = ChatPromptTemplate.from_template(template_multiple)

prompt = prompt_multiple.invoke({"adjective": "touching", "animal": "penguins"})
print(f"Generated Prompt: {prompt}\n")
result = model.invoke(prompt)
print(f"AI Response: {result.content}\n")


# --- Part 3: System and User Messages (Tuple Mode) ---
print("\n----- Part 3: System and User Messages (Tuple Mode) -----\n")
messages = [
    ("system", "You are a comedian specialized in telling jokes about {topic}."),
    ("human", "Please tell {joke_count} jokes."),
]
prompt_template = ChatPromptTemplate.from_messages(messages)

prompt = prompt_template.invoke({"topic": "programmers", "joke_count": 2})
print(f"Generated Prompt: {prompt}\n")
result = model.invoke(prompt)
print(f"AI Response: {result.content}\n")