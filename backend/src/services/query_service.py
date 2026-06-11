"""时序数据查询服务 — 查询、聚合、统计。"""

import logging
from datetime import datetime

import pandas as pd
from sqlalchemy import text, func

from src.db.engine import get_session
from src.db.models import TimeSeriesPoint, Parameter

logger = logging.getLogger(__name__)

# 聚合间隔映射
AGG_INTERVALS = {
    "raw": None,
    "1min": "1min",
    "5min": "5min",
    "15min": "15min",
    "1h": "1h",
    "6h": "6h",
    "1d": "1D",
    "1w": "1W",
}


def get_time_range(unit_id: str = "GT-01") -> dict:
    """获取数据库中的时间范围。"""
    with get_session() as session:
        result = session.query(
            func.min(TimeSeriesPoint.timestamp).label("min_ts"),
            func.max(TimeSeriesPoint.timestamp).label("max_ts"),
            func.count(TimeSeriesPoint.id).label("total_points"),
        ).filter(TimeSeriesPoint.unit_id == unit_id).first()

        if result.min_ts is None:
            return {"has_data": False, "unit_id": unit_id}

        return {
            "has_data": True,
            "unit_id": unit_id,
            "min_timestamp": result.min_ts.isoformat(),
            "max_timestamp": result.max_ts.isoformat(),
            "total_points": result.total_points,
        }


def query_time_series(
    parameter_keys: list[str],
    start_time: str | datetime,
    end_time: str | datetime,
    unit_id: str = "GT-01",
    aggregation: str = "raw",
) -> dict:
    """查询多个参数的时序数据。

    每个参数独立返回自己的时间戳和值数组，避免不同采样频率交叉产生空值。
    Returns: {data: {param_key1: {timestamp: [...], values: [...]}, ...}, period_days: N}
    """
    if isinstance(start_time, str):
        start_time = pd.to_datetime(start_time)
    if isinstance(end_time, str):
        end_time = pd.to_datetime(end_time)

    interval = AGG_INTERVALS.get(aggregation)
    period_days = (end_time - start_time).days or 1

    result_data: dict = {}
    total_points = 0

    for pk in parameter_keys:
        with get_session() as session:
            rows = (
                session.query(
                    TimeSeriesPoint.timestamp,
                    TimeSeriesPoint.value,
                )
                .filter(
                    TimeSeriesPoint.unit_id == unit_id,
                    TimeSeriesPoint.parameter_key == pk,
                    TimeSeriesPoint.timestamp >= start_time,
                    TimeSeriesPoint.timestamp <= end_time,
                )
                .order_by(TimeSeriesPoint.timestamp)
                .all()
            )

        if not rows:
            result_data[pk] = {"timestamp": [], "values": []}
            continue

        total_points += len(rows)

        # 单参数 DataFrame → 聚合降采样
        df = pd.DataFrame(rows, columns=["timestamp", "value"])
        df.set_index("timestamp", inplace=True)

        if interval:
            df = df.resample(interval).mean()

        timestamps = [
            ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
            for ts in df.index.tolist()
        ]
        values = [None if pd.isna(v) else round(float(v), 4) for v in df["value"].tolist()]

        result_data[pk] = {"timestamp": timestamps, "values": values}

    return {
        "data": result_data,
        "period_days": period_days,
        "point_count": total_points,
    }


def get_parameter_stats(
    parameter_key: str,
    start_time: str | datetime,
    end_time: str | datetime,
    unit_id: str = "GT-01",
) -> dict:
    """获取单个参数在时间范围内的统计摘要。"""
    if isinstance(start_time, str):
        start_time = pd.to_datetime(start_time)
    if isinstance(end_time, str):
        end_time = pd.to_datetime(end_time)

    with get_session() as session:
        # 获取参数信息
        param = session.query(Parameter).filter(Parameter.key == parameter_key).first()

        # 统计查询
        result = session.query(
            func.count(TimeSeriesPoint.id).label("count"),
            func.avg(TimeSeriesPoint.value).label("mean"),
            func.min(TimeSeriesPoint.value).label("min_val"),
            func.max(TimeSeriesPoint.value).label("max_val"),
        ).filter(
            TimeSeriesPoint.unit_id == unit_id,
            TimeSeriesPoint.parameter_key == parameter_key,
            TimeSeriesPoint.timestamp >= start_time,
            TimeSeriesPoint.timestamp <= end_time,
        ).first()

        if result.count == 0:
            return {"has_data": False, "parameter_key": parameter_key}

        # 标准差需要用原始数据算
        rows = session.query(TimeSeriesPoint.value).filter(
            TimeSeriesPoint.unit_id == unit_id,
            TimeSeriesPoint.parameter_key == parameter_key,
            TimeSeriesPoint.timestamp >= start_time,
            TimeSeriesPoint.timestamp <= end_time,
        ).all()
        values = pd.Series([r[0] for r in rows])

        return {
            "has_data": True,
            "parameter_key": parameter_key,
            "parameter_name": param.name if param else parameter_key,
            "unit": param.unit if param else "",
            "count": int(result.count),
            "mean": round(float(result.mean), 4) if result.mean else None,
            "std": round(float(values.std()), 4) if len(values) > 1 else 0,
            "min": round(float(result.min_val), 4) if result.min_val else None,
            "max": round(float(result.max_val), 4) if result.max_val else None,
            "normal_min": param.normal_min if param else None,
            "normal_max": param.normal_max if param else None,
            "out_of_range_count": int(((values < (param.normal_min or -999999)) | (values > (param.normal_max or 999999))).sum()) if param and param.normal_min is not None else 0,
        }


def get_multi_parameter_stats(
    parameter_keys: list[str],
    start_time: str | datetime,
    end_time: str | datetime,
    unit_id: str = "GT-01",
) -> list[dict]:
    """批量获取多个参数的统计摘要。"""
    return [
        get_parameter_stats(key, start_time, end_time, unit_id)
        for key in parameter_keys
    ]


def get_latest_values(unit_id: str = "GT-01") -> dict:
    """获取每个参数的最新值（用于实时监控 real 模式）。"""
    with get_session() as session:
        # 子查询: 每个参数的最新时间戳
        subq = (
            session.query(
                TimeSeriesPoint.parameter_key,
                func.max(TimeSeriesPoint.timestamp).label("latest_ts"),
            )
            .filter(TimeSeriesPoint.unit_id == unit_id)
            .group_by(TimeSeriesPoint.parameter_key)
            .subquery()
        )

        # 关联获取实际值
        rows = (
            session.query(TimeSeriesPoint)
            .join(
                subq,
                (TimeSeriesPoint.parameter_key == subq.c.parameter_key)
                & (TimeSeriesPoint.timestamp == subq.c.latest_ts),
            )
            .filter(TimeSeriesPoint.unit_id == unit_id)
            .all()
        )

        result = {}
        for r in rows:
            result[r.parameter_key] = {
                "value": r.value,
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                "quality": r.quality,
            }

        return result


def get_parameter_trend(
    parameter_key: str,
    days: int = 7,
    unit_id: str = "GT-01",
) -> dict:
    """获取单参数趋势（兼容现有 monitoring API 格式）。"""
    end_time = datetime.now()
    start_time = end_time - pd.Timedelta(days=days)

    with get_session() as session:
        rows = (
            session.query(TimeSeriesPoint.timestamp, TimeSeriesPoint.value)
            .filter(
                TimeSeriesPoint.unit_id == unit_id,
                TimeSeriesPoint.parameter_key == parameter_key,
                TimeSeriesPoint.timestamp >= start_time,
                TimeSeriesPoint.timestamp <= end_time,
            )
            .order_by(TimeSeriesPoint.timestamp)
            .all()
        )

    if not rows:
        return {"data": {"timestamp": [], parameter_key: []}, "period_days": days}

    df = pd.DataFrame(rows, columns=["timestamp", "value"])
    return {
        "data": {
            "timestamp": [ts.isoformat() for ts in df["timestamp"].tolist()],
            parameter_key: [round(v, 4) for v in df["value"].tolist()],
        },
        "period_days": days,
    }


def get_parameter_latest_value(parameter_key: str, unit_id: str = "GT-01") -> float | None:
    """获取单个参数的最新时序值。"""
    with get_session() as session:
        row = (
            session.query(TimeSeriesPoint.value)
            .filter(
                TimeSeriesPoint.unit_id == unit_id,
                TimeSeriesPoint.parameter_key == parameter_key,
            )
            .order_by(TimeSeriesPoint.timestamp.desc())
            .first()
        )
        return float(row[0]) if row else None


def get_parameter_aggregated_value(
    parameter_key: str,
    aggregation: str = "raw",
    unit_id: str = "GT-01",
) -> float | None:
    """获取参数的聚合值。

    - raw: 最新一条时序值
    - 1d:  最近1天的均值
    - 1w:  最近1周的均值
    """
    if aggregation == "raw":
        return get_parameter_latest_value(parameter_key, unit_id)

    # 计算时间窗口
    agg_days = {"1d": 1, "1w": 7}
    days = agg_days.get(aggregation, 1)
    end_time = datetime.now()
    start_time = end_time - pd.Timedelta(days=days)

    with get_session() as session:
        result = session.query(
            func.avg(TimeSeriesPoint.value).label("mean_val"),
        ).filter(
            TimeSeriesPoint.unit_id == unit_id,
            TimeSeriesPoint.parameter_key == parameter_key,
            TimeSeriesPoint.timestamp >= start_time,
            TimeSeriesPoint.timestamp <= end_time,
        ).first()

        return round(float(result.mean_val), 4) if result and result.mean_val is not None else None
