
from dotenv import load_dotenv
from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda

# 1. Load environment variables
load_dotenv()

# 2. Initialize DeepSeek model
#model = ChatDeepSeek(model="deepseek-chat")
model = ChatOpenAI(
    model="gpt-4o-mini",
    # base_url is optional here; defaults to https://api.openai.com/v1
)

# 3. Define Prompt Template
prompt_template = ChatPromptTemplate.from_messages(
    [
        ("system", "You are a master of humor specialized in telling jokes about {topic}."),
        ("human", "Please tell {joke_count} jokes."),
    ]
)

# 4. Define custom processing steps (using RunnableLambda)
# Step A: Convert output to uppercase (For Chinese, usually used for emphasis or English characters within the text)
uppercase_output = RunnableLambda(lambda x: x.upper())  # type: ignore

# Step B: Count characters and prepend it to the result
count_words = RunnableLambda(lambda x: f"Total Character Count: {len(x)}\n{'-'*20}\n{x}")  # type: ignore

# 5. Build the composite chain (LCEL)
# Data flow: Prompt -> Model -> Parser -> Uppercase Processing -> Word Count
chain = (
    prompt_template 
    | model 
    | StrOutputParser() 
    | uppercase_output 
    | count_words
)

# 6. Run the chain
print("\n--- OpenAI is processing and executing post-processing logic ---\n")
result = chain.invoke({"topic": "programmers", "joke_count": 1})

# 7. Output result
print(result, '\n')