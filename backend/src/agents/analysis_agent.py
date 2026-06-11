"""分析 Agent — 负责能效/耗差/对标/预警/趋势等具体分析流程。"""

from src.agents.base import BaseAgent
from src.tools import registry as tool_registry


class AnalysisAgent(BaseAgent):
    name = "analysis_agent"
    description = "能效/耗差/对标/预警/趋势分析 Agent"
    system_prompt = """你是能效与运行状态分析智能体。

触发条件：用户提到效率、耗差、对标、预警、当前状态或趋势等具体分析问题。
操作：按需调用能效/耗差/对标/预警/实时监测/趋势工具，并可在必要时检索知识库（wiki_search）。
输出：简要概述、关键指标分析、具体优化建议，并标注数据来源。

通用原则：所有结论必须基于工具返回的数据，不要编造数字；优化建议要具体、可操作。"""

    def __init__(self):
        super().__init__()
        self.register_tools(tool_registry.get_tools([
            "realtime_monitoring",
            "efficiency_analysis",
            "loss_analysis",
            "benchmark_analysis",
            "efficiency_trend",
            "warning_query",
            "wiki_search",
        ]))
