"""能效趋势工具 — 获取能效指标历史趋势。"""

import json
from langchain_core.tools import tool

from src.data.connector import get_efficiency_trend


@tool
def efficiency_trend(days: int = 7) -> str:
    """获取燃气轮机能效指标近 N 天的历史趋势。

    返回热耗率、发电效率、厂用电率、综合厂用电率的逐日变化数据。

    Args:
        days: 回溯天数，默认 7 天
    """
    result = get_efficiency_trend(days)
    return json.dumps(result, ensure_ascii=False, indent=2)
