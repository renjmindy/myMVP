import os
import torch
from dotenv import load_dotenv
from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI
# Replace local loader with WebBaseLoader
from langchain_community.document_loaders import WebBaseLoader
from langchain_text_splitters import CharacterTextSplitter
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

# 1. Environment and Path Configuration
load_dotenv()
current_dir = os.path.dirname(os.path.abspath(__file__))
db_dir = os.path.join(current_dir, "db")
# Define the persistent directory specifically for web content
persistent_directory = os.path.join(db_dir, "07_webloader_db")

# 2. Initialize DeepSeek Chat Model
#model = ChatDeepSeek(model="deepseek-chat")
model = ChatOpenAI(
    model="gpt-4o-mini",
    # base_url is optional here; defaults to https://api.openai.com/v1
)

# 3. Initialize BGE Embedding Model (Maintaining a high-performance combination)
model_name = "BAAI/bge-large-en-v1.5"
device = "cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu")

hf_embeddings = HuggingFaceEmbeddings(
    model_name=model_name,
    model_kwargs={"device": device},
    encode_kwargs={"normalize_embeddings": True}
)

# 4. Vector Database Logic: Integrated Web Scraping
if not os.path.exists(persistent_directory):
    print(f"--- Scraping data from the web and initializing vector database ---")
    
    # Define target URLs
    urls = ["https://www.apple.com/"]
    
    # Use WebBaseLoader to scrape web content
    loader = WebBaseLoader(urls)
    documents = loader.load()
    
    # Text splitting
    text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    docs = text_splitter.split_documents(documents)
    
    print(f"Scraping complete. Split into {len(docs)} document chunks.")

    # Create and persist the vector database
    db = Chroma.from_documents(
        documents=docs, 
        embedding=hf_embeddings, 
        persist_directory=persistent_directory
    )
    print("Web content vector database initialization complete.")
else:
    db = Chroma(
        persist_directory=persistent_directory, 
        embedding_function=hf_embeddings
    )
    print(f"Successfully loaded existing web vector database: {persistent_directory}")

# 5. Execute Retrieval and Q&A
# Modified query to match the web topic
query = "What new products are announced on Apple.com?"
print(f"\n--- Question: {query} ---")

# Retrieve the top 3 most relevant web snippets
retrieved_docs = db.similarity_search(query, k=3)

# Combine context
context_parts = []
for i, doc in enumerate(retrieved_docs, 1):
    # Extract content and the source URL from metadata
    source = doc.metadata.get("source", "Unknown URL")
    context_parts.append(f"[Source {source}]:\n{doc.page_content}")

context = "\n\n".join(context_parts)

# 6. Generate Answer
prompt = f"""Please answer the question based on the following background information retrieved from the web.
If no specific products are mentioned in the background, please summarize based on the retrieved content.

Background: {context}

Question: {query}"""

response = model.invoke(prompt)

print(f"\n--- OpenAI Answer (Based on Web Content) ---\n{response.content}")