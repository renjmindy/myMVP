import os
import torch
from dotenv import load_dotenv
from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import CharacterTextSplitter
from langchain_chroma import Chroma
# Use the latest interface provided by langchain_huggingface
from langchain_huggingface import HuggingFaceEmbeddings

# 1. Environment and Path Configuration
load_dotenv()
current_dir = os.path.dirname(os.path.abspath(__file__))
file_path = os.path.join(current_dir, "story.txt")
persistent_directory = os.path.join(current_dir, "db", "01_chroma_db")

# 2. Initialize DeepSeek Chat Model
#model = ChatDeepSeek(model="deepseek-chat")
model = ChatOpenAI(
    model="gpt-4o-mini",
    # base_url is optional here; defaults to https://api.openai.com/v1
)

# 3. Initialize BGE Embedding Model
model_name = "BAAI/bge-large-en-v1.5"

# Automatic device selection (MPS for Mac, CUDA for NVIDIA, or CPU)
if torch.backends.mps.is_available():
    device = "mps"
elif torch.cuda.is_available():
    device = "cuda"
else:
    device = "cpu"

print(f"--- Loading embedding model using device: {device} ---")

hf_embeddings = HuggingFaceEmbeddings(
    model_name=model_name,
    model_kwargs={"device": device},
    encode_kwargs={"normalize_embeddings": True}
)

# 4. Vector Database Logic
if not os.path.exists(persistent_directory):
    print(f"--- Initializing Vector Database ---")
    loader = TextLoader(file_path)
    documents = loader.load()
    text_splitter = CharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    docs = text_splitter.split_documents(documents)

    db = Chroma.from_documents(
        documents=docs,               # Text chunks
        embedding=hf_embeddings,      # Embedding model
        persist_directory=persistent_directory # Persistence path
    )
    print("Vector database initialization complete.")
else:
    db = Chroma(
        persist_directory=persistent_directory, # Persistence path
        embedding_function=hf_embeddings       # Embedding model
    )
    print("Existing vector database loaded successfully.")

# 5. Execute Retrieval and Q&A
query = "How did Duo Duo help Zhuang Zhuang?"
print(f"--- Question: {query} ---")

# Retrieval
# Search for the top 3 text chunks most similar to the query
retrieved_docs = db.similarity_search(query, k=3)   
context = "\n\n".join([doc.page_content for doc in retrieved_docs])

# Generation (RAG Prompt)
prompt = f"Please answer the question based on the following background information.\n\nBackground: {context}\n\nQuestion: {query}"
response = model.invoke(prompt)

print(f"\n--- OpenAI Answer ---\n{response.content}")