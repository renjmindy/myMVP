from dotenv import load_dotenv
from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# 1. Environment Preparation
load_dotenv()

# 2. Component Initialization (Using your specified ChatDeepSeek method)
#model = ChatDeepSeek(model="deepseek-chat")
model = ChatOpenAI(
    model="gpt-4o-mini",
    # base_url is optional here; defaults to https://api.openai.com/v1
)
parser = StrOutputParser()

# 3. Define Prompt Template (Including multiple variables)
prompt_template = ChatPromptTemplate.from_messages([
    ("system", "You are a master of humor specialized in telling jokes about {topic}."),
    ("human", "Please tell me {joke_count} jokes."),
])

# 4. Construct the Chain (LCEL)
# This represents the data flow: Template | Model | Parser
chain = prompt_template | model | parser

# 5. Run the Chain
# When calling invoke, data automatically flows through all components, 
# ultimately returning the string content directly.
print("\n--- Generating results via OpenAI ---\n")
result = chain.invoke({"topic": "lawyers", "joke_count": 3})

print(result, '\n')