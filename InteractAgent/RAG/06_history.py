import os
import torch
from dotenv import load_dotenv

# Core Chain Components
from langchain_classic.chains import create_history_aware_retriever, create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain

# Basic Components
from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import CharacterTextSplitter
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage

# 1. Environment and Path Configuration
load_dotenv()
current_dir = os.path.dirname(os.path.abspath(__file__))
file_path = os.path.join(current_dir, "story.txt")
persistent_directory = os.path.join(current_dir, "db", "06_history_db")

# 2. Initialize DeepSeek
#llm = ChatDeepSeek(model="deepseek-chat")
llm = ChatOpenAI(
    model="gpt-4o-mini",
    # base_url is optional here; defaults to https://api.openai.com/v1
)

# 3. Initialize Embedding Model
model_name = "BAAI/bge-large-en-v1.5"
device = "cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu")

hf_embeddings = HuggingFaceEmbeddings(
    model_name=model_name,
    model_kwargs={"device": device},
    encode_kwargs={"normalize_embeddings": True}
)

# 4. Vector Database Logic
if not os.path.exists(persistent_directory):
    loader = TextLoader(file_path, encoding='utf-8')
    documents = loader.load()
    text_splitter = CharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    docs = text_splitter.split_documents(documents)
    db = Chroma.from_documents(docs, hf_embeddings, persist_directory=persistent_directory)
else:
    db = Chroma(persist_directory=persistent_directory, embedding_function=hf_embeddings)

# Base Retriever
base_retriever = db.as_retriever(search_kwargs={"k": 3})

# --- CORE IMPROVEMENT: Building a History-Aware Retrieval Chain ---

# A. Question Reformulation Prompt: 
# Encourages the AI to rewrite the question into a standalone version based on chat history.
contextualize_q_system_prompt = (
    "Given a chat history and the latest user question "
    "which might reference context in the chat history, "
    "formulate a standalone question which can be understood "
    "without the chat history. Do NOT answer the question, "
    "just reformulate it if needed and otherwise return it as is."
)

contextualize_q_prompt = ChatPromptTemplate.from_messages([
    ("system", contextualize_q_system_prompt),
    MessagesPlaceholder("chat_history"),
    ("human", "{input}"),
])

# Create History-Aware Retriever
history_aware_retriever = create_history_aware_retriever(
    llm, base_retriever, contextualize_q_prompt
)

# B. Final Answer Prompt: 
# Instructs the AI to answer based on the retrieved context.
qa_system_prompt = (
    "You are an assistant for question-answering tasks. "
    "Use the following pieces of retrieved context to answer the question. "
    "If you don't know the answer, just say that you don't know. "
    "Use three sentences maximum and keep the answer concise."
    "\n\nContext: {context}"
)

qa_prompt = ChatPromptTemplate.from_messages([
    ("system", qa_system_prompt),
    MessagesPlaceholder("chat_history"),
    ("human", "{input}"),
])

# Create Document Combination Chain (Stuff Documents Chain)
question_answer_chain = create_stuff_documents_chain(llm, qa_prompt)

# Create the Final RAG Retrieval Chain
rag_chain = create_retrieval_chain(history_aware_retriever, question_answer_chain)

# 5. Execute Continuous Dialogue Loop
def start_chatting():
    print("\n--- History-Aware Dialogue Mode Started (Type 'exit' to quit) ---")
    chat_history = []  # List to store dialogue records
    
    while True:
        user_input = input("\nYou: ")
        if user_input.lower() == "exit":
            break
            
        # Invoke RAG Chain
        # The rag_chain automatically handles: Question Rewriting -> Retrieval -> Contextual Answering
        response = rag_chain.invoke({
            "input": user_input,
            "chat_history": chat_history
        })
        
        print(f"DeepSeek: {response['answer']}")
        
        # Update Dialogue History (Note: Save as HumanMessage and AIMessage objects)
        chat_history.append(HumanMessage(content=user_input))
        chat_history.append(AIMessage(content=response['answer']))

if __name__ == "__main__":
    start_chatting()