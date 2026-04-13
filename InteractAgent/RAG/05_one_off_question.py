import os
import torch
from dotenv import load_dotenv
from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import CharacterTextSplitter
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
# Import message classes for better conversation management
from langchain_core.messages import SystemMessage, HumanMessage

# 1. Environment and Path Configuration
load_dotenv()
current_dir = os.path.dirname(os.path.abspath(__file__))
file_path = os.path.join(current_dir, "story.txt")
persistent_directory = os.path.join(current_dir, "db", "01_chroma_db")

# 2. Initialize DeepSeek
#model = ChatDeepSeek(model="deepseek-chat")
model = ChatOpenAI(
    model="gpt-4o-mini",
    # base_url is optional here; defaults to https://api.openai.com/v1
)


# 3. Initialize BGE Embedding Model
model_name = "BAAI/bge-large-en-v1.5"
device = "cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu")

hf_embeddings = HuggingFaceEmbeddings(
    model_name=model_name,
    model_kwargs={"device": device},
    encode_kwargs={"normalize_embeddings": True}
)

# 4. Vector Database Logic (Simplified, remains unchanged)
if not os.path.exists(persistent_directory):
    loader = TextLoader(file_path, encoding='utf-8')
    documents = loader.load()
    text_splitter = CharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    docs = text_splitter.split_documents(documents)
    db = Chroma.from_documents(docs, hf_embeddings, persist_directory=persistent_directory)
else:
    db = Chroma(persist_directory=persistent_directory, embedding_function=hf_embeddings)

# 5. Execute Retrieval and Q&A (Enhanced Constraint Logic)
query = "What is the main content of the story?"
print(f"--- Question: {query} ---")

# Execute similarity search
retrieved_docs = db.similarity_search(query, k=3)

# --- CORE IMPROVEMENT: Building context injection with "Hard Constraints" ---
context_text = "\n\n".join([doc.page_content for doc in retrieved_docs])

combined_input = (
    "The following are document snippets that may help answer the question:\n"
    "--------------------\n"
    f"{context_text}\n"
    "--------------------\n\n"
    f"Based on the documents above, answer the following question: {query}\n"
)

# Use Message Sequences: System Instruction + Human Input
messages = [
    SystemMessage(content=(
        "You are a rigorous assistant. Please answer questions based ONLY on the provided background information. "
        "If the answer is not in the background information, respond directly with 'I'm not sure' and do not attempt to fabricate content."
    )),
    HumanMessage(content=combined_input)
]

# Generate result
response = model.invoke(messages)

print(f"\n--- OpenAI Answer ---\n{response.content}")