"""对标分析工具 — 封装对标分析小模型为 LangChain Tool。"""

import json
from langchain_core.tools import tool

from src.data.connector import get_benchmark_analysis


@tool
def benchmark_analysis(unit_id: str = "GT-01") -> str:
    """调用对标分析小模型，将本机组运行指标与同类机组进行对比分析。

    对标指标包括：厂用电率、利用小时、平均发电负荷、负荷率、发电计划完成率、
    热电比、售电收入等。返回本机组与同类机组平均值的对比及差距分析。

    Args:
        unit_id: 机组编号，默认 GT-01
    """
    result = get_benchmark_analysis()
    result["unit_id"] = unit_id
    return json.dumps(result, ensure_ascii=False, indent=2)
