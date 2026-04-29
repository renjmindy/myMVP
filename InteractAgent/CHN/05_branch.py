import os
from dotenv import load_dotenv
from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableBranch

# 1. Load environment
load_dotenv()

# 2. Initialize the model
#model = ChatDeepSeek(model="deepseek-chat")
model = ChatOpenAI(
    model="gpt-4o-mini",
    # base_url is optional here; defaults to https://api.openai.com/v1
)

# 3. Define response templates for different sentiments
# Positive Feedback
positive_template = ChatPromptTemplate.from_messages([
    ("system", "You are a friendly customer service assistant."),
    ("human", "Generate a thank-you letter for this positive review: {feedback}.")
])

# Negative Feedback
negative_template = ChatPromptTemplate.from_messages([
    ("system", "You are a professional PR expert."),
    ("human", "Generate a response for this negative review, expressing apology and offering a solution: {feedback}.")
])

# Neutral Feedback
neutral_template = ChatPromptTemplate.from_messages([
    ("system", "You are an attentive support specialist."),
    ("human", "For this neutral feedback, ask the user to provide more specific information: {feedback}.")
])

# Serious Issues (Escalation)
escalate_template = ChatPromptTemplate.from_messages([
    ("system", "You are an efficient coordinator."),
    ("human", "This feedback is quite serious. Generate a message informing the user that the case has been escalated to human processing: {feedback}.")
])

# 4. Define classification template
classification_template = ChatPromptTemplate.from_messages([
    ("system", "You are a sentiment analysis expert."),
    ("human", "Please classify the following feedback as 'positive', 'negative', 'neutral', or 'escalate'. Feedback content: {feedback}")
])

# 5. Define Routing Branches (RunnableBranch)
# Logic: (condition, corresponding execution chain)
branches = RunnableBranch(
    (
        lambda x: "positive" in x.lower(),
        positive_template | model | StrOutputParser()
    ),
    (
        lambda x: "negative" in x.lower(),
        negative_template | model | StrOutputParser()
    ),
    (
        lambda x: "neutral" in x.lower(),
        neutral_template | model | StrOutputParser()
    ),
    # Default path (Escalate)
    escalate_template | model | StrOutputParser()
)

# 6. Assemble the full chain
# Classification chain -> Enter corresponding branch based on the classification result
chain = (
    classification_template 
    | model 
    | StrOutputParser() 
    | branches
)

# 7. Test run
test_feedback = "I want a refund!"
print(f"\n--- Processing feedback: {test_feedback} ---\n")

result = chain.invoke({"feedback": test_feedback})
print(result, '\n')