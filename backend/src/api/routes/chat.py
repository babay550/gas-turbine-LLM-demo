"""智能对话 API — 对话接口（同步 + WebSocket）。"""

import asyncio
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect

from src.api.routes.chat_sessions import append_message

router = APIRouter()

_executor = ThreadPoolExecutor(max_workers=4)

# 工具名称 → 显示标签的映射
_TOOL_LABELS = {
    "realtime_monitoring": "实时监测数据",
    "efficiency_analysis": "能效分析模型",
    "loss_analysis": "耗差分析模型",
    "benchmark_analysis": "对标分析模型",
    "efficiency_trend": "能效趋势数据",
    "warning_query": "预警查询",
    "wiki_search": "技术知识库",
    "root_cause_analysis": "根因推理诊断",
}


def _build_citations(tool_results: list[dict]) -> list[dict]:
    """将工具调用结果转为前端可展示的引用列表。"""
    citations = []
    for tr in tool_results:
        tool_name = tr.get("tool", "")
        label = _TOOL_LABELS.get(tool_name, tool_name)
        result = tr.get("result", "")

        # 从结果中提取关键摘要
        summary = _extract_summary(tool_name, result)

        citations.append({
            "tool": tool_name,
            "label": label,
            "summary": summary,
        })
    return citations


def _extract_summary(tool_name: str, result) -> str:
    """根据工具类型提取一句话摘要。"""
    if not result:
        return ""
    try:
        import json
        if isinstance(result, str):
            data = json.loads(result)
        else:
            data = result
    except (json.JSONDecodeError, TypeError):
        return str(result)[:100]

    if tool_name == "realtime_monitoring":
        params = data.get("parameters", {})
        power = params.get("发电机有功功率", "?")
        status = data.get("status", "?")
        warnings = data.get("warnings", [])
        warn_text = f"，预警: {', '.join(warnings)}" if warnings else "，无活跃预警"
        return f"机组状态: {status}，负荷: {power} MW{warn_text}"

    if tool_name == "efficiency_analysis":
        indicators = data.get("indicators", {})
        parts = []
        for name, ind in indicators.items():
            val = ind.get("value", "?")
            unit = ind.get("unit", "")
            parts.append(f"{name}: {val}{unit}")
        return "；".join(parts[:5]) + ("..." if len(parts) > 5 else "")

    if tool_name == "loss_analysis":
        total = data.get("total_loss", "?")
        items = data.get("items", [])
        major = data.get("major_losses", [])
        major_names = ", ".join(i["name"] for i in major[:3])
        return f"总损失率: {total}%，主要损失: {major_names}"

    if tool_name == "benchmark_analysis":
        gaps = data.get("gaps", [])
        strengths = data.get("strengths", [])
        weaknesses = data.get("weaknesses", [])
        parts = []
        if strengths:
            parts.append(f"领先项: {', '.join(s['indicator'] for s in strengths)}")
        if weaknesses:
            parts.append(f"劣势项: {', '.join(w['indicator'] for w in weaknesses[:3])}")
        return "；".join(parts) if parts else f"共对比 {len(gaps)} 项指标"

    if tool_name == "efficiency_trend":
        period = data.get("period_days", "?")
        return f"近 {period} 天能效趋势数据"

    if tool_name == "warning_query":
        total = data.get("total", 0)
        warnings = data.get("warnings", [])
        levels = [w["level"] for w in warnings]
        high = levels.count("高")
        medium = levels.count("中")
        return f"活跃预警 {total} 条（高 {high}，中 {medium}）"

    if tool_name == "wiki_search":
        total = data.get("total", 0)
        items = data.get("items", [])
        titles = ", ".join(i.get("title", "") for i in items[:5])
        return f"检索到 {total} 条知识词条: {titles}"

    if tool_name == "root_cause_analysis":
        status = data.get("status", "")
        rules = data.get("triggered_rules", [])
        if status == "triggered" and rules:
            names = ", ".join(r.get("rule_name", "") for r in rules[:3])
            return f"触发 {len(rules)} 条专家规则: {names}"
        return "未触发专家规则，已检索知识库"

    return str(data)[:100]


@router.post("/message")
async def send_message(request: Request):
    """发送对话消息，获取 Agent 回复（同步接口）。"""
    body = await request.json()
    query = body.get("message", "")
    session_id = body.get("session_id")

    scheduler = request.app.state.scheduler

    # 尝试调用 Agent（LLM + 工具），有超时兜底
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(_executor, scheduler.dispatch, query)
        citations = _build_citations(result.get("tool_results", []))
        answer = result.get("answer", "")
        debug_logs = result.get("debug_logs", [])

        if session_id:
            append_message(session_id, "user", query)
            append_message(session_id, "assistant", answer, citations, debug_logs)

        return {
            "answer": answer,
            "citations": citations,
            "tool_results": result.get("tool_results", []),
            "debug_logs": debug_logs,
        }
    except FuturesTimeoutError:
        answer = "分析超时，LLM 服务可能响应较慢。当前可直接使用面板按钮触发分析。"
        if session_id:
            append_message(session_id, "user", query)
            append_message(session_id, "assistant", answer)
        return {
            "answer": answer,
            "citations": [],
            "tool_results": [],
            "debug_logs": [{"step": "dispatch", "status": "timeout", "detail": "执行超时"}],
        }
    except Exception as e:
        answer = f"当前 LLM 服务未连接（{e}），请使用面板按钮直接触发分析，或配置 .env 中的 LLM 地址后重启。"
        if session_id:
            append_message(session_id, "user", query)
            append_message(session_id, "assistant", answer)
        return {
            "answer": answer,
            "citations": [],
            "tool_results": [],
            "debug_logs": [{"step": "dispatch", "status": "error", "detail": str(e)}],
        }


@router.websocket("/ws")
async def chat_websocket(websocket: WebSocket):
    """WebSocket 对话接口（流式回复）。"""
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            query = data.get("message", "")

            scheduler = websocket.app.state.scheduler
            try:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(_executor, scheduler.dispatch, query)
                citations = _build_citations(result.get("tool_results", []))
                await websocket.send_json({
                    "type": "answer",
                    "content": result.get("answer", ""),
                    "citations": citations,
                    "tool_results": result.get("tool_results", []),
                    "debug_logs": result.get("debug_logs", []),
                })
            except Exception as e:
                await websocket.send_json({
                    "type": "error",
                    "content": str(e),
                })
    except WebSocketDisconnect:
        pass
