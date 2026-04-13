import os
import torch
from dotenv import load_dotenv
from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import CharacterTextSplitter
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

# 1. Environment and Path Configuration
load_dotenv()
current_dir = os.path.dirname(os.path.abspath(__file__))
# Still pointing to the current story.txt
file_path = os.path.join(current_dir, "story.txt")
persistent_directory = os.path.join(current_dir, "db", "02_chroma_db_with_metadata")

# 2. Initialize DeepSeek Chat Model
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

# 4. Vector Database Logic (Injecting metadata for a single file)
if not os.path.exists(persistent_directory):
    print(f"--- Initializing vector database and injecting metadata ---")
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    # Load document
    loader = TextLoader(file_path)
    raw_documents = loader.load()

    # --- CORE: Manually inject file name into metadata ---
    for doc in raw_documents:
        # Explicitly record the source even if there is only one file
        doc.metadata = {"source": os.path.basename(file_path)}

    # Split documents (Metadata will automatically be copied to each chunk)
    text_splitter = CharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    docs = text_splitter.split_documents(raw_documents)

    db = Chroma.from_documents(
        documents=docs, 
        embedding=hf_embeddings, 
        persist_directory=persistent_directory
    )
    print(f"Vector database initialization complete. Tagged source: {os.path.basename(file_path)}")
else:
    db = Chroma(
        persist_directory=persistent_directory, 
        embedding_function=hf_embeddings
    )
    print("Successfully loaded existing vector database with metadata.")

# 5. Execute Retrieval and Q&A
query = "What is the main content of the story?"
print(f"\n--- Question: {query} ---")

# Retrieve relevant snippets
retrieved_docs = db.similarity_search(query, k=3)

# Extract content and retrieve source tags
context = "\n\n".join([doc.page_content for doc in retrieved_docs])
# Extract sources from metadata (using a set for deduplication)
sources = {doc.metadata.get("source", "Unknown Source") for doc in retrieved_docs}

# 6. Generate Answer
prompt = f"""Please answer the question based on the following background information.

Background: {context}

Question: {query}

(Please cite the source in your answer: {', '.join(sources)})"""

response = model.invoke(prompt)

print(f"\n--- OpenAI Answer ---\n{response.content}")