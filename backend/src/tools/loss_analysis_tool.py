"""耗差分析工具 — 封装耗差分析小模型为 LangChain Tool。"""

import json
from langchain_core.tools import tool

from src.data.connector import get_loss_analysis


@tool
def loss_analysis(unit_id: str = "GT-01") -> str:
    """调用耗差分析小模型，分析燃气轮机各项损失对整体能效的影响。

    返回内容包括：压气机效率损失、燃烧效率损失、透平效率损失、排气热损失等各项
    损失占比，以及与设计值的偏差。

    Args:
        unit_id: 机组编号，默认 GT-01
    """
    result = get_loss_analysis()
    result["unit_id"] = unit_id
    return json.dumps(result, ensure_ascii=False, indent=2)
