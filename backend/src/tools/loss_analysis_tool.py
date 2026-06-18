"""耗差分析工具 — 基于系统上报的已算好 coalLossValue 做偏差分解与传递分析。

核心定位：
  系统上报的时序数据已自带各参数/子系统的耗差值，本工具不再自行计算耗差，
  而是直接读取这些已算好的损失项，沿 LOSS_HIERARCHY
  （能耗偏差 → 燃机效率 / 余热锅炉效率 / 汽机效率 → 各下属因素）
  做偏差分解与传递分析，定位核心影响子系统与参数。

历史分析与实时分析共用同一套分解逻辑，区别仅在取值方式：
  - 历史分析：对所选时段的时序求均值
  - 实时分析：取最新时间点的值

数据契约（tsd_time_series.parameter_key 命名约定）：
  {name}_coalLossValue     对标基准耗差 (g/kWh) — 核心输入，系统已算好
  {name}_optimalLossValue  对标最优耗差 (g/kWh)
  {name}_value             运行过程值
  {name}_referValue        基准参考值
  其中 name ∈ {能耗偏差(总量), 燃机效率/余热锅炉效率/汽机效率(子系统), 各因素}
"""

import json
import time
import logging
from datetime import datetime

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# ──────────────────── 耗差分层结构 ────────────────────
# 能耗偏差 = 燃机效率 + 余热锅炉效率 + 汽机效率
# 每个子系统效率耗差由其下属因素耗差影响决定（非绝对求和，存在交叉耦合）。
# 因素名需与 tsd_time_series 的 parameter_key 前缀一致；缺失因素自动跳过。
LOSS_HIERARCHY: dict[str, list[str]] = {
    "燃机效率": [
        "压气机效率", "压气机进气压损", "燃机排气压力",
        "环境温度", "大气压力", "大气相对湿度",
    ],
    "余热锅炉效率": [
        "余热锅炉烟气压损", "余热锅炉排烟温度",
    ],
    "汽机效率": [
        "汽机高压主蒸汽压力", "汽机高压主蒸汽温度", "凝汽器压力",
        "高压缸效率", "再热蒸汽压损", "再热蒸汽温度", "过冷度",
    ],
}

TOTAL_NAME = "能耗偏差"

# 时序 parameter_key 后缀 → 字段名
LOSS_SUFFIX = {
    "coalLossValue": "_coalLossValue",
    "optimalLossValue": "_optimalLossValue",
    "value": "_value",
    "referValue": "_referValue",
}

# ──────────────────── 负荷率三区间策略 ────────────────────
# 调峰机组按负荷率分区采用不同分析策略；数据无负荷率/功率参数时整体分析。
RATED_POWER_MW = 200  # F 级燃机典型额定功率 (MW)，用于由功率反算负荷率
ZONE1_THRESHOLD = 10  # 极低负荷阈值 (%) — 该区间数据舍去不分析
ZONE2_THRESHOLD = 60  # 中低负荷阈值 (%)

# 识别负荷率/功率的参数 key（优先级从高到低）
_LOAD_RATE_PARAM_KEYS = ["负荷率", "负荷"]
_POWER_PARAM_KEYS = ["发电机有功功率", "有功功率", "发电功率", "汽机发电功率"]


# ──────────────────── 取值（纯内存） ────────────────────

def _pick_loss(value_map: dict, name: str) -> dict:
    """从扁平 {key: value} map 按 {name}_<suffix> 规则取一个节点的损失四元组。

    缺失字段为 None；coalLossValue 为 None 视为该节点无有效耗差数据。
    """
    return {
        "coalLossValue": value_map.get(f"{name}{LOSS_SUFFIX['coalLossValue']}"),
        "optimalLossValue": value_map.get(f"{name}{LOSS_SUFFIX['optimalLossValue']}"),
        "value": value_map.get(f"{name}{LOSS_SUFFIX['value']}"),
        "referValue": value_map.get(f"{name}{LOSS_SUFFIX['referValue']}"),
    }


def _pct(numerator: float | None, denominator: float) -> float:
    """绝对值权重占比 (%)：体现影响权重（与正负方向无关），分母为 0 返回 0。

    coalLossValue 可正可负，简单 coal/sum 在有正有负时失真；改用 |x|/Σ|x|
    让"核心影响"由绝对值决定，方向由 coalLossValue 正负独立体现。
    """
    if denominator == 0 or numerator is None:
        return 0.0
    return round(abs(numerator) / abs(denominator) * 100, 1)


def _round(v, ndigits=4):
    return None if v is None else round(float(v), ndigits)


# ──────────────────── 偏差分解 ────────────────────

def _build_decomposition(value_map: dict, mode: str = "coal") -> dict:
    """基于扁平 {key: value}（时段均值或最新点）构建偏差分解树 + 因素排名 + 报告。

    mode 决定评估模式：coal=对标基准（coalLossValue）、optimal=对标最优（optimalLossValue）。
    所有分析决策（排序、贡献、增耗判断）统一使用 mode 对应值，coalLossValue 与
    optimalLossValue 不混用；两值都保留在输出中供查看。
    纯内存计算，无 IO。贡献用绝对值权重（|x|/Σ|x|），方向由主值正负体现。
    """
    main_field = "coalLossValue" if mode == "coal" else "optimalLossValue"

    total = _pick_loss(value_map, TOTAL_NAME)

    subsystems_out: list[dict] = []
    factor_ranking: list[dict] = []

    for sub_name, factor_names in LOSS_HIERARCHY.items():
        sub = _pick_loss(value_map, sub_name)

        factors_out: list[dict] = []
        factors_abs_sum = 0.0  # 子系统内有数据因素的 |主值| 之和
        for fname in factor_names:
            fac = _pick_loss(value_map, fname)
            fmain = fac[main_field]
            if fmain is None:
                continue  # 该因素在当前模式下无耗差数据，跳过
            factors_abs_sum += abs(fmain)
            factors_out.append({"name": fname, "main_value": _round(fmain), **fac})
            factor_ranking.append({
                "name": fname,
                "coalLossValue": _round(fac["coalLossValue"]),
                "optimalLossValue": _round(fac["optimalLossValue"]),
                "main_value": _round(fmain),
                "value": _round(fac["value"]),
                "referValue": _round(fac["referValue"]),
                "subsystem": sub_name,
            })

        # 子系统主值：优先用系统上报值；缺失则用下属因素之和
        eff_sub_main = sub[main_field]
        if eff_sub_main is None and factors_out:
            eff_sub_main = round(sum(f[main_field] for f in factors_out), 4)

        subsystems_out.append({
            "name": sub_name,
            "coalLossValue": _round(sub["coalLossValue"]),
            "optimalLossValue": _round(sub["optimalLossValue"]),
            "value": _round(sub["value"]),
            "referValue": _round(sub["referValue"]),
            "main_value": _round(eff_sub_main),
            "factors": factors_out,
            "factor_count": len(factors_out),
            "_factors_abs_sum": factors_abs_sum,
            "_abs": abs(eff_sub_main) if eff_sub_main is not None else 0.0,
        })

    # contribution：绝对值权重（按当前模式主值）
    subs_abs_total = sum(s["_abs"] for s in subsystems_out)
    for s in subsystems_out:
        s["contribution_to_total"] = _pct(s["_abs"], subs_abs_total)
        for f in s["factors"]:
            f["contribution_to_subsystem"] = _pct(f[main_field], s["_factors_abs_sum"])
        s["factors"].sort(key=lambda x: abs(x[main_field]), reverse=True)
        s.pop("_factors_abs_sum", None)
        s.pop("_abs", None)

    subsystems_out.sort(key=lambda x: abs(x["main_value"] or 0), reverse=True)
    factor_ranking.sort(key=lambda x: abs(x[main_field] or 0), reverse=True)

    total_out = {"name": TOTAL_NAME, **{k: _round(v) for k, v in total.items()}}
    total_out["main_value"] = _round(total[main_field])

    return {
        "eval_mode": mode,
        "main_field": main_field,
        "total": total_out,
        "subsystems": subsystems_out,
        "factor_ranking": factor_ranking,
        "key_findings": _derive_findings(total_out, subsystems_out, factor_ranking, main_field, mode),
        "report": _build_report(total_out, subsystems_out, factor_ranking, main_field, mode),
        "suggestions": _build_suggestions(subsystems_out, factor_ranking, main_field),
    }


def _derive_findings(total: dict, subsystems: list[dict], factor_ranking: list[dict],
                     main_field: str, mode: str) -> list[str]:
    mode_label = "对标基准" if mode == "coal" else "对标最优"
    findings: list[str] = []
    tmain = total.get("main_value")
    if tmain is None:
        findings.append(f"所选数据未包含有效的 {main_field} 耗差项，无法做偏差分解。")
        return findings

    findings.append(f"综合能耗偏差（{mode_label}）{tmain} g/kWh")
    if subsystems and subsystems[0].get("main_value") is not None:
        s0 = subsystems[0]
        findings.append(f"影响最大的子系统为「{s0['name']}」"
                        f"（{mode_label} {s0['main_value']} g/kWh，权重 {s0['contribution_to_total']}%）")
    if factor_ranking:
        f0 = factor_ranking[0]
        fval = f0.get(main_field)
        if fval is not None:
            findings.append(f"影响最大的因素为「{f0['name']}」"
                            f"（{mode_label} {fval} g/kWh，归属 {f0['subsystem']}）")
    return findings


def _build_report(total: dict, subsystems: list[dict], factor_ranking: list[dict],
                  main_field: str, mode: str) -> str:
    mode_label = "对标基准" if mode == "coal" else "对标最优"
    tmain = total.get("main_value")
    if tmain is None:
        return (
            f"【偏差分解与传递分析（{mode_label}）】\n"
            f"所选时段/数据点未包含有效的 {main_field} 耗差值，无法执行偏差分解。\n"
            f"请确认上传数据包含 {{因素}}_{main_field} 时序项。"
        )

    lines = [f"【偏差分解与传递分析（{mode_label}）】"]
    lines.append(f"综合能耗偏差（{mode_label}）{tmain} g/kWh。\n")
    lines.append("── 子系统贡献分解 ──")
    for s in subsystems:
        if not s.get("main_value"):
            continue
        lines.append(f"  {s['name']}：{s['main_value']} g/kWh（权重 {s['contribution_to_total']}%）")
        for f in s["factors"][:3]:
            lines.append(f"    └ {f['name']}：{f[main_field]} g/kWh（本子系统权重 {f['contribution_to_subsystem']}%）")
    lines.append(f"\n── 因素耗差排名（{mode_label}，Top 5）──")
    for f in factor_ranking[:5]:
        lines.append(f"  {f['name']}（{f['subsystem']}）：{f[main_field]} g/kWh")
    return "\n".join(lines)


def _build_suggestions(subsystems: list[dict], factor_ranking: list[dict], main_field: str) -> list[str]:
    """优化/检修建议只针对增耗（main_field > 0）项；降耗项不作为问题。"""
    suggestions: list[str] = []
    pos_factors = [f for f in factor_ranking if f[main_field] and f[main_field] > 0]
    if pos_factors:
        top = pos_factors[0]
        suggestions.append(
            f"[优化] 增耗最大的因素「{top['name']}」"
            f"（{top[main_field]} g/kWh，归属 {top['subsystem']}），"
            "建议优先排查其运行工况与设备状态。"
        )
    for s in subsystems:
        if (s.get("main_value") or 0) > 0:
            pos_in_sub = [f for f in s["factors"] if f[main_field] and f[main_field] > 0]
            if pos_in_sub:
                suggestions.append(
                    f"[检修] 「{s['name']}」子系统整体增耗（{s['main_value']} g/kWh），"
                    f"其中增耗因素「{pos_in_sub[0]['name']}」（{pos_in_sub[0][main_field]} g/kWh）值得关注，"
                    "建议检查相关设备并安排维护。"
                )
    if not suggestions:
        suggestions.append("各项因素以降耗为主，机组运行状态良好，建议保持当前工况。")
    return suggestions


# ──────────────────── 三区间报告合成 ────────────────────

def _build_zoned_findings(zone_distribution: dict, zones: dict, mode: str) -> list[str]:
    main_field = "coalLossValue" if mode == "coal" else "optimalLossValue"
    mode_label = "对标基准" if mode == "coal" else "对标最优"
    findings: list[str] = []
    labels = {
        1: ("极低负荷区间（<10%）", "已舍去不分析"),
        2: ("部分负荷区间（10%~60%）", "耗差固有偏高，关注异常偏高项"),
        3: ("高负荷区间（>60%）", "已做详细偏差传递分析"),
    }
    for zid in (1, 2, 3):
        zd = zone_distribution.get(f"zone{zid}", {})
        cnt = zd.get("count", 0)
        if cnt == 0:
            continue
        name, action = labels[zid]
        findings.append(f"{name}：{cnt} 个点（{zd.get('ratio', 0)}%），平均负荷率 {zd.get('avg_load_rate', 0)}%，{action}。")
    for zid in (3, 2):
        z = zones.get(f"zone{zid}", {})
        total = z.get("total") or {}
        if total.get("main_value") is not None:
            findings.append(f"zone{zid} 综合能耗偏差（{mode_label}）{total['main_value']} g/kWh。")
            ranking = z.get("factor_ranking") or []
            if ranking:
                f0 = ranking[0]
                findings.append(f"zone{zid} 影响最大的因素「{f0['name']}」（{mode_label} {f0.get(main_field)} g/kWh）。")
            break
    return findings


def _build_zoned_report(zone_distribution: dict, zones: dict, start: str, end: str, mode: str) -> str:
    main_field = "coalLossValue" if mode == "coal" else "optimalLossValue"
    mode_label = "对标基准" if mode == "coal" else "对标最优"
    lines = [f"【偏差分解与传递分析（{mode_label}，按负荷率三区间）】时段 {start} ~ {end}"]
    labels = {1: "极低负荷（<10%，已舍去）", 2: "部分负荷（10%~60%）", 3: "高负荷（>60%）"}
    for zid in (1, 2, 3):
        zd = zone_distribution.get(f"zone{zid}", {})
        cnt = zd.get("count", 0)
        if cnt == 0:
            continue
        lines.append(f"\n── {labels[zid]}：{cnt} 个点（{zd.get('ratio', 0)}%），平均负荷率 {zd.get('avg_load_rate', 0)}% ──")
        z = zones.get(f"zone{zid}", {})
        if zid == 1:
            lines.append("  负荷率过低，热力参数波动大，耗差无参考价值，已舍去。")
            continue
        total = z.get("total") or {}
        if total.get("main_value") is None:
            lines.append(f"  无有效 {main_field} 数据。")
            continue
        if zid == 2:
            lines.append("  注：部分负荷下耗差固有偏高，以下仅作异常偏高项参考。")
        lines.append(f"  综合能耗偏差（{mode_label}）{total['main_value']} g/kWh。")
        for s in (z.get("subsystems") or [])[:3]:
            if not s.get("main_value"):
                continue
            lines.append(f"    · {s['name']}：{s['main_value']} g/kWh（权重 {s['contribution_to_total']}%）")
        for f in (z.get("factor_ranking") or [])[:3]:
            lines.append(f"      └ {f['name']}：{f.get(main_field)} g/kWh")
    return "\n".join(lines)


def _build_zoned_suggestions(zones: dict, mode: str) -> list[str]:
    main_field = "coalLossValue" if mode == "coal" else "optimalLossValue"
    suggestions: list[str] = []
    for zid in (3, 2):
        z = zones.get(f"zone{zid}", {})
        total = z.get("total") or {}
        if total.get("main_value") is None:
            continue
        tag = "高负荷" if zid == 3 else "部分负荷"
        for s in z.get("subsystems") or []:
            if (s.get("main_value") or 0) > 0:
                pos_in_sub = [f for f in s["factors"] if f.get(main_field) and f[main_field] > 0]
                if pos_in_sub:
                    suggestions.append(
                        f"[检修-{tag}] 「{s['name']}」子系统增耗（{s['main_value']} g/kWh），"
                        f"增耗因素「{pos_in_sub[0]['name']}」（{pos_in_sub[0][main_field]} g/kWh）值得关注。"
                    )
        pos = [f for f in (z.get("factor_ranking") or []) if f.get(main_field) and f[main_field] > 0]
        if pos:
            suggestions.append(
                f"[优化-{tag}] 异常偏高因素「{pos[0]['name']}」（{pos[0][main_field]} g/kWh），"
                + ("结合部分负荷特性评估是否需调整。" if zid == 2 else "建议优先排查其运行工况与设备状态。")
            )
    if not suggestions:
        suggestions.append("各区间未见显著增耗，建议保持当前运行工况。")
    return suggestions


# ──────────────────── 时序取值（IO） ────────────────────

def _query_loss_values_for_period(start: str, end: str, unit_id: str = "GT-01") -> tuple[dict, int]:
    """一条聚合查询：时段内各 parameter_key 的均值 + 去重时间点数。

    Returns: ({parameter_key: mean_value}, distinct_point_count)
    """
    import pandas as pd
    from sqlalchemy import func
    from src.db.engine import get_session
    from src.db.models import TimeSeriesPoint

    start_dt = pd.to_datetime(start)
    end_dt = pd.to_datetime(end)

    try:
        with get_session() as session:
            point_count = session.query(
                func.count(func.distinct(TimeSeriesPoint.timestamp))
            ).filter(
                TimeSeriesPoint.unit_id == unit_id,
                TimeSeriesPoint.timestamp >= start_dt,
                TimeSeriesPoint.timestamp <= end_dt,
            ).scalar() or 0

            rows = session.query(
                TimeSeriesPoint.parameter_key,
                func.avg(TimeSeriesPoint.value),
            ).filter(
                TimeSeriesPoint.unit_id == unit_id,
                TimeSeriesPoint.timestamp >= start_dt,
                TimeSeriesPoint.timestamp <= end_dt,
            ).group_by(TimeSeriesPoint.parameter_key).all()

            value_map = {r[0]: round(float(r[1]), 6) for r in rows if r[1] is not None}
            return value_map, int(point_count)
    except Exception as e:
        logger.warning("查询时段耗差均值失败: %s", e)
        return {}, 0


def _query_loss_values_latest(unit_id: str = "GT-01") -> dict:
    """取最新时间点所有 parameter_key 的值。"""
    from sqlalchemy import func
    from src.db.engine import get_session
    from src.db.models import TimeSeriesPoint

    try:
        with get_session() as session:
            latest_ts = session.query(
                func.max(TimeSeriesPoint.timestamp)
            ).filter(TimeSeriesPoint.unit_id == unit_id).scalar()

            if not latest_ts:
                return {}

            rows = session.query(
                TimeSeriesPoint.parameter_key,
                TimeSeriesPoint.value,
            ).filter(
                TimeSeriesPoint.unit_id == unit_id,
                TimeSeriesPoint.timestamp == latest_ts,
            ).all()

            return {r[0]: round(float(r[1]), 6) for r in rows if r[1] is not None}
    except Exception as e:
        logger.warning("查询最新耗差点失败: %s", e)
        return {}


def _query_loss_values_recent(unit_id: str = "GT-01", days: int = 1) -> dict:
    """取最近 days 天（相对数据最新时间点）各 parameter_key 的均值。

    用于实时分析的「按天/按周均值」聚合；raw 模式用 _query_loss_values_latest 取最新单点。
    """
    from datetime import timedelta
    from sqlalchemy import func
    from src.db.engine import get_session
    from src.db.models import TimeSeriesPoint

    try:
        with get_session() as session:
            latest = session.query(
                func.max(TimeSeriesPoint.timestamp)
            ).filter(TimeSeriesPoint.unit_id == unit_id).scalar()
            if not latest:
                return {}
            start = latest - timedelta(days=days)
            rows = session.query(
                TimeSeriesPoint.parameter_key,
                func.avg(TimeSeriesPoint.value),
            ).filter(
                TimeSeriesPoint.unit_id == unit_id,
                TimeSeriesPoint.timestamp >= start,
                TimeSeriesPoint.timestamp <= latest,
            ).group_by(TimeSeriesPoint.parameter_key).all()
            return {r[0]: round(float(r[1]), 6) for r in rows if r[1] is not None}
    except Exception as e:
        logger.warning("查询近期耗差均值失败: %s", e)
        return {}


# ──────────────────── 负荷率识别与三区间分区 ────────────────────

def _find_load_rate_param_key(unit_id: str = "GT-01") -> tuple[str, bool] | None:
    """识别负荷率/功率参数 key。

    Returns: (param_key, is_direct_load_rate)；is_direct=True 表示该参数本身即负荷率
    百分比，False 表示是功率参数需按 RATED_POWER_MW 反算。找不到返回 None。
    """
    try:
        from src.db.engine import get_session
        from src.db.models import Parameter

        with get_session() as session:
            params = session.query(Parameter).all()
            key_set = {p.key for p in params}
            name_to_key = {p.name: p.key for p in params}

            for cand in _LOAD_RATE_PARAM_KEYS:  # 优先：直接负荷率
                if cand in key_set:
                    return (cand, True)
                if cand in name_to_key:
                    return (name_to_key[cand], True)
            for cand in _POWER_PARAM_KEYS:  # 其次：功率参数反算
                if cand in key_set:
                    return (cand, False)
                if cand in name_to_key:
                    return (name_to_key[cand], False)
    except Exception as e:
        logger.warning("查找负荷率参数失败: %s", e)
    return None


def _query_series_points(start: str, end: str, unit_id: str = "GT-01") -> dict:
    """逐点查询时序 → {timestamp(datetime): {parameter_key: value}}。用于按负荷率分区。"""
    import pandas as pd
    from src.db.engine import get_session
    from src.db.models import TimeSeriesPoint

    start_dt = pd.to_datetime(start)
    end_dt = pd.to_datetime(end)
    points: dict = {}
    try:
        with get_session() as session:
            rows = (
                session.query(
                    TimeSeriesPoint.timestamp,
                    TimeSeriesPoint.parameter_key,
                    TimeSeriesPoint.value,
                )
                .filter(
                    TimeSeriesPoint.unit_id == unit_id,
                    TimeSeriesPoint.timestamp >= start_dt,
                    TimeSeriesPoint.timestamp <= end_dt,
                )
                .all()
            )
            for ts, pk, v in rows:
                if v is None:
                    continue
                points.setdefault(ts, {})[pk] = v
    except Exception as e:
        logger.warning("查询逐点时序失败: %s", e)
    return points


def _query_single_series(param_key: str, start: str, end: str, unit_id: str = "GT-01") -> dict:
    """查询单参数时序 → {timestamp(datetime): value}（轻量，用于负荷率探测）。"""
    import pandas as pd
    from src.db.engine import get_session
    from src.db.models import TimeSeriesPoint

    start_dt = pd.to_datetime(start)
    end_dt = pd.to_datetime(end)
    out: dict = {}
    try:
        with get_session() as session:
            rows = session.query(
                TimeSeriesPoint.timestamp, TimeSeriesPoint.value
            ).filter(
                TimeSeriesPoint.unit_id == unit_id,
                TimeSeriesPoint.parameter_key == param_key,
                TimeSeriesPoint.timestamp >= start_dt,
                TimeSeriesPoint.timestamp <= end_dt,
            ).all()
            for ts, v in rows:
                if v is not None:
                    out[ts] = v
    except Exception as e:
        logger.warning("查询单参数时序失败: %s", e)
    return out


def _classify_zone(load_rate: float) -> int:
    """按负荷率返回区间编号 1/2/3。"""
    if load_rate < ZONE1_THRESHOLD:
        return 1
    if load_rate <= ZONE2_THRESHOLD:
        return 2
    return 3


def _aggregate_points(points: dict, timestamps: list) -> dict:
    """对指定时间点集合，计算各 parameter_key 均值 → {key: mean}。"""
    ts_set = set(timestamps)
    sums: dict = {}
    counts: dict = {}
    for ts, kv in points.items():
        if ts not in ts_set:
            continue
        for k, v in kv.items():
            if v is None:
                continue
            sums[k] = sums.get(k, 0.0) + v
            counts[k] = counts.get(k, 0) + 1
    return {k: round(sums[k] / counts[k], 6) for k in sums if counts[k]}


# ──────────────────── 入口 ────────────────────

def run_historical_loss_analysis(
    start: str,
    end: str,
    unit_id: str = "GT-01",
    aggregation: str = "1h",
    mode: str = "coal",
) -> dict:
    """对已导入的历史数据执行偏差分解分析。

    mode 决定评估模式：coal=对标基准（coalLossValue）、optimal=对标最优（optimalLossValue）。
    策略：若数据含负荷率/功率参数，按负荷率三区间分别分析
    （<10% 舍去、10%~60% 关注异常偏高项、>60% 详细偏差传递）；
    否则对整个时段做整体分解。
    """
    start_time = time.monotonic()

    lr_info = _find_load_rate_param_key(unit_id)
    load_rates: dict = {}
    if lr_info:
        # 轻量探测：单查负荷率/功率时序，避免字典有定义但时序无数据时全表逐点扫描
        lr_key, is_direct = lr_info
        for ts, v in _query_single_series(lr_key, start, end, unit_id).items():
            if is_direct:
                if v >= 0:
                    load_rates[ts] = round(float(v), 1)
            elif v > 0 and RATED_POWER_MW > 0:
                load_rates[ts] = round(float(v) / RATED_POWER_MW * 100, 1)

    if not load_rates:
        # 无负荷率时序 → 整体分解（SQL 聚合，高效）
        value_map, point_count = _query_loss_values_for_period(start, end, unit_id)
        result = {
            "mode": "historical",
            "period": {"start": start, "end": end},
            "aggregation": aggregation,
            "zone_strategy": "overall",
            "total_data_points": point_count,
            **_build_decomposition(value_map, mode),
        }
        _finalize_result(result, unit_id, start_time)
        return result

    # 有负荷率时序 → 逐点查询全部时序 + 三区间分区
    points = _query_series_points(start, end, unit_id)

    zone_ts: dict = {1: [], 2: [], 3: []}
    zone_lr: dict = {1: [], 2: [], 3: []}
    for ts, lr in load_rates.items():
        zid = _classify_zone(lr)
        zone_ts[zid].append(ts)
        zone_lr[zid].append(lr)

    total_points = len(load_rates)
    zone_distribution: dict = {}
    for zid in (1, 2, 3):
        cnt = len(zone_ts[zid])
        zone_distribution[f"zone{zid}"] = {
            "count": cnt,
            "ratio": round(cnt / total_points * 100, 1) if total_points else 0,
            "avg_load_rate": round(sum(zone_lr[zid]) / cnt, 1) if cnt else 0,
        }

    zones: dict = {}
    primary: dict | None = None
    for zid in (1, 2, 3):
        ts_list = zone_ts[zid]
        zkey = f"zone{zid}"
        if zid == 1:
            zones[zkey] = {
                "zone_id": 1,
                "strategy": "skip",
                "point_count": len(ts_list),
                "message": "负荷率<10%，极低负荷/空载，耗差无参考价值，已舍去。",
            }
            continue
        if not ts_list:
            zones[zkey] = {"zone_id": zid, "strategy": "no_data", "point_count": 0}
            continue
        value_map = _aggregate_points(points, ts_list)
        decomp = _build_decomposition(value_map, mode)
        decomp["zone_id"] = zid
        decomp["strategy"] = "partial" if zid == 2 else "full"
        decomp["point_count"] = len(ts_list)
        decomp["avg_load_rate"] = zone_distribution[zkey]["avg_load_rate"]
        if zid == 2:
            decomp["note"] = "部分负荷区间，耗差固有偏高；关注异常偏高项的偏差传递。"
        zones[zkey] = decomp
        if zid == 3 or primary is None:
            primary = decomp  # zone3 优先作顶层展示，无 zone3 则用 zone2

    result = {
        "mode": "historical",
        "period": {"start": start, "end": end},
        "eval_mode": mode,
        "main_field": "coalLossValue" if mode == "coal" else "optimalLossValue",
        "aggregation": aggregation,
        "zone_strategy": "by_load_rate",
        "total_data_points": total_points,
        "zone_distribution": zone_distribution,
        "zones": zones,
        "total": (primary or {}).get("total", {}),
        "subsystems": (primary or {}).get("subsystems", []),
        "factor_ranking": (primary or {}).get("factor_ranking", []),
        "key_findings": _build_zoned_findings(zone_distribution, zones, mode),
        "report": _build_zoned_report(zone_distribution, zones, start, end, mode),
        "suggestions": _build_zoned_suggestions(zones, mode),
    }
    _finalize_result(result, unit_id, start_time)
    return result


def run_loss_analysis(unit_id: str = "GT-01", aggregation: str = "raw", mode: str = "coal") -> dict:
    """实时偏差分解分析。

    aggregation 决定取值方式：raw=最新单点、1d=最近1天均值、1w=最近1周均值。
    mode 决定评估模式：coal=对标基准、optimal=对标最优。
    """
    start_time = time.monotonic()
    if aggregation == "1d":
        value_map = _query_loss_values_recent(unit_id, 1)
    elif aggregation == "1w":
        value_map = _query_loss_values_recent(unit_id, 7)
    else:
        value_map = _query_loss_values_latest(unit_id)
    result = {
        "mode": "realtime",
        "aggregation": aggregation,
        "total_data_points": 1 if value_map else 0,
        **_build_decomposition(value_map, mode),
    }
    _finalize_result(result, unit_id, start_time)
    return result


def _finalize_result(result: dict, unit_id: str, start_time: float) -> None:
    """填充公共字段。"""
    result["analysis_time"] = datetime.now().isoformat()
    result["unit_id"] = unit_id
    result["elapsed_ms"] = round((time.monotonic() - start_time) * 1000)


# ──────────────────── LangChain Tool 注册 ────────────────────

@tool
def loss_analysis(
    unit_id: str = "GT-01",
    start: str = "",
    end: str = "",
    mode: str = "coal",
) -> str:
    """耗差分析：基于系统上报的已算好耗差值做偏差分解与传递分析。

    沿 能耗偏差 → 燃机效率 / 余热锅炉效率 / 汽机效率 → 各下属因素 的层级，
    量化各子系统与因素对总能耗偏差的贡献占比，定位核心影响因素。

    - mode='coal' → 对标基准（coalLossValue）；mode='optimal' → 对标最优（optimalLossValue）
    - 不传 start/end → 实时分析（取最新时序点）
    - 传入 start/end → 历史分析（按时段均值，含负荷率三区间策略）

    当用户提问涉及耗差分析、损失分析、能效偏差、煤耗偏差、偏差分解时使用此工具。

    Args:
        unit_id: 机组编号，默认 GT-01
        start: 开始时间（ISO 格式，如 "2026-06-01T00:00:00"），空则实时分析
        end: 结束时间（ISO 格式），空则实时分析
        mode: 评估模式，coal=对标基准 / optimal=对标最优，默认 coal
    """
    if start and end:
        result = run_historical_loss_analysis(start, end, unit_id, mode=mode)
    else:
        result = run_loss_analysis(unit_id, mode=mode)
    return json.dumps(result, ensure_ascii=False, indent=2)
