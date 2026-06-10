"""知识问答 Agent — 负责纯技术知识库检索与回答（不触发实时工具）。"""

from src.agents.base import BaseAgent
from src.tools import registry as tool_registry


class WikiAgent(BaseAgent):
    name = "wiki_agent"
    description = "知识库问答 Agent — 用于检索规程/标准/处理方案等技术问答"
    system_prompt = """你是技术知识问答智能体。

触发条件：用户询问检修规程、设备参数、操作规范、技术标准、处理方案等纯知识类问题。
操作：仅调用 wiki_search 工具，不要调用其他实时分析工具。
输出：基于检索结果回答，并标注来源词条 ID 与标题；如知识库不足，应如实说明。"""

    def __init__(self):
        super().__init__()
        self.register_tools(tool_registry.get_tools(["wiki_search"]))
