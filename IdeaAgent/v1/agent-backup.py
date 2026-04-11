import os
import logging
from dotenv import load_dotenv
from google.adk.agents import Agent, ParallelAgent, SequentialAgent
from google.adk.models.lite_llm import LiteLlm

load_dotenv()

def create_product_analyst(selected_agents=None, detailed_mode=False):
    """创建产品分析系统
    Args:
        selected_agents: 可选，指定要使用的专家列表
        detailed_mode: 是否启用详细模式(包含风险评估)
    """
    if selected_agents is None:
        selected_agents = ["UserExpert", "TechExpert", "MarketExpert"]

    # 1. 模型配置
    model_config = LiteLlm(
        model="deepseek/deepseek-chat", 
        api_key=os.getenv("DEEPSEEK_API_KEY")
    )

    # --- 并行阶段：三个专家同时分析 ---
    # Agent 会自动接收用户消息并基于对话历史进行分析
    user_expert = Agent(
        name="UserExpert",
        model=model_config,
        instruction="""你是一名产品经理。请分析用户提出的产品创意的用户痛点。

请用 Markdown 列表格式输出，包括：
1. 目标用户群体
2. 核心痛点分析
3. 用户需求优先级""",
        output_key="user_analysis"
    )

    tech_expert = Agent(
        name="TechExpert",
        model=model_config,
        instruction="""你是一名CTO。请为用户提出的产品创意提供技术架构建议。

请用 Markdown 格式输出，包括：
1. 技术选型建议
2. 系统架构设计
3. 技术难点分析
4. 开发成本估算""",
        output_key="tech_analysis"
    )

    market_expert = Agent(
        name="MarketExpert",
        model=model_config,
        instruction="""你是一名商业分析师。请分析用户提出的产品创意的商业模式。

请用 Markdown 格式输出，包括：
1. 目标市场分析
2. 竞品分析
3. 盈利模式建议
4. 市场推广策略""",
        output_key="market_analysis"
    )

    # 根据selected_agents过滤子agent
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

    # --- 串行阶段：汇总并生成图表 ---
    feature_agent = Agent(
        name="FeatureManager",
        model=model_config,
        instruction="""基于以下分析报告：

用户分析：
{user_analysis}

技术建议：
{tech_analysis}

市场分析：
{market_analysis}

请整理出该产品的 MVP 功能列表，用 Markdown 表格格式输出。
表格应包含：功能名称、优先级、实现难度、预期效果。""",
        output_key="feature_list"
    )

    logic_agent = Agent(
        name="LogicDesigner",
        model=model_config,
        instruction="""请根据以下功能列表：

{feature_list}

生成一个 Mermaid graph TD 格式的业务逻辑流程图。

要求：
1. 不要包含 ```mermaid 标签或其他包装，直接输出纯文本流程图代码
2. 流程要清晰完整
3. 包含主要业务节点和流转关系
4. 输出必须是有效的 Mermaid 语法，不要使用 JSON 格式""",
        output_key="mermaid_code"
    )

    # 构建分析流程
    sub_agents = [parallel_analysis, feature_agent, logic_agent]
    
    if detailed_mode:
        risk_agent = Agent(
            name="RiskAgent",
            model=model_config,
            instruction="""基于以下分析报告：

用户分析：
{user_analysis}

技术建议：
{tech_analysis}

市场分析：
{market_analysis}

功能列表：
{feature_list}

请进行全面的产品风险评估，用 Markdown 格式输出：
1. 技术风险
2. 市场风险
3. 运营风险
4. 法律风险
5. 风险缓解建议""",
            output_key="risk_analysis",
            required_inputs=["user_analysis", "tech_analysis", "market_analysis", "feature_list"]
        )
        sub_agents.append(risk_agent)  # 将RiskAgent移到流程最后
        logging.basicConfig(level=logging.DEBUG)
        logger = logging.getLogger(__name__)
        logger.debug(f"RiskAgent added to workflow with inputs: {risk_agent.required_inputs}")

    root_system = SequentialAgent(
        name="ProductAnalystSystem",
        sub_agents=sub_agents
    )

    return root_system

# --- 重要：给 API Server 用的插头 ---
root_agent = create_product_analyst()
