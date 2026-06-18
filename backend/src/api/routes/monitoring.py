"""能效监测 API — 实时数据、能效指标、趋势数据。"""

from fastapi import APIRouter
from pydantic import BaseModel

from src.data.connector import (
    get_realtime_data,
    get_efficiency_trend,
    set_mock_override,
    get_mock_override,
    is_mock_active,
)

router = APIRouter()


class MockToggleRequest(BaseModel):
    force_mock: bool | None = None  # True=强制mock, False=强制real, None=跟随配置


@router.post("/mock-toggle")
async def toggle_mock_mode(req: MockToggleRequest):
    """调试用：运行时切换 mock/real 数据源（不持久化，重启失效）。"""
    set_mock_override(req.force_mock)
    return {
        "mock_active": is_mock_active(),
        "override": get_mock_override(),
        "message": "已切换为 Mock 数据" if is_mock_active() else "已切换为 Real 数据",
    }


@router.get("/mock-status")
async def mock_status():
    """查询当前 mock 状态。"""
    return {
        "mock_active": is_mock_active(),
        "override": get_mock_override(),
    }


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
