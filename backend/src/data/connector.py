"""数据连接器 — 统一数据访问接口。

当前全部使用 Mock 数据。后续替换为真实 API 调用时，只需修改本文件内部实现，
上层调用方无需变动。
"""

from src.data.mock_data import (
    generate_realtime_data,
    generate_efficiency_trend,
    generate_efficiency_analysis,
    generate_loss_analysis,
    generate_benchmark_analysis,
)


def get_realtime_data() -> dict:
    """获取燃气轮机实时监测数据。"""
    return generate_realtime_data()


def get_efficiency_trend(days: int = 7) -> dict:
    """获取能效指标趋势数据。"""
    df = generate_efficiency_trend(days)
    return {"data": df.to_dict(orient="list"), "period_days": days}


def get_efficiency_analysis() -> dict:
    """调用能效分析小模型。"""
    return generate_efficiency_analysis()


def get_loss_analysis() -> dict:
    """调用耗差分析小模型。"""
    return generate_loss_analysis()


def get_benchmark_analysis() -> dict:
    """调用对标分析小模型。"""
    return generate_benchmark_analysis()
