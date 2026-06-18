"""数据连接器 — 统一数据访问接口。

根据 config.data_mode 切换 mock/real 数据源。
上层调用方无需变动。
"""

import logging
from datetime import datetime

from src.config import get_settings

logger = logging.getLogger(__name__)

# ── 调试用：运行时 mock 覆盖（不写入配置，重启后失效） ──
_mock_override: bool | None = None  # None=跟随配置, True=强制mock, False=强制real


def set_mock_override(force_mock: bool | None) -> None:
    """设置运行时 mock 覆盖。

    - True  → 所有数据源强制返回 mock
    - False → 所有数据源强制走 real
    - None  → 恢复跟随 config.data_mode
    """
    global _mock_override
    _mock_override = force_mock


def get_mock_override() -> bool | None:
    return _mock_override


def is_mock_active() -> bool:
    """当前是否使用 mock 数据（综合配置 + 运行时覆盖）。"""
    if _mock_override is not None:
        return _mock_override
    return get_settings().data_mode != "real"


def _is_real_mode() -> bool:
    return not is_mock_active()


# ──────────── 实时数据 ────────────

def get_realtime_data() -> dict:
    """获取燃气轮机实时监测数据。"""
    if _is_real_mode():
        return _get_realtime_from_db()
    return _get_realtime_mock()


def _get_realtime_mock() -> dict:
    from src.data.mock_data import generate_realtime_data
    return generate_realtime_data()


def _get_realtime_from_db() -> dict:
    """从 SQLite 获取最新时序数据，组装为与 mock 相同格式。"""
    try:
        from src.services.query_service import get_latest_values
        from src.db.engine import get_session
        from src.db.models import Parameter

        latest = get_latest_values()

        if not latest:
            logger.warning("数据库无时序数据，回退 mock")
            return _get_realtime_mock()

        # 组装 parameters dict
        parameters = {}
        now = datetime.now()

        with get_session() as session:
            params = session.query(Parameter).all()
            for p in params:
                if p.key in latest:
                    parameters[p.key] = latest[p.key]["value"]
                elif p.name in latest:
                    parameters[p.name] = latest[p.name]["value"]

        # 取第一个时间戳作为全局 timestamp
        ts = next((v["timestamp"] for v in latest.values() if v.get("timestamp")), now.isoformat())

        return {
            "timestamp": ts,
            "unit_id": "GT-01",
            "parameters": parameters,
            "status": "正常运行",
            "warnings": [],
        }
    except Exception as e:
        logger.error("从数据库获取实时数据失败，回退 mock: %s", e)
        return _get_realtime_mock()


# ──────────── 能效趋势 ────────────

def get_efficiency_trend(days: int = 7) -> dict:
    """获取能效指标趋势数据。"""
    if _is_real_mode():
        return _get_trend_from_db(days)
    return _get_trend_mock(days)


def _get_trend_mock(days: int) -> dict:
    from src.data.mock_data import generate_efficiency_trend
    df = generate_efficiency_trend(days)
    return {"data": df.to_dict(orient="list"), "period_days": days}


def _get_trend_from_db(days: int) -> dict:
    """从数据库查询效率趋势。"""
    try:
        from src.services.query_service import query_time_series
        import pandas as pd

        keys = ["热耗率_kJ/kWh", "发电效率_%", "厂用电率_%", "综合厂用电率_%"]
        end = datetime.now()
        start = end - __import__("datetime").timedelta(days=days)

        result = query_time_series(keys, start.isoformat(), end.isoformat(), aggregation="1h")
        if result.get("point_count", 0) == 0:
            logger.warning("数据库无趋势数据，回退 mock")
            return _get_trend_mock(days)

        # 新格式：每个参数独立 {timestamp: [], values: []}
        # 需要转为扁平共享格式：{日期: [...], 热耗率_kJ/kWh: [...], ...}
        data = result.get("data", {})
        per_param_dfs = []
        for pk in keys:
            param_data = data.get(pk, {})
            ts_list = param_data.get("timestamp", [])
            val_list = param_data.get("values", [])
            if ts_list:
                df_param = pd.DataFrame({"日期": ts_list, pk: val_list})
                df_param.set_index("日期", inplace=True)
                per_param_dfs.append(df_param)

        if not per_param_dfs:
            return _get_trend_mock(days)

        # 合并所有参数到一个 DataFrame（按时间对齐）
        merged = per_param_dfs[0]
        for df in per_param_dfs[1:]:
            merged = merged.join(df, how="outer")

        merged = merged.reset_index()
        flat_data = {}
        flat_data["日期"] = merged["日期"].tolist()
        for pk in keys:
            if pk in merged.columns:
                flat_data[pk] = [None if pd.isna(v) else round(float(v), 4) for v in merged[pk].tolist()]
            else:
                flat_data[pk] = []

        return {"data": flat_data, "period_days": days}
    except Exception as e:
        logger.error("从数据库获取趋势失败，回退 mock: %s", e)
    return _get_trend_mock(days)


# ──────────── 分析功能（暂不切换，保持 mock） ────────────

def get_efficiency_analysis() -> dict:
    """调用能效分析小模型。"""
    from src.data.mock_data import generate_efficiency_analysis
    return generate_efficiency_analysis()


def get_loss_analysis() -> dict:
    """耗差分析：基于系统上报的 coalLossValue 做偏差分解（实时取最新点）。

    force-mock 模式回退 mock_data；否则转发 loss_analysis_tool.run_loss_analysis。
    """
    if _is_real_mode():
        from src.tools.loss_analysis_tool import run_loss_analysis
        return run_loss_analysis("GT-01")
    from src.data.mock_data import generate_loss_analysis
    return generate_loss_analysis()


def get_benchmark_analysis() -> dict:
    """调用对标分析小模型。"""
    from src.data.mock_data import generate_benchmark_analysis
    return generate_benchmark_analysis()

