import os
from dotenv import load_dotenv
from google.adk.agents import Agent, ParallelAgent, SequentialAgent
from google.adk.models.lite_llm import LiteLlm
from tavily_search import tavily_search_tool

# Load API keys from .env file
load_dotenv()

def create_product_analyst():
    """
    Constructs the Product Analyst Multi-Agent System using Google ADK.
    Orchestration: Parallel Analysis -> Feature Synthesis -> Logic Visualization.
    """

    # 1. Model Configuration (Using LiteLLM to interface with DeepSeek)
    model_config = LiteLlm(
        model="deepseek/deepseek-chat", 
        api_key=os.getenv("DEEPSEEK_API_KEY")
    )

    # --- PHASE 1: Parallel Analysis (Three Specialized Experts) ---
    
    # User Expert: Focuses on Persona and Pain Points
    user_expert = Agent(
        name="UserExpert",
        model=model_config,
        instruction="""You are a Product Manager. Analyze user pain points for the proposed product idea. 
        Limit to 200 words. Use Markdown list format covering:
        1. Target User Segments
        2. Core Pain Point Analysis
        3. User Requirement Prioritization""",
        output_key="user_analysis"
    )

    # Tech Expert: Focuses on Architecture and Implementation
    tech_expert = Agent(
        name="TechExpert",
        model=model_config,
        instruction="""You are a CTO. Provide technical architecture advice for the product idea.
        Limit to 200 words. Use Markdown format covering:
        1. Tech Stack Recommendations
        2. System Architecture Design
        3. Technical Challenge Analysis
        4. Development Cost Estimation""",
        output_key="tech_analysis"
    )

    # Market Expert: Real-time intelligence using Tavily Search
    market_expert = Agent(
        name="MarketExpert",
        model=model_config,
        instruction="""You are a Senior Business Analyst. Use real-time retrieval to provide market depth.
        
        Standard Operating Procedure (SOP):
        1. **Mandatory Search**: Call `tavily_search_tool` for latest trends, competitors, and industry reports.
        2. **Data Handling**: Base your analysis on the `content` field. DO NOT discard the `search_sources`.
        3. **Logic**: If search fails, state so and provide knowledge-based advice. Evaluate feasibility using live data.
        4. **Output**: Target market, competitors, monetization, and marketing strategy.
        5. **Strict Requirement**: End your response with a [SEARCH_DATA] tag containing the unmodified `search_sources` list.
        """,
        tools=[tavily_search_tool],
        output_key="market_analysis"
    )

    # Orchestrate the three experts to run concurrently
    parallel_analysis = ParallelAgent(
        name="ParallelAnalysis",
        sub_agents=[user_expert, tech_expert, market_expert]
    )

    # --- PHASE 2: Sequential Synthesis (Consolidation & Visualization) ---
    
    # Feature Manager: Synthesizes expert reports into an MVP roadmap
    feature_agent = Agent(
        name="FeatureManager",
        model=model_config,
        instruction="""Based on the provided reports:
        User Analysis: {user_analysis}
        Tech Advice: {tech_analysis}
        Market Analysis: {market_analysis}

        Generate an MVP Feature List in a Markdown table format.
        Include: Feature Name, Priority, Implementation Difficulty, and Expected Impact.""",
        output_key="feature_list"
    )

    # Logic Designer: Converts the roadmap into a visual flowchart
    logic_agent = Agent(
        name="LogicDesigner",
        model=model_config,
        instruction="""Based on this feature list: {feature_list}
        Generate a business logic flowchart in Mermaid 'graph TD' format.
        
        Requirements:
        1. Output raw text ONLY (no ```mermaid tags).
        2. Ensure a clear, complete logic flow.
        3. Must be valid Mermaid syntax, NOT JSON.""",
        output_key="mermaid_code"
    )

    # Final Orchestration: Parallel Experts -> Feature Aggregator -> Logic Flow Visualizer
    root_system = SequentialAgent(
        name="ProductAnalystSystem",
        sub_agents=[parallel_analysis, feature_agent, logic_agent]
    )

    return root_system

# --- Deployment: Export the root agent for the API Server ---
root_agent = create_product_analyst()