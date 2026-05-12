"""运营优化 Agent — 封装能效分析、耗差分析、对标分析、实时监测、预警查询能力。"""

from src.agents.base import BaseAgent
from src.tools.efficiency_tool import efficiency_analysis
from src.tools.loss_analysis_tool import loss_analysis
from src.tools.benchmark_tool import benchmark_analysis
from src.tools.realtime_tool import realtime_monitoring
from src.tools.warning_tool import warning_query
from src.tools.trend_tool import efficiency_trend


class OptimizationAgent(BaseAgent):

    name = "optimization_agent"
    description = "燃气轮机运营优化智能体，提供实时监测、能效分析、耗差分析、对标分析、预警查询及优化建议"
    system_prompt = """你是燃气轮机运营优化专家智能体。你的职责是基于监测数据和分析结果为电厂运行优化工程师提供专业的运营建议。

你的核心能力（通过工具获取数据）：
1. realtime_monitoring — 获取当前 29 项 SCADA 实时监测参数（温度、压力、流量、功率、振动等）
2. efficiency_analysis — 调用能效分析小模型，获取七大能效指标及原始 SCADA 值
3. loss_analysis — 调用耗差分析小模型，分析各项损失占比
4. benchmark_analysis — 调用对标分析小模型，将本机组与同类机组对比
5. efficiency_trend — 获取近期能效指标历史趋势
6. warning_query — 查询当前活跃预警信息

工作原则：
- 回答任何关于机组状态的问题时，必须先调用 realtime_monitoring 获取实时数据
- 需要分析性能时，调用 efficiency_analysis 和 loss_analysis
- 需要对比同类机组时，调用 benchmark_analysis
- 提到预警时，调用 warning_query
- 所有结论必须基于工具返回的数据，不要编造数字
- 优化建议要具体、可操作（如调整参数方向和幅度）

回复格式：
1. 简要概述当前状态（引用实际监测数据）
2. 关键指标分析（标注数据来源，如"根据实时监测数据"或"根据能效分析模型结果"）
3. 具体优化建议（按优先级排列）"""

    def __init__(self):
        super().__init__()
        self.register_tools([
            realtime_monitoring,
            efficiency_analysis,
            loss_analysis,
            benchmark_analysis,
            efficiency_trend,
            warning_query,
        ])
