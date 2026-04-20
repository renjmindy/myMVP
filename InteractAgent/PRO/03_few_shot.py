import os
from dotenv import load_dotenv
from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI
from langchain_core.prompts import FewShotPromptTemplate, PromptTemplate

# 1. Load environment
load_dotenv()

# 2. Initialize the model
#model = ChatDeepSeek(model="deepseek-chat")
model = ChatOpenAI(
    model="gpt-4o-mini",
    # base_url is optional here; defaults to https://api.openai.com/v1
)

# 3. Prepare example data (Specific Examples)
examples = [
    {"input": "Happy", "output": "Sad"},
    {"input": "Tall", "output": "Short"},
    {"input": "Cold", "output": "Hot"},
]

# 4. Configure the format for a single example (Standardized structure)
example_prompt = PromptTemplate(
    input_variables=["input", "output"], 
    template="Input: {input}\nOutput: {output}"
)

# 5. Construct the FewShotPromptTemplate
few_shot_template = FewShotPromptTemplate(
    examples=examples,                  # Inject examples
    example_prompt=example_prompt,       # Specify how examples are formatted
    prefix="Find the antonym for each of the following words:",  # Instructions
    suffix="Input: {adjective}\nOutput:", # Suffix (part to be filled)
    input_variables=["adjective"]        # Final user variable
)

# 6. Format and invoke
final_prompt = few_shot_template.format(adjective="Bright")

print("\n----- Constructed Final Prompt -----\n")
print(final_prompt)

print("\n----- OpenAI Response -----")
# Note: few_shot_template generates a string, which is passed to the model
result = model.invoke(final_prompt)
print(result.content, '\n')