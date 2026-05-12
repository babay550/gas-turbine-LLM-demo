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

        # TODO: 多 Agent 路由逻辑
        # 关键词匹配：运维相关 → maintenance_agent，优化相关 → optimization_agent
        optimization_keywords = ["能效", "效率", "耗差", "对标", "优化", "热耗", "厂用电", "负荷"]
        if any(kw in query for kw in optimization_keywords):
            agent = self._agents.get("optimization_agent")
        else:
            agent = next(iter(self._agents.values()))

        if agent is None:
            return {"error": "无可用的 Agent"}

        return {"agent": agent.name, **agent.run(query)}

    def trigger_direct(self, agent_name: str, tool_name: str) -> dict:
        """直接触发指定 Agent 的指定工具（一键触发场景）。"""
        agent = self._agents.get(agent_name)
        if agent is None:
            return {"error": f"Agent {agent_name} 不存在"}
        return agent.run_direct(tool_name)
