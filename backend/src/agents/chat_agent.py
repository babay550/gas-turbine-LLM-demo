"""闲聊 Agent — 处理与燃机运行无关的问题的直接回答（不调用工具）。"""

from src.agents.base import BaseAgent


class ChatAgent(BaseAgent):
    name = "chat_agent"
    description = "闲聊/非燃机相关问题 Agent"
    system_prompt = """你是通用闲聊智能体。

触发条件：与燃气轮机运行、设备运维、技术知识无关的问题（如天气、新闻、编程问答、生活问题等）。
操作：不调用任何外部工具，直接基于自身知识回答；若问题涉及安全或专业范围外，应提前说明。"""

    def __init__(self):
        super().__init__()
        # 不注册工具
