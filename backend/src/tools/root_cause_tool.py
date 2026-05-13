"""根因推理分析工具 — 基于专家规则 + 因果图的推理链。

推理链路:
  1. 获取实时 SCADA 参数 + 能效分析指标
  2. 检测参数/指标异常
  3. 逐条匹配专家规则
  4. (触发) → 规则结论 + 置信度 → 搜索技术知识库 → 输出建议
  5. (未触发) → 直接搜索技术知识库 → 输出诊断建议
"""

import json
import time

from langchain_core.tools import tool

from src.data.connector import get_realtime_data, get_efficiency_analysis
from src.data.expert_rules_data import EXPERT_RULES, CAUSAL_GRAPH


_OPS = {
    ">": lambda a, b: a > b,
    "<": lambda a, b: a < b,
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
}


def _evaluate_rule(rule: dict, scada_params: dict, indicators: dict) -> tuple:
    """评估单条专家规则，返回 (是否触发, 匹配参数详情)。"""
    checks = rule.get("check_params", [])
    logic = rule.get("logic", "all")
    matched: dict = {}
    results: list[bool] = []

    for check in checks:
        param_name = check["param"]
        op = check["op"]
        threshold = check["value"]

        if param_name.startswith("__indicator__"):
            ind_name = param_name[len("__indicator__"):]
            value = indicators.get(ind_name, {}).get("value")
        else:
            value = scada_params.get(param_name)

        if value is None:
            results.append(False)
            continue

        triggered = _OPS.get(op, lambda a, b: False)(value, threshold)
        results.append(triggered)
        if triggered:
            matched[param_name] = {"value": value, "threshold": threshold, "op": op}

    if logic == "any":
        return any(results), matched
    return all(results), matched


def _find_chain(trigger_rule_id: str, graph_nodes: dict) -> list[str]:
    """从触发规则节点回溯到征兆节点，返回有序链路名称列表。"""
    chain: list[str] = []
    current_id = trigger_rule_id
    for _ in range(4):
        node = graph_nodes.get(current_id)
        if node:
            chain.append(node["name"])
        parent_edge = next(
            (e for e in CAUSAL_GRAPH["edges"] if e["target"] == current_id), None
        )
        if not parent_edge:
            break
        current_id = parent_edge["source"]
    chain.reverse()
    return chain


def run_root_cause_analysis(query: str = "") -> dict:
    """执行根因推理分析，返回结构化诊断结果。"""
    start_time = time.monotonic()

    # 1. 获取实时 SCADA 数据
    realtime = get_realtime_data()
    scada_params = realtime["parameters"]

    # 获取能效分析指标（部分规则基于指标判定）
    try:
        eff_result = get_efficiency_analysis()
        indicators = eff_result.get("indicators", {})
    except Exception:
        indicators = {}

    # 2. 逐条匹配专家规则
    triggered_rules: list[dict] = []
    for rule in EXPERT_RULES:
        is_triggered, matched = _evaluate_rule(rule, scada_params, indicators)
        if is_triggered:
            triggered_rules.append({
                "rule_id": rule["id"],
                "rule_name": rule["name"],
                "confidence": rule["confidence"],
                "conclusion": rule["conclusion"],
                "severity": rule["severity"],
                "symptom_tag": rule.get("symptom_tag", ""),
                "subsystem_tag": rule.get("subsystem_tag", ""),
                "root_cause_tag": rule.get("root_cause_tag") or "",
                "trigger_rule_id": rule.get("trigger_rule_id") or "",
                "matched_params": matched,
                "recommended_actions": rule.get("recommended_actions", ""),
            })

    triggered_rules.sort(key=lambda r: r["confidence"], reverse=True)

    # 3. 通过因果图构建诊断链
    graph_nodes = {n["id"]: n for n in CAUSAL_GRAPH["nodes"]}

    diagnosis_chains: list[dict] = []
    for tr in triggered_rules:
        trid = tr.get("trigger_rule_id", "")
        if trid:
            chain = _find_chain(trid, graph_nodes)
            diagnosis_chains.append({
                "chain": chain,
                "confidence": tr["confidence"],
                "severity": tr["severity"],
                "rule_id": tr["rule_id"],
                "rule_name": tr["rule_name"],
                "conclusion": tr["conclusion"],
                "recommended_actions": tr["recommended_actions"],
            })

    # 4. 搜索技术知识库
    wiki_refs: list[dict] = []
    try:
        from src.tools.wiki_search_tool import _get_wiki_manager
        wiki_mgr = _get_wiki_manager()

        search_terms: list[str] = []
        for tr in triggered_rules:
            if tr.get("root_cause_tag"):
                search_terms.append(tr["root_cause_tag"])
            if tr.get("subsystem_tag") and tr["subsystem_tag"] not in ("综合", ""):
                search_terms.append(tr["subsystem_tag"])
            # Meta-rules: use condition keywords
            if not tr.get("root_cause_tag") and not tr.get("trigger_rule_id"):
                search_terms.extend(["效率", "热耗"])
        if not search_terms and query:
            search_terms = [query]
        if not search_terms:
            search_terms = ["效率", "热耗"]

        seen_ids: set[str] = set()
        for term in search_terms[:4]:
            results = wiki_mgr.search_entries(term, limit=3)
            for r in results:
                rid = r.get("id", "")
                if rid and rid not in seen_ids:
                    seen_ids.add(rid)
                    wiki_refs.append({
                        "id": rid,
                        "title": r.get("title", ""),
                        "snippet": r.get("content_preview", "")[:200],
                        "relevance_score": r.get("score", 0),
                    })
    except Exception:
        pass

    # 5. 生成综合建议
    suggestions: list[str] = []
    if triggered_rules:
        for tr in triggered_rules[:3]:
            suggestions.append(f"[{tr['severity']}] {tr['conclusion']}")
            for action in tr["recommended_actions"].split("\n")[:2]:
                stripped = action.strip()
                if stripped:
                    suggestions.append(stripped)
    else:
        suggestions.append("未触发已知专家规则，建议持续监测关键参数")
        if wiki_refs:
            suggestions.append("请参考技术知识库中的相关资料进行人工判断")

    elapsed_ms = round((time.monotonic() - start_time) * 1000)

    # 汇总异常参数
    anomalies: list[dict] = []
    for tr in triggered_rules:
        for pname, pinfo in tr["matched_params"].items():
            anomalies.append({
                "param": pname,
                "value": pinfo["value"],
                "threshold": pinfo["threshold"],
                "direction": pinfo["op"],
            })

    return {
        "status": "triggered" if triggered_rules else "no_rule_matched",
        "anomalies": anomalies,
        "triggered_rules": triggered_rules,
        "diagnosis_chains": diagnosis_chains,
        "wiki_references": wiki_refs[:8],
        "suggestions": suggestions,
        "elapsed_ms": elapsed_ms,
    }


@tool
def root_cause_analysis(query: str = "") -> str:
    """根因推理诊断工具：检测参数异常，匹配专家规则，结合因果图和技术知识库输出诊断结论。

    当用户提问涉及根因诊断、故障排查、异常分析时使用此工具。
    """
    result = run_root_cause_analysis(query)
    return json.dumps(result, ensure_ascii=False, indent=2)
