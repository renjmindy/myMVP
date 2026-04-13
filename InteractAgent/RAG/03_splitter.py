import os
import torch
from dotenv import load_dotenv
from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI
from langchain_community.document_loaders import TextLoader
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_text_splitters import (
    CharacterTextSplitter,
    RecursiveCharacterTextSplitter,
    TokenTextSplitter,
    SentenceTransformersTokenTextSplitter,
    TextSplitter
)

# 1. Environment and Model Initialization
load_dotenv()
current_dir = os.path.dirname(os.path.abspath(__file__))
file_path = os.path.join(current_dir, "story.txt")
db_base_dir = os.path.join(current_dir, "db", "03_benchmarking")

#model = ChatDeepSeek(model="deepseek-chat")
model = ChatOpenAI(
    model="gpt-4o-mini",
    # base_url is optional here; defaults to https://api.openai.com/v1
)
device = "cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu")

hf_embeddings = HuggingFaceEmbeddings(
    model_name="BAAI/bge-large-en-v1.5",
    model_kwargs={"device": device}
)

# 2. Define 5 different splitting strategies
class CustomParagraphSplitter(TextSplitter):
    def split_text(self, text): 
        return text.split("\n\n")

splitters = {
    "Character": CharacterTextSplitter(chunk_size=500, chunk_overlap=50),
    "Recursive": RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50),
    "Token": TokenTextSplitter(chunk_size=200, chunk_overlap=20),
    "Sentence": SentenceTransformersTokenTextSplitter(chunk_size=500),
    "Custom_Para": CustomParagraphSplitter()
}

# 3. Loop through index creation and retrieval testing
loader = TextLoader(file_path, encoding='utf-8')
documents = loader.load()
query = "What is the main content of the story?"
results_summary = {}

print(f"--- Starting Benchmarking (Device: {device}) ---")

for name, splitter in splitters.items():
    persist_path = os.path.join(db_base_dir, f"db_{name}")
    
    # Build Vector Database
    if not os.path.exists(persist_path):
        docs = splitter.split_documents(documents)
        db = Chroma.from_documents(docs, hf_embeddings, persist_directory=persist_path)
    else:
        db = Chroma(persist_directory=persist_path, embedding_function=hf_embeddings)
    
    # Retrieve relevant snippets
    retrieved_docs = db.similarity_search(query, k=2)
    context = "\n\n".join([d.page_content for d in retrieved_docs])
    
    # Let OpenAI evaluate the effectiveness of each splitting method
    eval_prompt = f"""
    You are a RAG system evaluation expert.
    Below is the content retrieved using the '{name}' splitting strategy:
    ---
    {context}
    ---
    Please answer the following question based on the content above: '{query}'.
    After your answer, provide a brief evaluation: Is the context provided by this splitting method complete and coherent?
    """
    
    print(f"\n> Testing Strategy: {name}...")
    response = model.invoke(eval_prompt)
    results_summary[name] = response.content

# 4. Print Final Comparative Conclusion
print("\n" + "="*50)
print("Benchmarking Complete! Here is the OpenAI feedback for each strategy:")
for strategy, report in results_summary.items():
    print(f"\n[{strategy} Strategy Results]:\n{report}\n" + "-"*30)