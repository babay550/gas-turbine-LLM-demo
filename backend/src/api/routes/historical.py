"""历史数据查询 API — 时序查询、聚合、统计分析。"""

import logging
from typing import Optional

from fastapi import APIRouter, Query, HTTPException

from src.services.query_service import (
    get_time_range,
    query_time_series,
    get_parameter_stats,
    get_multi_parameter_stats,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/range")
async def api_get_range(unit_id: str = Query("GT-01")):
    """获取数据库中时序数据的时间范围。"""
    return get_time_range(unit_id)


@router.get("/query")
async def api_query(
    parameter_keys: str = Query(..., description="逗号分隔的参数key列表"),
    start: str = Query(..., description="开始时间 ISO格式"),
    end: str = Query(..., description="结束时间 ISO格式"),
    unit_id: str = Query("GT-01"),
    aggregation: str = Query("raw", description="聚合间隔: raw/1min/5min/15min/1h/6h/1d/1w"),
):
    """查询多参数时序数据（返回 ECharts 友好格式）。"""
    keys = [k.strip() for k in parameter_keys.split(",") if k.strip()]
    if not keys:
        raise HTTPException(400, "至少需要一个参数key")

    return query_time_series(keys, start, end, unit_id, aggregation)


@router.get("/stats")
async def api_stats(
    parameter_keys: str = Query(..., description="逗号分隔的参数key列表"),
    start: str = Query(..., description="开始时间"),
    end: str = Query(..., description="结束时间"),
    unit_id: str = Query("GT-01"),
):
    """批量获取参数统计摘要。"""
    keys = [k.strip() for k in parameter_keys.split(",") if k.strip()]
    if not keys:
        raise HTTPException(400, "至少需要一个参数key")

    stats = get_multi_parameter_stats(keys, start, end, unit_id)
    return {"stats": stats, "total": len(stats)}


@router.get("/parameters/{parameter_key}/trend")
async def api_parameter_trend(
    parameter_key: str,
    start: str = Query(..., description="开始时间"),
    end: str = Query(..., description="结束时间"),
    unit_id: str = Query("GT-01"),
    aggregation: str = Query("raw"),
):
    """单参数趋势数据。"""
    result = query_time_series([parameter_key], start, end, unit_id, aggregation)
    stats = get_parameter_stats(parameter_key, start, end, unit_id)
    return {
        "parameter_key": parameter_key,
        "data": result.get("data", {}),
        "stats": stats,
        "period_days": result.get("period_days", 0),
    }
