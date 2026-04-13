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
file_path = os.path.join(current_dir, "story.txt")
persistent_directory = os.path.join(current_dir, "db", "04_rag_deep_dive")

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

# 4. Vector Database Logic
if not os.path.exists(persistent_directory):
    loader = TextLoader(file_path, encoding='utf-8')
    documents = loader.load()
    text_splitter = CharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    docs = text_splitter.split_documents(documents)
    db = Chroma.from_documents(docs, hf_embeddings, persist_directory=persistent_directory)
else:
    db = Chroma(persist_directory=persistent_directory, embedding_function=hf_embeddings)

# 5. CORE UPGRADE: Integrating Three Retrieval Modes
# You can switch modes by modifying SEARCH_TYPE
# Mode A: "similarity" - Basic vector similarity
# Mode B: "mmr" - Maximum Marginal Relevance (Recommended for diversity in long texts)
# Mode C: "similarity_score_threshold" - Strict similarity threshold filtering

SEARCH_TYPE = "similarity_score_threshold" # Switch mode here

search_configs = {
    "similarity": {"k": 3},
    "mmr": {"k": 3, "fetch_k": 10, "lambda_mult": 0.5},
    "similarity_score_threshold": {"k": 3, "score_threshold": 0.1}
}

print(f"--- Executing search using {SEARCH_TYPE} mode ---")

retriever = db.as_retriever(
    search_type=SEARCH_TYPE,
    search_kwargs=search_configs[SEARCH_TYPE]
)

# 6. Execute Retrieval and Q&A
query = "What is the main content of the story?"
retrieved_docs = retriever.invoke(query)

if not retrieved_docs:
    print("--- Search results are empty (Threshold not met or no matching content) ---")
    context = "No relevant background information found."
else:
    context = "\n\n".join([doc.page_content for doc in retrieved_docs])

# 7. Generation
prompt = f"Please answer the question based on the following background information.\n\nBackground: {context}\n\nQuestion: {query}"
response = model.invoke(prompt)

print(f"\n--- OpenAI Answer ---\n{response.content}")