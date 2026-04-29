import os
from dotenv import load_dotenv
from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# 1. Environment Loading
load_dotenv()
#model = ChatDeepSeek(model="deepseek-chat")
model = ChatOpenAI(
    model="gpt-4o-mini",
    # base_url is optional here; defaults to https://api.openai.com/v1
)

# 2. Define two completely different sub-chains (Expert vs. Beginner)

# Expert Chain: Focuses on rigor, terminology, and depth
expert_prompt = ChatPromptTemplate.from_template("You are a senior expert. Please explain using professional and detailed terminology: {input}")
expert_chain = expert_prompt | model | StrOutputParser()

# Beginner Chain: Focuses on intuition, metaphors, and accessibility
beginner_prompt = ChatPromptTemplate.from_template("You are a caring teacher. Please explain to a complete beginner using everyday metaphors: {input}")
beginner_chain = beginner_prompt | model | StrOutputParser()

# 3. Routing Logic: Select the Chain at the Python layer based on user info (Stages A & B in the diagram)
def get_chain_for_user(user_profile):
    if user_profile["expertise"] == "expert":
        print("--- Routing to: Expert Mode ---")
        return expert_chain
    else:
        print("--- Routing to: Beginner Mode ---")
        return beginner_chain

# 4. Execution Workflow
current_user = {"name": "Zhang San", "expertise": "expert"} # Simulated user profile
user_input = "What is a neural network?"

# Retrieve the matching chain and execute
chain = get_chain_for_user(current_user)
result = chain.invoke({"input": user_input})

print(result)