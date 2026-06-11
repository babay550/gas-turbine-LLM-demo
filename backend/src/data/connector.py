"""数据连接器 — 统一数据访问接口。

根据 config.data_mode 切换 mock/real 数据源。
上层调用方无需变动。
"""

import logging
from datetime import datetime

from src.config import get_settings

logger = logging.getLogger(__name__)


def _is_real_mode() -> bool:
    return get_settings().data_mode == "real"


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
    """调用耗差分析小模型。"""
    from src.data.mock_data import generate_loss_analysis
    return generate_loss_analysis()


def get_benchmark_analysis() -> dict:
    """调用对标分析小模型。"""
    from src.data.mock_data import generate_benchmark_analysis
    return generate_benchmark_analysis()


def get_period_loss_analysis(parameter_keys: list[str], start: str, end: str, unit_id: str = "GT-01") -> dict:
    """基于时间段历史数据生成耗差分析结果。"""
    if _is_real_mode():
        return _get_period_loss_from_db(parameter_keys, start, end, unit_id)
    return _get_period_loss_mock(parameter_keys, start, end, unit_id)


def _get_period_loss_mock(parameter_keys: list[str], start: str, end: str, unit_id: str) -> dict:
    from src.data.mock_data import generate_period_loss_analysis
    return generate_period_loss_analysis(parameter_keys, start, end, unit_id)


def _get_period_loss_from_db(parameter_keys: list[str], start: str, end: str, unit_id: str) -> dict:
    """从数据库查询指定时间段的参数统计，生成耗差分析。

    逻辑：
    1. 读取 LossVariableConfig 获取已配置损失项的基准值/最优值
    2. 对每个选中的参数，取时间段内的真实均值作为当前值
    3. 如果参数在 LossVariableConfig 中有配置，使用配置的 baseline/best
    4. 如果参数没有配置，从 Parameter 表获取正常范围作为参考
    """
    try:
        from src.services.query_service import get_multi_parameter_stats
        from src.db.engine import get_session
        from src.db.models import Parameter, LossVariableConfig

        stats = get_multi_parameter_stats(parameter_keys, start, end, unit_id)

        with get_session() as session:
            params = session.query(Parameter).all()
            param_map = {p.key: p for p in params}
            loss_configs = session.query(LossVariableConfig).all()
            loss_config_map = {c.param_key: c for c in loss_configs}

        items = []
        for s in stats:
            if not s.get("has_data", True):
                continue
            pk = s.get("parameter_key", "")
            p = param_map.get(pk)
            cfg = loss_config_map.get(pk)
            mean_val = s.get("mean") or 0

            if cfg:
                # 有损失项配置 → 使用配置的 baseline/best，真实均值作为当前值
                name = cfg.name
                unit = cfg.unit
                baseline = cfg.baseline
                best = cfg.best
            else:
                # 无配置 → 使用参数字典信息
                name = p.name if p else pk
                unit = p.unit if p else ""
                # 基准值用正常范围中点，最优值用正常范围上限（代表理想状态）
                if p and p.normal_min is not None and p.normal_max is not None:
                    baseline = round((p.normal_min + p.normal_max) / 2, 4)
                    best = round(p.normal_max, 4)
                else:
                    baseline = round(mean_val, 4)
                    best = round(mean_val * 0.95, 4)

            items.append({
                "name": name,
                "value": round(mean_val, 4),
                "design": round(baseline, 4),
                "best": round(best, 4),
                "unit": unit,
                "param_key": pk,
            })

        total_loss = round(sum(i["value"] for i in items), 4)
        total_design = round(sum(i["design"] for i in items), 4)
        total_best = round(sum(i["best"] for i in items), 4)

        return {
            "analysis_time": datetime.now().isoformat(),
            "unit_id": unit_id,
            "period": {"start": start, "end": end},
            "total_loss": total_loss,
            "total_design_loss": total_design,
            "total_best_loss": total_best,
            "items": items,
            "major_losses": sorted(
                [i for i in items if i["value"] > i["design"] * 1.2],
                key=lambda x: x["value"] - x["design"],
                reverse=True,
            ),
        }
    except Exception as e:
        logger.error("从数据库获取时段耗差分析失败，回退 mock: %s", e)
        return _get_period_loss_mock(parameter_keys, start, end, unit_id)
