"""根因诊断 Agent — 负责故障排查与异常诊断，严格只使用 root_cause_analysis 工具。"""

from src.agents.base import BaseAgent
from src.tools import registry as tool_registry


class RootCauseAgent(BaseAgent):
    name = "root_cause_agent"
    description = "根因诊断 Agent — 专注故障排查与异常分析"
    system_prompt = """你是根因诊断智能体。

触发条件：用户询问“原因”、“为什么”、“故障排查”、“异常分析”、“诊断”等根因类问题。
操作：仅调用 root_cause_analysis 工具（不要同时调用其他工具）。
输出：结构化诊断报告（异常参数、触发规则、诊断链、知识库参考、处理建议）。

通用原则：所有结论必须基于工具返回的数据，不要编造数字；引用来源并给出可执行建议。"""

    def __init__(self):
        super().__init__()
        self.register_tools(tool_registry.get_tools(["root_cause_analysis"]))
