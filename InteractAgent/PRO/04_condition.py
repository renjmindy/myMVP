import os
from dotenv import load_dotenv
from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

# 1. Load environment
load_dotenv()

# 2. Initialize DeepSeek
#model = ChatDeepSeek(model="deepseek-chat")
model = ChatOpenAI(
    model="gpt-4o-mini",
    # base_url is optional here; defaults to https://api.openai.com/v1
)

# 3. Template Factory Function (Formatting Logic D from the diagram)
def get_template(user_type):
    """
    Returns different prompt skeletons based on the user type.
    """
    if user_type == "technical":
        # Corresponds to: Direct and unambiguous + Standardized structure
        return ChatPromptTemplate.from_messages([
            ("system", "You are a senior architect. Please use professional terminology, focusing on underlying principles and performance optimization. Limit to 200 words."),
            ("human", "Please analyze this concept in depth: {concept}")
        ])
    else:
        # Corresponds to: Relevant background information + Simple terminology
        return ChatPromptTemplate.from_messages([
            ("system", "You are a friendly elementary school teacher. Please use metaphors and simple everyday vocabulary. Limit to 200 words."),
            ("human", "Please help me explain this concept: {concept}")
        ])

# 4. Simulated Application Logic
user_profile = "technical"  # Assume this profile is read from a database
concept_to_explain = "Quantum Entanglement"

# Dynamically retrieve the template
prompt_template = get_template(user_profile)

# 5. Execute invocation
print(f"\n--- Generating content for [{user_profile}] user ---\n")
chain = prompt_template | model
response = chain.invoke({"concept": concept_to_explain})

print(response.content, '\n')