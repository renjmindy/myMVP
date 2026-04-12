import os
from tavily import TavilyClient
from dotenv import load_dotenv

# Load environment variables (ensures TAVILY_API_KEY is accessible)
load_dotenv()

def tavily_search_tool(query: str) -> dict:
    """
    Tavily Enhanced Search Tool Function.
    Call this tool when you need to retrieve the latest market news, competitor updates, or real-time data.
    
    Args:
        query: Search keywords or the user's question.
        
    Returns:
        dict: A dictionary containing two fields:
            - content: Cleaned webpage body summary for AI analysis.
            - search_sources: A list of titles and URLs for frontend source attribution.
    """
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return {"content": "Error: TAVILY_API_KEY not found", "search_sources": []}

    try:
        client = TavilyClient(api_key=api_key)
        # Use 'advanced' search depth for more professional/business-grade information
        response = client.search(
            query=query, 
            search_depth="advanced", 
            max_results=3,
            include_raw_content=False # Ensure this is False to avoid huge HTML blobs
        )
        
        results = response.get('results', [])
        # 🔴 Log 2: Monitor the number of data entries returned by Tavily
        print(f"✅ [Tavily Module] Retrieval complete, found {len(results)} real-time sources.")

        if not results:
            return {"content": "No relevant search results found.", "search_sources": []}

        # 1. Extract core content for the LLM to process
        #content_for_ai = "\n".join([r.get('content', '') for r in results])
        content_for_ai = ""
        for r in results:
            text = r.get('content', '')
            content_for_ai += f"\nSource: {r.get('title')}\nContent: {text[:4000]}\n---" # Truncate here
        
        # 2. Extract reference links for UI display (Key for attribution/fact-checking)
        references = [
            {"title": r.get('title', 'Unknown Title'), "url": r.get('url', '')} 
            for r in results
        ]
        
        # 🔴 Log 3: Print the attribution dictionary to be returned, confirming format
        print(f"📦 [Tavily Module] Returning attribution dict, fields: {list({'content': '', 'search_sources': references}.keys())}")
        for idx, ref in enumerate(references):
            print(f"   └─ Source {idx+1}: {ref['title']} -> {ref['url']}")
            
        # 3. Persistence: Save search results to a JSON file for auditing
        import json
        import datetime
        from pathlib import Path
        
        content_data = {
            "query": query,
            "content": content_for_ai,
            "sources": references,
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        # Save to the local directory
        json_path = Path(__file__).parent / "content.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(content_data, f, ensure_ascii=False, indent=2)
        
        # Return composite structure for the Agent
        return {
            "content": content_for_ai,
            "search_sources": references
        }

    except Exception as e:
        return {"content": f"Search call exception: {str(e)}", "search_sources": []}

# --- Independent Testing Area ---
if __name__ == "__main__":
    # Only executes when running 'python tavily_search.py' directly
    print("🚀 Testing Tavily Search functionality...")
    test_query = "Latest AI Agent industry trends in 2025"
    result = tavily_search_tool(test_query)
    print("-" * 30)
    print(result)
    print("-" * 30)