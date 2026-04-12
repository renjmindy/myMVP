import os
from dotenv import load_dotenv
from google.adk.agents import Agent, ParallelAgent, SequentialAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StdioServerParameters, StdioConnectionParams
from tavily_search import tavily_search_tool

load_dotenv()

# --- 1. Unified Google MCP Toolset Initialization ---
# --- SERVER 1: Your existing Code Assist (Docs) ---
def get_google_mcp_tools():
    """
    Initializes the official Google Maps Platform MCP server.
    As of 2026, this unified server provides:
    - Places (Nearby, Text Search)
    - Routes (Compute Routes with Traffic)
    - Environment (Weather, Air Quality, Pollen)
    """
    print("🚀 Launching Unified Google Maps Platform MCP Server...")
    
    # We use the updated official server that includes the 2025/2026 Environment APIs
    # 1. Ensure the key is loaded (and provide a fallback for testing)
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("CRITICAL: GOOGLE_MAPS_API_KEY is missing from environment variables.")

    return MCPToolset(
        connection_params=StdioConnectionParams(
            # The 'server_params' field is REQUIRED by the Pydantic model
            server_params=StdioServerParameters(
                command='npx',
                args=["-y", "@googlemaps/code-assist-mcp@latest"],
                env={
                    "GOOGLE_MAPS_API_KEY": api_key
                }
            )
        )
    )

# --- SERVER 2: The new Live Maps Server (Data) ---
# Ensure your GOOGLE_MAPS_API_KEY is in your .env file
def get_googleMap_mcp_tools():
    """
    Initializes the official Google Maps Platform MCP server.
    As of 2026, this unified server provides:
    - Places (Nearby, Text Search)
    - Routes (Compute Routes with Traffic)
    - Environment (Weather, Air Quality, Pollen)
    """
    print("🚀 Launching Unified Google Maps Platform MCP Server...")
    
    # We use the updated official server that includes the 2025/2026 Environment APIs
    # 1. Ensure the key is loaded (and provide a fallback for testing)
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("CRITICAL: GOOGLE_MAPS_API_KEY is missing from environment variables.")

    #return MCPToolset(
    #    connection_params=StdioConnectionParams(
    #        # The 'server_params' field is REQUIRED by the Pydantic model
    #        server_params=StdioServerParameters(
    #            command="npx",
    #            args=["-y", "@cablate/mcp-google-map", "--stdio"],
    #            env={
    #                "GOOGLE_MAPS_API_KEY": api_key
    #            }
    #        )
    #    )
    #)

    return MCPToolset(
        connection_params=StdioConnectionParams(
            # Use the direct command 'mcp-google-map' instead of 'npx'
            server_params={  # Wrap everything inside this key
                "command": "mcp-google-map", 
                "args": ["--stdio"],
                "env": {
                    "GOOGLE_MAPS_API_KEY": api_key
                }
            }
        )
    )

def create_product_analyst():
    # 1. Model Configuration (DeepSeek for low-cost, high-reasoning tool calls)
    #model_config = LiteLlm(
    #    model="deepseek/deepseek-chat", 
    #    api_key=os.getenv("DEEPSEEK_API_KEY")
    #)
    #model_config = LiteLlm(
    #    model="deepseek/deepseek-chat", 
    #    api_key=os.getenv("DEEPSEEK_API_KEY"),
    #    max_tokens=4096, # Limits the output
    #    context_window_fallback_dict={"deepseek/deepseek-chat": 128000} # Explicitly set limit
    #)

    #model_config = LiteLlm(
    #    model="gemini/gemini-1.5-pro", 
    #    api_key=os.getenv("GEMINI_API_KEY")
    #)

    # Replace your LiteLlm config with this
    model_config = LiteLlm(
        model="openai/gpt-4o-mini",  # or "openai/gpt-4o-mini" for a cheaper/faster option
        api_key=os.getenv("OPENAI_API_KEY") 
    )

    # Initialize the single unified Google toolset
    google_tools = get_google_mcp_tools()
    google_maps = get_googleMap_mcp_tools()

    # --- PHASE 1: Parallel Analysis ---

    # User Expert: Uses Google MCP for location and mobility (Traffic)
    user_expert = Agent(
        name="UserExpert",
        model=model_config,
        instruction="""You are a Product Manager specializing in Location Intelligence.
        
        【MANDATORY】: Use the google-maps tools to:
        1. Call 'places_search_text' to find existing businesses in the target area.
        2. Call 'routes_compute' to analyze real-time traffic and travel durations.
        
        Analyze patient/user pain points based on these real-world spatial constraints.""",
        output_key="user_analysis",
        tools=[google_tools] 
    )

    # Market Expert: Uses Tavily for trends and Google MCP for Environment (Weather)
    market_expert = Agent(
        name="MarketExpert",
        model=model_config,
        instruction="""You are a Senior Business Analyst.
        
        Tasks:
        1. Use 'tavily_search_tool' for industry-wide market trends.
        2. Use the 'lookup_weather' tool (from Google MCP) to analyze environmental impacts.
        
        Provide a Markdown report on feasibility, seasonal risks, and market positioning.""",
        tools=[tavily_search_tool, google_tools], 
        output_key="market_analysis"
    )

    # Tech Expert: Focuses on the implementation ecosystem
    #tech_expert = Agent(
    #    name="TechExpert",
    #    model=model_config,
    #    instruction="""You are a CTO. Provide technical architecture advice. 
    #    Focus on integrating these Google MCP services into a secure, HIPAA-compliant medical platform.""",
    #    output_key="tech_analysis"
    #)
    tech_expert = Agent(
        name="TechExpert",
        model=model_config,
        instruction="""
        CRITICAL: When using documentation tools, only extract the SPECIFIC parameters 
        or endpoints needed. Do NOT repeat large blocks of documentation in your 
        output. Be concise to stay within token limits.

        That is, only summarize the key endpoints, do not include full document text.

        You have two toolsets: 
        1. 'google_tools' for verifying implementation best practices.
        2. 'google_maps' for searching real competitors and travel times.
    
        When asked about a location like San Jose 95127:

        CRITICAL SEARCH INSTRUCTIONS:
        When searching for competitors using 'search_nearby', use these EXACT types:
        - 'medical_office'
        - 'hospital'
        - 'doctor'
    
        DO NOT use the type 'clinic' as it is not supported by the New Places API. 
        If you want to find clinics specifically, use 'search_places' with a text_query like 'medical clinics in 95127'.

        - Use google_maps 'compute_routes' for patient travel times.
        - If you are unsure of the API parameters, check google_tools.
        """,
        tools=[google_tools, google_maps], # Ensure your MCP tools are passed here
        output_key="tech_analysis"
    )

    parallel_analysis = ParallelAgent(
        name="ParallelAnalysis",
        sub_agents=[user_expert, tech_expert, market_expert]
    )

    # --- PHASE 2: Synthesis ---
    
    feature_agent = Agent(
        name="FeatureManager",
        model=model_config,
        instruction="""Synthesize the following reports into an MVP roadmap:
        User/Location: {user_analysis}
        Tech: {tech_analysis}
        Market/Weather: {market_analysis}
        
        Produce a Markdown table of features for the medical appointment app.""",
        output_key="feature_list"
    )

    logic_agent = Agent(
        name="LogicDesigner",
        model=model_config,
        instruction="""Based on {feature_list}, generate a Mermaid graph TD business logic flowchart.
        Focus on the 'Appointment Scheduling' and 'Traffic/Weather Alert' flow.""",
        output_key="mermaid_code"
    )

    # Final Orchestration
    root_system = SequentialAgent(
        name="MedicalAnalystSystem",
        sub_agents=[parallel_analysis, feature_agent, logic_agent]
    )

    return root_system

# Deployment Entry Point
root_agent = create_product_analyst()