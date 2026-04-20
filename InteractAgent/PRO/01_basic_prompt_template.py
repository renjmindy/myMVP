
from dotenv import load_dotenv
from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage

# Load environment variables (ensure DEEPSEEK_API_KEY is included)
load_dotenv()

# Initialize DeepSeek model
#model = ChatDeepSeek(model="deepseek-chat")
model = ChatOpenAI(
    model="gpt-4o-mini",
    # base_url is optional here; defaults to https://api.openai.com/v1
)

# --- Part 1: Creating ChatPromptTemplate using template strings ---
# Corresponds to the static text + dynamic variable structure in the diagram
template = "Please tell me a joke about {topic}."
prompt_template = ChatPromptTemplate.from_template(template)

print("\n----- Part 1: Simple Template -----\n")
prompt = prompt_template.invoke({"topic": "kittens"})
# We can pass the formatted prompt directly to the model
print(prompt, '\n')
response = model.invoke(prompt) 
print(response.content, '\n')


# --- Part 2: Multiple Placeholder Template ---
template_multiple = """You are a helpful assistant.
User: Please tell me a {adjective} story about {animal}.
Assistant:"""
prompt_multiple = ChatPromptTemplate.from_template(template_multiple)
prompt = prompt_multiple.invoke({"adjective": "funny", "animal": "pandas"})

print("\n----- Part 2: Multiple Placeholder Template -----\n")
print(prompt, '\n')
response = model.invoke(prompt)
print(response.content, '\n')


# --- Part 3: Using System and User Messages (Using Tuples) ---
# This is the most recommended approach in LangChain 1.0, as the structure is clear
messages = [
    ("system", "You are a comedian specialized in telling jokes about {topic}."),
    ("human", "Please tell {joke_count} jokes."),
]
prompt_template = ChatPromptTemplate.from_messages(messages)
prompt = prompt_template.invoke({"topic": "programmers", "joke_count": 2})

print("\n----- Part 3: System & User Messages (Tuple Mode) -----\n")
print(prompt, '\n')
response = model.invoke(prompt)
print(response.content, '\n')

# --- Advanced Supplement: Important notes on message types ---

# This approach is feasible (Hybrid Mode):
# But Note: The content in a HumanMessage object is static and will NOT be replaced by the dictionary in invoke
messages_work = [
    ("system", "You are a comedian specialized in telling jokes about {topic}."),
    HumanMessage(content="Please tell 3 jokes."), 
]
prompt_template_work = ChatPromptTemplate.from_messages(messages_work)
prompt_final = prompt_template_work.invoke({"topic": "chefs"})
print("\n----- Supplement: Hybrid Mode Result -----\n")
print(prompt_final, '\n')
response = model.invoke(prompt_final)
print(response.content, '\n')

# This approach is [NOT feasible] (as mentioned in your notes):
# Reason for error: Once a HumanMessage instance is created, its content becomes a fixed string.
# LangChain will not automatically parse {curly_braces} inside the object.
# If dynamic parsing is needed, you MUST use the tuple format ("human", "{var}").
"""
messages_not_work = [
    ("system", "You are a comedian specialized in {topic}."),
    HumanMessage(content="Tell {joke_count} jokes."), # This will error or output as-is without replacement
]
"""