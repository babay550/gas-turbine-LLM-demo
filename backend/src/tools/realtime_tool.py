"""实时监测工具 — 获取燃气轮机当前 SCADA 运行参数。"""

import json
from langchain_core.tools import tool

from src.data.connector import get_realtime_data


@tool
def realtime_monitoring(unit_id: str = "GT-01") -> str:
    """获取燃气轮机当前实时 SCADA 监测参数。

    返回 29 项实时监测数据，包括压气机（进口温度T1、进口压力P1、出口温度T2、出口压力P2、空气流量）、
    燃烧室（透平进口温度T3、出口压力P3、天然气瞬时流量、燃气温度、燃气压力、低位热值、排烟含氧量、CO、未燃碳氢）、
    透平（出口温度T4、出口压力P4）、发电机（有功功率、累计发电量）、汽机（主蒸汽参数、发电功率）、
    余热锅炉（进出口烟温、蒸汽参数）、振动（轴向/垂向）。

    Args:
        unit_id: 机组编号，默认 GT-01
    """
    result = get_realtime_data()
    return json.dumps(result, ensure_ascii=False, indent=2)
