"""能效分析工具 — 封装能效分析小模型为 LangChain Tool。"""

import json
from langchain_core.tools import tool

from src.data.connector import get_efficiency_analysis


@tool
def efficiency_analysis(unit_id: str = "GT-01") -> str:
    """调用能效分析小模型，获取燃气轮机当前能效指标分析结果。

    返回内容包括：当前热耗率、发电效率、厂用电率等指标，与设计值和历史最优值的偏差，
    以及优化建议。

    Args:
        unit_id: 机组编号，默认 GT-01
    """
    result = get_efficiency_analysis()
    result["unit_id"] = unit_id
    return json.dumps(result, ensure_ascii=False, indent=2)
