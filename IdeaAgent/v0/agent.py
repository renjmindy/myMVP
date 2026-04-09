import os
from dotenv import load_dotenv
from google.adk.agents import Agent, ParallelAgent, SequentialAgent
from google.adk.models.lite_llm import LiteLlm

load_dotenv()

def create_product_analyst(selected_agents=None):
    # Default to all experts if none are specified
    if selected_agents is None:
        selected_agents = ["UserExpert", "TechExpert", "MarketExpert"]

    # 1. Model Configuration
    # Using LiteLLM to interface with DeepSeek
    model_config = LiteLlm(
        model="deepseek/deepseek-chat", 
        api_key=os.getenv("DEEPSEEK_API_KEY")
    )

    # --- Parallel Phase: Three experts analyzing simultaneously ---
    # Agents automatically receive user messages and analyze based on conversation history
    
    user_expert = Agent(
        name="UserExpert",
        model=model_config,
        instruction="""You are a Product Manager. Analyze the user's product idea for user pain points.

Output in Markdown list format, including:
1. Target User Groups
2. Core Pain Point Analysis
3. User Requirement Prioritization""",
        output_key="user_analysis"
    )

    tech_expert = Agent(
        name="TechExpert",
        model=model_config,
        instruction="""You are a CTO. Provide technical architecture suggestions for the product idea.

Output in Markdown format, including:
1. Technical Stack Suggestions
2. System Architecture Design
3. Technical Challenges Analysis
4. Development Cost Estimation""",
        output_key="tech_analysis"
    )

    market_expert = Agent(
        name="MarketExpert",
        model=model_config,
        instruction="""You are a Business Analyst. Analyze the business model for the product idea.

Output in Markdown format, including:
1. Target Market Analysis
2. Competitive Analysis
3. Profit Model Suggestions
4. Go-to-Market Strategy""",
        output_key="market_analysis"
    )

    # Filter sub-agents based on selected_agents
    all_agents = {
        "UserExpert": user_expert,
        "TechExpert": tech_expert,
        "MarketExpert": market_expert
    }
    active_agents = [all_agents[name] for name in selected_agents if name in all_agents]

    parallel_analysis = ParallelAgent(
        name="ParallelAnalysis",
        sub_agents=active_agents
    )

    # --- Sequential Phase: Synthesis and Diagram Generation ---
    
    feature_agent = Agent(
        name="FeatureManager",
        model=model_config,
        instruction="""Based on the following analysis reports:

User Analysis:
{user_analysis}

Technical Suggestions:
{tech_analysis}

Market Analysis:
{market_analysis}

Please organize an MVP (Minimum Viable Product) feature list in a Markdown table.
The table should include: Feature Name, Priority, Implementation Difficulty, and Expected Impact.""",
        output_key="feature_list"
    )

    logic_agent = Agent(
        name="LogicDesigner",
        model=model_config,
        instruction="""Based on the following feature list:

{feature_list}

Generate a business logic flowchart in Mermaid 'graph TD' format.

Requirements:
1. Do not include ```mermaid tags or other wrappers; output plain text flowchart code only.
2. The process flow must be clear and complete.
3. Include main business nodes and transition relationships.
4. Output must be valid Mermaid syntax; do not use JSON format.""",
        output_key="mermaid_code"
    )

    # Final Orchestration: Parallel -> Synthesis -> Diagramming
    root_system = SequentialAgent(
        name="ProductAnalystSystem",
        sub_agents=[parallel_analysis, feature_agent, logic_agent]
    )

    return root_system

# --- Important: Entry point for the API Server ---
root_agent = create_product_analyst()