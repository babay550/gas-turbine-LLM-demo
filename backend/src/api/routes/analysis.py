"""分析诊断 API — 能效分析、耗差分析、对标分析、根因诊断。"""

from fastapi import APIRouter, Request

from src.data.connector import get_efficiency_analysis, get_loss_analysis, get_benchmark_analysis

router = APIRouter()


@router.post("/efficiency")
async def run_efficiency_analysis(request: Request):
    """执行能效分析。"""
    result = get_efficiency_analysis()
    return {"tool": "efficiency_analysis", "result": result}


@router.post("/loss")
async def run_loss_analysis(request: Request):
    """执行耗差分析。"""
    result = get_loss_analysis()
    return {"tool": "loss_analysis", "result": result}


@router.post("/benchmark")
async def run_benchmark_analysis(request: Request):
    """执行对标分析。"""
    result = get_benchmark_analysis()
    return {"tool": "benchmark_analysis", "result": result}


@router.post("/root-cause")
async def run_root_cause_analysis(request: Request):
    """执行根因推理分析（调用 Agent 通过 LLM 进行推理）。"""
    # MVP: 直接调用 Agent 的工具，后续接入 LLM 推理链
    scheduler = request.app.state.scheduler
    result = scheduler.trigger_direct("optimization_agent", "efficiency_analysis")
    return result


@router.post("/decomposition")
async def run_decomposition(request: Request):
    """执行逐级分解分析。"""
    # 基于耗差分析结果进行逐级分解
    loss_data = get_loss_analysis()
    total_loss = loss_data["total_loss"]
    items = loss_data["items"]

    # 模拟逐级分解
    subsystems = {
        "压气机": {"contribution": 0, "components": []},
        "燃烧室": {"contribution": 0, "components": []},
        "透平": {"contribution": 0, "components": []},
    }

    for item in items:
        name = item["name"]
        if "压气机" in name:
            subsystems["压气机"]["contribution"] += item["value"]
            subsystems["压气机"]["components"].append({"name": name, "value": item["value"], "design": item["design"]})
        elif "燃烧" in name:
            subsystems["燃烧室"]["contribution"] += item["value"]
            subsystems["燃烧室"]["components"].append({"name": name, "value": item["value"], "design": item["design"]})
        elif "透平" in name:
            subsystems["透平"]["contribution"] += item["value"]
            subsystems["透平"]["components"].append({"name": name, "value": item["value"], "design": item["design"]})

    return {
        "total_loss": total_loss,
        "total_design_loss": loss_data["total_design_loss"],
        "subsystems": subsystems,
    }
