"""分析诊断 API — 能效分析、耗差分析、对标分析、根因诊断。"""

import logging

from fastapi import APIRouter, Request

from src.data.connector import get_efficiency_analysis, get_loss_analysis, get_benchmark_analysis, get_period_loss_analysis

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/efficiency")
async def run_efficiency_analysis(request: Request):
    """执行能效分析。"""
    result = get_efficiency_analysis()
    return {"tool": "efficiency_analysis", "result": result}


@router.post("/loss")
async def run_loss_analysis(request: Request):
    """执行耗差分析 — 从数据库读取配置项，取真实时序数据作为当前值。"""
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass

    aggregation = body.get("aggregation", "raw")  # raw / 1d / 1w

    return _build_loss_analysis(aggregation)


@router.post("/benchmark")
async def run_benchmark_analysis(request: Request):
    """执行对标分析。"""
    result = get_benchmark_analysis()
    return {"tool": "benchmark_analysis", "result": result}


@router.post("/root-cause")
async def run_root_cause_analysis(request: Request):
    """执行根因推理分析 — 异常检测 → 专家规则匹配 → 知识库检索 → 诊断建议。"""
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    query = body.get("query", "")
    from src.tools.root_cause_tool import run_root_cause_analysis
    return run_root_cause_analysis(query)


@router.post("/decomposition")
async def run_decomposition(request: Request):
    """执行逐级分解分析。"""
    # 基于耗差分析结果进行逐级分解
    loss_result = _build_loss_analysis("raw")
    loss_data = loss_result["result"]

    total_loss = loss_data["total_loss"]
    items = loss_data["items"]

    # 按子系统分组
    subsystems = {
        "压气机": {"contribution": 0, "components": []},
        "燃烧室": {"contribution": 0, "components": []},
        "透平": {"contribution": 0, "components": []},
        "其他": {"contribution": 0, "components": []},
    }

    for item in items:
        name = item["name"]
        placed = False
        for sub_name in ["压气机", "燃烧室", "透平"]:
            if sub_name in name:
                subsystems[sub_name]["contribution"] += item["current"]
                subsystems[sub_name]["components"].append({
                    "name": name,
                    "value": item["current"],
                    "design": item["baseline"],
                })
                placed = True
                break
        if not placed:
            subsystems["其他"]["contribution"] += item["current"]
            subsystems["其他"]["components"].append({
                "name": name,
                "value": item["current"],
                "design": item["baseline"],
            })

    # 移除空子系统
    subsystems = {k: v for k, v in subsystems.items() if v["contribution"] > 0 or v["components"]}

    return {
        "total_loss": total_loss,
        "total_design_loss": loss_data["total_baseline"],
        "subsystems": subsystems,
    }


@router.post("/period-loss")
async def run_period_loss_analysis(request: Request):
    """基于指定时间段的历史数据执行耗差分析。"""
    body = await request.json()
    parameter_keys = body.get("parameter_keys", [])
    start = body.get("start", "")
    end = body.get("end", "")
    unit_id = body.get("unit_id", "GT-01")

    if not parameter_keys:
        return {"tool": "period_loss_analysis", "error": "请至少选择一个参数"}
    if not start or not end:
        return {"tool": "period_loss_analysis", "error": "请指定时间范围"}

    result = get_period_loss_analysis(parameter_keys, start, end, unit_id)
    return {"tool": "period_loss_analysis", "result": result}


# ──────────── 内部函数 ────────────

def _build_loss_analysis(aggregation: str = "raw") -> dict:
    """从数据库构建耗差分析结果。

    1. 读取 LossVariableConfig 配置列表
    2. 每个配置项取真实时序当前值
    3. baseline/best 直接从配置读取
    """
    from datetime import datetime
    from src.db.engine import get_session
    from src.db.models import LossVariableConfig
    from src.services.query_service import get_parameter_aggregated_value

    with get_session() as session:
        configs = session.query(LossVariableConfig).order_by(
            LossVariableConfig.sort_order, LossVariableConfig.id
        ).all()

        if not configs:
            # 无配置时回退到 mock
            result = get_loss_analysis()
            return {"tool": "loss_analysis", "result": _adapt_mock_result(result)}

        items = []
        for cfg in configs:
            current = get_parameter_aggregated_value(cfg.param_key, aggregation)
            if current is None:
                # 无时序数据时用 mock 随机值
                import random
                current = round(cfg.baseline * (0.8 + random.random() * 0.8), 4)

            items.append({
                "name": cfg.name,
                "unit": cfg.unit,
                "param_key": cfg.param_key,
                "current": round(current, 4),
                "baseline": cfg.baseline,
                "best": cfg.best,
                "deltaBaseline": round(current - cfg.baseline, 4),
                "deltaBest": round(current - cfg.best, 4),
            })

        total_current = round(sum(i["current"] for i in items), 4)
        total_baseline = round(sum(i["baseline"] for i in items), 4)
        total_best = round(sum(i["best"] for i in items), 4)

        result = {
            "analysis_time": datetime.now().isoformat(),
            "unit_id": "GT-01",
            "aggregation": aggregation,
            "total_loss": total_current,
            "total_design_loss": total_baseline,
            "total_best_loss": total_best,
            "items": items,
            "major_losses": sorted(
                [i for i in items if i["current"] > i["baseline"] * 1.2],
                key=lambda x: x["current"] - x["baseline"],
                reverse=True,
            ),
        }
        return {"tool": "loss_analysis", "result": result}


def _adapt_mock_result(mock: dict) -> dict:
    """将旧 mock 格式适配为新格式。"""
    items = []
    for item in mock.get("items", []):
        current = item["value"]
        baseline = item["design"]
        best = round(baseline * 0.7, 4)
        items.append({
            "name": item["name"],
            "unit": "%",
            "param_key": "",
            "current": current,
            "baseline": baseline,
            "best": best,
            "deltaBaseline": round(current - baseline, 4),
            "deltaBest": round(current - best, 4),
        })

    return {
        "analysis_time": mock.get("analysis_time", ""),
        "unit_id": mock.get("unit_id", "GT-01"),
        "aggregation": "raw",
        "total_loss": mock.get("total_loss", 0),
        "total_design_loss": mock.get("total_design_loss", 0),
        "total_best_loss": round(sum(i["best"] for i in items), 4),
        "items": items,
        "major_losses": [],
    }
