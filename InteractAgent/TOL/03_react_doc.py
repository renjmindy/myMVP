import os
import torch
from dotenv import load_dotenv
from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import CharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_classic import hub
from langchain_classic.agents import AgentExecutor, create_react_agent
from langchain_classic.chains import create_history_aware_retriever, create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import Tool

# 1. Environment and Path Configuration
load_dotenv()
current_dir = os.path.dirname(os.path.abspath(__file__))
file_path = os.path.join(current_dir, "story.txt")  # Your data source file
db_dir = os.path.join(current_dir, "db", "03_react_doc_db") # Vector store storage location

# 2. Initialize BGE Chinese Embedding Model
model_name = "BAAI/bge-large-en-v1.5"
device = "mps" if torch.backends.mps.is_available() else "cuda" if torch.cuda.is_available() else "cpu"
print(f"--- Loading BGE embedding model, using device: {device} ---")

hf_embeddings = HuggingFaceEmbeddings(
    model_name=model_name,
    model_kwargs={"device": device},
    encode_kwargs={"normalize_embeddings": True}
)

# 3. Vector Store Logic: Automatic Creation or Loading
if not os.path.exists(db_dir):
    print(f"--- Initializing vector store, reading file: {file_path} ---")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Source file not found: {file_path}, please ensure story.txt exists.")
    
    loader = TextLoader(file_path, encoding='utf-8')
    documents = loader.load()
    # Text Splitting
    text_splitter = CharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    docs = text_splitter.split_documents(documents)

    db = Chroma.from_documents(
        documents=docs, 
        embedding=hf_embeddings, 
        persist_directory=db_dir
    )
    print("--- Vector store initialization and saving complete ---")
else:
    db = Chroma(persist_directory=db_dir, embedding_function=hf_embeddings)
    print("--- Successfully loaded existing vector store ---")

# Create Retriever
retriever = db.as_retriever(search_type="similarity", search_kwargs={"k": 3})

# 4. Initialize DeepSeek Chat Model (Brain)
#llm = ChatDeepSeek(model="deepseek-chat", temperature=0)
llm = ChatOpenAI(
    model="gpt-4o-mini",
    # base_url is optional here; defaults to https://api.openai.com/v1
)

# 5. Configure RAG Reasoning Chain (Localized Version)
# Context Restructuring Prompt
contextualize_q_system_prompt = (
    "Given a chat history and the latest user question (which might reference context in the history), "
    "reformulate it into a standalone question that can be understood without the chat history. Do not answer the question, just reformulate it."
)
contextualize_q_prompt = ChatPromptTemplate.from_messages([
    ("system", contextualize_q_system_prompt),
    MessagesPlaceholder("chat_history"),
    ("human", "{input}"),
])

history_aware_retriever = create_history_aware_retriever(llm, retriever, contextualize_q_prompt)

# Core Q&A Prompt
qa_system_prompt = (
    "You are a Q&A assistant based on a document library. Please use the following background information to answer the question. "
    "If you don't know, say you don't know. Keep answers within three sentences and remain concise.\n\nBackground:\n{context}"
)
qa_prompt = ChatPromptTemplate.from_messages([
    ("system", qa_system_prompt),
    MessagesPlaceholder("chat_history"),
    ("human", "{input}"),
])

question_answer_chain = create_stuff_documents_chain(llm, qa_prompt)
rag_chain = create_retrieval_chain(history_aware_retriever, question_answer_chain)

# 6. Set up ReAct Agent Tools
tools = [
    Tool(
        name="Story Document Query",
        func=lambda input, **kwargs: rag_chain.invoke(
            {"input": input, "chat_history": kwargs.get("chat_history", [])}
        ),
        description="Use this tool when you need to answer questions about the story content, background, or details in the story.txt document library.",
    )
]

# Create Agent
react_prompt = hub.pull("hwchase17/react")
agent = create_react_agent(llm=llm, tools=tools, prompt=react_prompt)
agent_executor = AgentExecutor.from_agent_and_tools(
    agent=agent, 
    tools=tools, 
    handle_parsing_errors=True, 
    verbose=True
)

# 7. Interaction Loop
chat_history = []
print("--- OpenAI RAG Agent (story.txt version) Started ---")

while True:
    query = input("\nUser: ")
    if query.lower() == "exit":
        break

    response = agent_executor.invoke({"input": query, "chat_history": chat_history})
    print(f"\nAI: {response['output']} \n")

    chat_history.append(HumanMessage(content=query))
    chat_history.append(AIMessage(content=response["output"]))