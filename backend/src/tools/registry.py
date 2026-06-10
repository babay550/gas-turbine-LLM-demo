"""Centralized Tool Registry — 避免在多个 Agent 中重复实例化/注册工具。

提供：get_tool(name)、get_tools(names)、all_tools()
"""

from typing import List, Dict

from src.tools.efficiency_tool import efficiency_analysis
from src.tools.loss_analysis_tool import loss_analysis
from src.tools.benchmark_tool import benchmark_analysis
from src.tools.realtime_tool import realtime_monitoring
from src.tools.warning_tool import warning_query
from src.tools.trend_tool import efficiency_trend
from src.tools.wiki_search_tool import wiki_search
from src.tools.root_cause_tool import root_cause_analysis

# 列出所有可用的工具单例（导入即构建）
_ALL_TOOLS = [
    realtime_monitoring,
    efficiency_analysis,
    loss_analysis,
    benchmark_analysis,
    efficiency_trend,
    warning_query,
    wiki_search,
    root_cause_analysis,
]

# 建立名称到工具对象的映射，兼容 tool.name 或 函数名
_NAME_MAP: Dict[str, object] = {}
for _t in _ALL_TOOLS:
    _key = getattr(_t, "name", None) or getattr(_t, "__name__", None)
    if _key:
        _NAME_MAP[_key] = _t


def get_tool(name: str):
    """返回指定 name 的工具对象，找不到返回 None。"""
    return _NAME_MAP.get(name)


def get_tools(names: List[str]):
    """按名称列表返回存在的工具对象列表（保持顺序）。"""
    out: List[object] = []
    for n in names:
        t = get_tool(n)
        if t is not None:
            out.append(t)
    return out


def all_tools():
    """返回所有已注册的工具对象列表。"""
    return list(_ALL_TOOLS)
