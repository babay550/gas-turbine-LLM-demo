"""分析诊断 API — 能效分析、耗差分析、对标分析、根因诊断。"""

import asyncio
import json
import logging

from fastapi import APIRouter, Request

from src.data.connector import get_efficiency_analysis, get_benchmark_analysis

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/efficiency")
async def run_efficiency_analysis(request: Request):
    """执行能效分析。"""
    result = get_efficiency_analysis()
    return {"tool": "efficiency_analysis", "result": result}


@router.post("/loss")
async def run_loss_analysis_route(request: Request):
    """执行耗差分析 — 基于系统上报的 coalLossValue 做偏差分解（实时取最新点）。"""
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass

    unit_id = body.get("unit_id", "GT-01")
    aggregation = body.get("aggregation", "raw")  # raw / 1d / 1w
    mode = body.get("mode", "coal")  # coal=对标基准 / optimal=对标最优

    from src.tools.loss_analysis_tool import run_loss_analysis
    result = run_loss_analysis(unit_id, aggregation, mode)
    return {"tool": "loss_analysis", "result": result}


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
    """偏差分解：返回 能耗偏差 → 子系统 → 因素 的层级结构（实时取最新点）。"""
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    mode = body.get("mode", "coal")  # coal=对标基准 / optimal=对标最优
    aggregation = body.get("aggregation", "raw")  # raw / 1d / 1w

    from src.tools.loss_analysis_tool import run_loss_analysis
    result = run_loss_analysis("GT-01", aggregation=aggregation, mode=mode)
    total = result.get("total") or {}
    return {
        "total_loss": total.get("main_value") or 0,
        "total_optimal_loss": total.get("optimalLossValue") or 0,
        "total": total,
        "subsystems": result.get("subsystems", []),
        "factor_ranking": result.get("factor_ranking", []),
        "mode": mode,
    }


@router.post("/historical-loss")
async def run_historical_loss_analysis_route(request: Request):
    """基于指定时间段执行三区间耗差分析（直接调用 loss_analysis_tool）。"""
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass

    start = body.get("start", "")
    end = body.get("end", "")
    unit_id = body.get("unit_id", "GT-01")
    aggregation = body.get("aggregation", "1h")
    mode = body.get("mode", "coal")  # coal=对标基准 / optimal=对标最优

    if not start or not end:
        return {"tool": "historical_loss_analysis", "error": "请指定时间范围"}

    from src.tools.loss_analysis_tool import run_historical_loss_analysis
    result = run_historical_loss_analysis(start, end, unit_id, aggregation, mode)
    return {"tool": "historical_loss_analysis", "result": result}


@router.post("/qa")
async def analysis_qa(request: Request):
    """数据问答：综合 耗差分析 + 所选参数统计摘要 + 知识库检索 三源，由 LLM 作答。"""
    body = await request.json()
    message = body.get("message", "")
    start = body.get("start", "")
    end = body.get("end", "")
    unit_id = body.get("unit_id", "GT-01")
    stats = body.get("stats", []) or []

    if not message.strip():
        return {"answer": "请输入问题", "loss_summary": {}}
    if not start or not end:
        return {"answer": "请先选择时间范围", "loss_summary": {}}

    from src.tools.loss_analysis_tool import run_historical_loss_analysis

    # 耗差分析与知识库检索无相互依赖，并发执行；二者均为同步阻塞调用，
    # 用 to_thread 交给线程池，避免阻塞 FastAPI 事件循环（否则处理期间全站卡顿）。
    loss_result, wiki_ctx = await asyncio.gather(
        asyncio.to_thread(run_historical_loss_analysis, start, end, unit_id),
        asyncio.to_thread(_build_wiki_context, message),
    )

    loss_summary = _extract_loss_summary(loss_result)
    # 以下为纯内存计算（微秒级），直接同步调用即可
    loss_ctx = _build_loss_qa_context(loss_result)
    stats_ctx = _build_stats_context(stats)

    sections = []
    if loss_ctx:
        sections.append("【耗差分析（基于负荷率三区间）】\n" + loss_ctx)
    if stats_ctx:
        sections.append("【所选参数统计摘要】\n" + stats_ctx)
    if wiki_ctx:
        sections.append("【相关知识库检索】\n" + wiki_ctx)
    full_context = "\n\n".join(sections) or "（该时段无可用的耗差分析结论与统计数据）"

    scheduler = request.app.state.scheduler
    agent = scheduler._agents.get("analysis_agent")
    llm = getattr(agent, "_llm", None) if agent else None

    if llm is None:
        answer = full_context
    else:
        from langchain_core.messages import SystemMessage, HumanMessage
        system_prompt = (
            "你是燃气轮机运行分析助手。以下是关于用户所选时段的多源信息"
            "（耗差分析 / 统计摘要 / 知识库），请综合它们回答用户问题。"
            "严格基于提供的数据，不要编造未给出的数字；若信息不足以下结论，请明确说明缺少什么。"
            "回答简洁专业。\n\n"
            f"{full_context}"
        )
        try:
            # llm.invoke 为同步阻塞（网络请求），同样交线程池，避免阻塞事件循环
            response = await asyncio.to_thread(
                llm.invoke,
                [SystemMessage(content=system_prompt), HumanMessage(content=message)],
            )
            answer = response.content if hasattr(response, "content") else str(response)
        except Exception as e:
            logger.warning("analysis_qa LLM 调用失败: %s", e)
            answer = f"分析已完成，但 LLM 作答失败（{e}）。以下为综合信息：\n\n{full_context}"

    # 持久化对话到 DB（按当前用户隔离）
    _save_qa_messages(getattr(request.state, "user_id", None), message, answer)

    return {"answer": answer, "loss_summary": loss_summary}


def _save_qa_messages(user_id, user_message: str, assistant_answer: str) -> None:
    """持久化数据问答的 user/assistant 消息对到 DB（按用户隔离）。"""
    try:
        from src.db.engine import get_session
        from src.db.models import HistoricalQAMessage
        with get_session() as session:
            session.add(HistoricalQAMessage(user_id=user_id, role="user", content=user_message))
            session.add(HistoricalQAMessage(user_id=user_id, role="assistant", content=assistant_answer))
    except Exception as e:
        logger.warning("持久化数据问答消息失败: %s", e)


@router.get("/qa/history")
async def get_qa_history(request: Request):
    """获取数据问答历史对话（按时间顺序）。"""
    from src.db.engine import get_session
    from src.db.models import HistoricalQAMessage
    user_id = getattr(request.state, "user_id", None)
    with get_session() as session:
        msgs = session.query(HistoricalQAMessage).filter(
            HistoricalQAMessage.user_id == user_id
        ).order_by(HistoricalQAMessage.id).all()
        return {"messages": [m.to_dict() for m in msgs]}


@router.delete("/qa/history")
async def clear_qa_history(request: Request):
    """清空数据问答历史。"""
    from src.db.engine import get_session
    from src.db.models import HistoricalQAMessage
    user_id = getattr(request.state, "user_id", None)
    with get_session() as session:
        session.query(HistoricalQAMessage).filter(
            HistoricalQAMessage.user_id == user_id
        ).delete()
    return {"success": True}


def _extract_loss_summary(loss_result: dict) -> dict:
    """从偏差分解结果提取关键汇总数字。"""
    total = loss_result.get("total") or {}
    subsystems = loss_result.get("subsystems") or []
    ranking = loss_result.get("factor_ranking") or []
    return {
        "total_data_points": loss_result.get("total_data_points", 0),
        "coal_loss_g_kwh": total.get("coalLossValue"),
        "optimal_loss_g_kwh": total.get("optimalLossValue"),
        "top_subsystem": subsystems[0].get("name") if subsystems else None,
        "top_factor": ranking[0].get("name") if ranking else None,
    }


def _build_loss_qa_context(loss_result: dict) -> str:
    """构建偏差分解上下文，仅在有真实 coalLossValue 时返回内容。"""
    total = loss_result.get("total") or {}
    if total.get("coalLossValue") is None:
        return ""
    parts = [loss_result.get("report", "")]
    findings = loss_result.get("key_findings") or []
    if findings:
        parts.append("关键结论：" + "；".join(findings))
    return "\n".join(p for p in parts if p)


def _build_stats_context(stats: list) -> str:
    """格式化前端传来的参数统计摘要为上下文文本。"""
    if not stats:
        return ""
    lines = []
    for s in stats:
        if not isinstance(s, dict):
            continue
        name = s.get("parameter_name") or s.get("parameter_key") or ""
        unit = s.get("unit") or ""
        mean = s.get("mean")
        mn = s.get("min")
        mx = s.get("max")
        oor = s.get("out_of_range_count") or 0
        line = f"- {name}({unit}): 均值={'无数据' if mean is None else round(mean, 2)}"
        if mn is not None and mx is not None:
            line += f"，范围=[{round(mn, 2)}, {round(mx, 2)}]"
        if s.get("normal_min") is not None and s.get("normal_max") is not None:
            line += f"，正常范围[{s['normal_min']}, {s['normal_max']}]"
        if oor:
            line += f"，超限{oor}次"
        lines.append(line)
    return "\n".join(lines)


def _build_wiki_context(query: str) -> str:
    """调用 wiki_search 检索知识库，格式化为上下文文本。"""
    try:
        from src.tools.wiki_search_tool import wiki_search
        result_str = wiki_search.invoke({"query": query})
        data = json.loads(result_str) if isinstance(result_str, str) else result_str
    except Exception as e:
        logger.warning("analysis_qa wiki_search 失败: %s", e)
        return ""
    items = data.get("items", []) if isinstance(data, dict) else []
    if not items:
        return ""
    lines = []
    for it in items[:5]:
        title = it.get("title", "")
        preview = (it.get("content_preview") or "").replace("\n", " ").strip()[:200]
        lines.append(f"- {title}: {preview}")
    return "\n".join(lines)
