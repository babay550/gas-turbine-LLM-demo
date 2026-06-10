"""Agent 调度器 — 意图识别 + 路由。"""

from src.agents.base import BaseAgent


class Scheduler:
    """根据用户意图将查询路由到合适的 Agent。

    MVP 阶段仅有一个运营优化 Agent，直接路由。
    后续扩展为基于关键词/意图分类的多 Agent 路由。
    """

    def __init__(self):
        self._agents: dict[str, BaseAgent] = {}

    def register_agent(self, agent: BaseAgent):
        self._agents[agent.name] = agent

    def dispatch(self, query: str) -> dict:
        """将用户查询路由到合适的 Agent 执行。"""
        # MVP: 只有一个 Agent，直接路由
        if len(self._agents) == 1:
            agent = next(iter(self._agents.values()))
            return {"agent": agent.name, **agent.run(query)}

        # 路由关键词集合（按优先级）
        root_keywords = ["原因", "为什么", "故障", "异常", "诊断", "根因", "排查"]
        analysis_keywords = ["能效", "效率", "耗差", "对标", "优化", "热耗", "厂用电", "负荷", "损失", "趋势"]
        wiki_keywords = ["规程", "检修", "操作规范", "设备参数", "技术标准", "手册", "处理方案"]

        q = query.lower()

        if any(kw in q for kw in root_keywords):
            agent = self._agents.get("root_cause_agent")
        elif any(kw in q for kw in analysis_keywords):
            agent = self._agents.get("analysis_agent")
        elif any(kw in q for kw in wiki_keywords):
            agent = self._agents.get("wiki_agent")
        else:
            agent = self._agents.get("chat_agent") or next(iter(self._agents.values()))

        if agent is None:
            return {"error": "无可用的 Agent"}

        return {"agent": agent.name, **agent.run(query)}

    def trigger_direct(self, agent_name: str, tool_name: str) -> dict:
        """直接触发指定 Agent 的指定工具（一键触发场景）。"""
        agent = self._agents.get(agent_name)
        if agent is None:
            return {"error": f"Agent {agent_name} 不存在"}
        return agent.run_direct(tool_name)
