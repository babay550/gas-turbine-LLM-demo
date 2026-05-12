"""预警查询工具 — 获取当前活跃预警列表。"""

import json
from langchain_core.tools import tool


@tool
def warning_query(severity: str = "all") -> str:
    """查询当前活跃的预警信息。

    返回预警列表，包括预警等级（高/中/低）、来源、消息、关联参数、
    当前值、阈值、单位、时间和状态。

    Args:
        severity: 筛选等级，可选 高/中/低/all，默认 all
    """
    from src.api.routes.warning import MOCK_WARNINGS
    items = MOCK_WARNINGS
    if severity != "all":
        items = [w for w in items if w["level"] == severity]
    active = [w for w in items if w["status"] == "active"]
    return json.dumps({"total": len(active), "warnings": active}, ensure_ascii=False, indent=2)
