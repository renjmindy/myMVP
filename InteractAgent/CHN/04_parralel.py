import os
from dotenv import load_dotenv
from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableParallel, RunnableLambda

# 1. Environment Preparation
load_dotenv()

# 2. Initialize DeepSeek
#model = ChatDeepSeek(model="deepseek-chat")
model = ChatOpenAI(
    model="gpt-4o-mini",
    # base_url is optional here; defaults to https://api.openai.com/v1
)

# 3. Base Prompt: Extract product features
prompt_template = ChatPromptTemplate.from_messages([
    ("system", "You are a senior product review expert."),
    ("human", "Please list the main features of the product {product_name}."),
])

# 4. Define Pros analysis logic (Functional definition, corresponding to Branch 1 in the diagram)
def analyze_pros(features):
    pros_template = ChatPromptTemplate.from_messages([
        ("system", "You are a senior product review expert."),
        ("human", "Based on the following features: {features}, please list the Pros of these features."),
    ])
    # Note: We return the formatted content here
    return pros_template.format_prompt(features=features)

# 5. Define Cons analysis logic (Functional definition, corresponding to Branch 2 in the diagram)
def analyze_cons(features):
    cons_template = ChatPromptTemplate.from_messages([
        ("system", "You are a senior product review expert."),
        ("human", "Based on the following features: {features}, please list the Cons of these features."),
    ])
    return cons_template.format_prompt(features=features)

# 6. Consolidation Logic (Fan-in)
def combine_pros_cons(pros, cons):
    return f"### ✅ Pros Analysis\n{pros}\n\n### ❌ Cons Analysis\n{cons}"

# 7. Build Branch Chains
# Each branch is an independent pipeline: Receive features -> Call DeepSeek -> Parse to string
pros_branch_chain = (
    RunnableLambda(lambda x: analyze_pros(x)) | model | StrOutputParser()
)

cons_branch_chain = (
    RunnableLambda(lambda x: analyze_cons(x)) | model | StrOutputParser()
)

# 8. Assemble the Main Chain (LCEL)
chain = (
    prompt_template
    | model
    | StrOutputParser()
    # Branching starts: Run two branches simultaneously (Fan-out)
    | RunnableParallel(branches={"pros": pros_branch_chain, "cons": cons_branch_chain})
    # Merging starts: Receive the resulting dictionary from the branches and process (Fan-in)
    | RunnableLambda(
        lambda x: combine_pros_cons(x["branches"]["pros"], x["branches"]["cons"])  # type: ignore
    )
)

# 9. Execution
print("\n--- OpenAI is performing multi-dimensional parallel analysis ---\n")
result = chain.invoke({"product_name": "iPhone 15 Pro"})

print(result, '\n')