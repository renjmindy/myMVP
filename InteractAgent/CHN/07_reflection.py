import os
from dotenv import load_dotenv
from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

load_dotenv()
#model = ChatDeepSeek(model="deepseek-chat")
model = ChatOpenAI(
    model="gpt-4o-mini",
    # base_url is optional here; defaults to https://api.openai.com/v1
)

# 1. Define the "Refinement Coach" Chain (Improvement Chain)
improvement_prompt = ChatPromptTemplate.from_template(
    "You are a senior editor. Here is the current content:\n{current}\n"
    "Please identify the weaknesses and rewrite a higher-quality version. Return the content directly."
)
improvement_chain = improvement_prompt | model | StrOutputParser()

# 2. Define the "Judge" Logic (is_good_enough)
def is_good_enough(content):
    """
    This can be a hard-coded rule or the judgment result of another AI model.
    Example: Requires content to contain "core competitiveness" and have a length > 50 characters.
    """
    has_keywords = "core competitiveness" in content
    is_long_enough = len(content) > 50
    return has_keywords and is_long_enough

# 3. Recursive Optimization Function (Refine Loop)
def refine_until_good(initial_topic):
    # Step 1: Generate initial draft
    print("--- Generating initial draft... ---")
    current = model.invoke(f"Write a business pitch about {initial_topic}. Around 200 words.").content
    
    attempts = 0
    max_retries = 3  # Safety guard to prevent infinite loops
    
    # Core loop logic
    while not is_good_enough(current) and attempts < max_retries:
        attempts += 1
        print(f"--- Quality not up to standard, performing refinement attempt #{attempts}... ---")
        
        # Feed the current version back into the chain for improvement
        current = improvement_chain.invoke({"current": current})
    
    return current

# 4. Execute Application
final_output = refine_until_good("AI Automated Marketing")
print("\n--- Final Qualified Content ---")
print(final_output)