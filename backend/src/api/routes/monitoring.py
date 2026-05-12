"""能效监测 API — 实时数据、能效指标、趋势数据。"""

from fastapi import APIRouter

from src.data.connector import get_realtime_data, get_efficiency_trend

router = APIRouter()


@router.get("/realtime")
async def realtime_data():
    """获取燃气轮机实时监测数据。"""
    return get_realtime_data()


@router.get("/efficiency-trend")
async def efficiency_trend(days: int = 7):
    """获取能效指标趋势数据。"""
    import pandas as pd
    data = get_efficiency_trend(days)
    df = pd.DataFrame(data["data"])
    df["日期"] = df["日期"].astype(str)
    return {"data": df.to_dict(orient="list"), "period_days": days}
