"""工作流执行引擎 — 将 JSON 工作流定义转为 LangGraph StateGraph 并执行。"""

import json
import logging
import time
from typing import Any

from langgraph.graph import StateGraph, END

logger = logging.getLogger(__name__)

# ---- 工作流状态 ----
WorkflowState = dict[str, Any]

# ---- 节点类型定义 ----
NODE_TYPES = [
    {"type": "user_input", "label": "用户输入", "category": "输入", "icon": "chat", "color": "#409eff",
     "description": "接收用户自然语言提问或参数输入", "config_fields": []},
    {"type": "parameter_select", "label": "指标参数选取", "category": "输入", "icon": "data", "color": "#409eff",
     "description": "从数据字典中选取监测参数或对标指标", "config_fields": [
         {"key": "parameters", "label": "选取参数", "type": "multiselect",
          "options": ["透平出口温度_T4", "压气机出口温度_T2", "发电机有功功率", "天然气瞬时流量",
                      "热耗率", "发电效率", "联合循环效率", "压气机效率", "透平效率", "振动_轴向"]}]},
    {"type": "intent_recognition", "label": "意图识别", "category": "分析", "icon": "brain", "color": "#e6a23c",
     "description": "调用大语言模型识别用户意图", "config_fields": [
         {"key": "prompt", "label": "提示词", "type": "textarea", "default": "识别用户意图"}]},
    {"type": "model_call", "label": "小模型调用", "category": "分析", "icon": "cpu", "color": "#e6a23c",
     "description": "调用已注册的分析小模型", "config_fields": [
         {"key": "tool", "label": "选择工具", "type": "select",
          "options": ["efficiency_analysis", "loss_analysis", "benchmark_analysis",
                       "realtime_monitoring", "efficiency_trend", "warning_query"]}]},
    {"type": "reasoning", "label": "推理分析", "category": "分析", "icon": "search", "color": "#e6a23c",
     "description": "基于指标、知识库、规则进行因果推理", "config_fields": [
         {"key": "focus", "label": "分析焦点", "type": "text", "default": "综合研判"}]},
    {"type": "code_execute", "label": "代码执行", "category": "分析", "icon": "code", "color": "#e6a23c",
     "description": "执行自定义 Python 计算脚本", "config_fields": [
         {"key": "code", "label": "Python 代码", "type": "textarea", "default": "# result = ..."}]},
    {"type": "knowledge_search", "label": "技术知识库", "category": "知识", "icon": "book", "color": "#67c23a",
     "description": "检索技术知识库", "config_fields": [
         {"key": "query", "label": "检索关键词", "type": "text"}]},
    {"type": "expert_rules", "label": "专家规则", "category": "知识", "icon": "rule", "color": "#67c23a",
     "description": "匹配并应用专家规则", "config_fields": []},
    {"type": "result_output", "label": "结果输出", "category": "输出", "icon": "output", "color": "#f56c6c",
     "description": "调用 LLM 生成自然语言报告", "config_fields": [
         {"key": "prompt_template", "label": "输出模板", "type": "textarea",
          "default": "基于以上分析数据，生成运维优化建议报告"}]},
    {"type": "data_output", "label": "数据输出", "category": "输出", "icon": "table", "color": "#f56c6c",
     "description": "输出结构化 JSON 数据", "config_fields": []},
    {"type": "condition_branch", "label": "条件分支", "category": "通用", "icon": "branch", "color": "#909399",
     "description": "条件判断，走不同分支", "config_fields": [
         {"key": "field", "label": "判断字段", "type": "text", "default": "result.indicators.发电效率.value"},
         {"key": "operator", "label": "运算符", "type": "select", "options": [">", "<", ">=", "<=", "==", "!="]},
         {"key": "threshold", "label": "阈值", "type": "number", "default": 40}]},
    {"type": "loop", "label": "循环", "category": "通用", "icon": "loop", "color": "#909399",
     "description": "对列表逐项执行", "config_fields": []},
    {"type": "iterator", "label": "迭代", "category": "通用", "icon": "refresh", "color": "#909399",
     "description": "反复执行直到满足终止条件", "config_fields": []},
    {"type": "question_classifier", "label": "问题分类器", "category": "通用", "icon": "classify", "color": "#909399",
     "description": "将问题分类并路由到不同链路", "config_fields": []},
    {"type": "list_operation", "label": "列表操作", "category": "通用", "icon": "list", "color": "#909399",
     "description": "过滤、排序、聚合列表数据", "config_fields": []},
    {"type": "variable_store", "label": "变量存储", "category": "通用", "icon": "variable", "color": "#909399",
     "description": "存取中间变量", "config_fields": []},
]

# ---- 预设模板 ----
TEMPLATES = [
    {
        "id": "tpl-efficiency",
        "name": "能效异常诊断流",
        "description": "获取实时数据 → 能效分析 → 偏差判断 → 正常报告或耗差深入分析 → 结果输出",
        "nodes": [
            {"id": "n1", "type": "user_input", "label": "用户提问", "position": {"x": 50, "y": 250}, "config": {}},
            {"id": "n2", "type": "model_call", "label": "能效分析", "position": {"x": 280, "y": 250}, "config": {"tool": "efficiency_analysis"}},
            {"id": "n3", "type": "condition_branch", "label": "效率>38%?", "position": {"x": 510, "y": 250}, "config": {"field": "result.indicators.发电效率.value", "operator": ">=", "threshold": 38}},
            {"id": "n4", "type": "result_output", "label": "正常报告", "position": {"x": 740, "y": 120}, "config": {"prompt_template": "能效指标正常，简要汇总分析结果"}},
            {"id": "n5", "type": "model_call", "label": "耗差分析", "position": {"x": 740, "y": 380}, "config": {"tool": "loss_analysis"}},
            {"id": "n6", "type": "result_output", "label": "异常报告", "position": {"x": 970, "y": 380}, "config": {"prompt_template": "能效指标异常，结合耗差分析数据给出优化建议"}},
        ],
        "edges": [
            {"id": "e1", "source": "n1", "target": "n2"},
            {"id": "e2", "source": "n2", "target": "n3"},
            {"id": "e3", "source": "n3", "target": "n4", "sourceHandle": "yes"},
            {"id": "e4", "source": "n3", "target": "n5", "sourceHandle": "no"},
            {"id": "e5", "source": "n5", "target": "n6"},
        ],
    },
    {
        "id": "tpl-warning",
        "name": "预警响应流",
        "description": "查询活跃预警 → 检索知识库 → 匹配专家规则 → 生成处置建议",
        "nodes": [
            {"id": "n1", "type": "user_input", "label": "触发输入", "position": {"x": 50, "y": 250}, "config": {}},
            {"id": "n2", "type": "model_call", "label": "预警查询", "position": {"x": 280, "y": 250}, "config": {"tool": "warning_query"}},
            {"id": "n3", "type": "knowledge_search", "label": "知识库检索", "position": {"x": 510, "y": 250}, "config": {"query": "预警相关故障处理"}},
            {"id": "n4", "type": "expert_rules", "label": "规则匹配", "position": {"x": 740, "y": 250}, "config": {}},
            {"id": "n5", "type": "result_output", "label": "处置建议", "position": {"x": 970, "y": 250}, "config": {"prompt_template": "基于预警数据、知识库和专家规则，生成处置建议"}},
        ],
        "edges": [
            {"id": "e1", "source": "n1", "target": "n2"},
            {"id": "e2", "source": "n2", "target": "n3"},
            {"id": "e3", "source": "n3", "target": "n4"},
            {"id": "e4", "source": "n4", "target": "n5"},
        ],
    },
    {
        "id": "tpl-benchmark",
        "name": "对标分析流",
        "description": "调用对标模型 → 差距分析 → 分类优势劣势 → 优化建议",
        "nodes": [
            {"id": "n1", "type": "user_input", "label": "触发输入", "position": {"x": 50, "y": 250}, "config": {}},
            {"id": "n2", "type": "model_call", "label": "对标分析", "position": {"x": 280, "y": 250}, "config": {"tool": "benchmark_analysis"}},
            {"id": "n3", "type": "reasoning", "label": "差距研判", "position": {"x": 510, "y": 250}, "config": {"focus": "对标差距根因分析"}},
            {"id": "n4", "type": "result_output", "label": "优化建议", "position": {"x": 740, "y": 250}, "config": {"prompt_template": "基于对标分析结果，指出优劣势指标并给出改进方向"}},
        ],
        "edges": [
            {"id": "e1", "source": "n1", "target": "n2"},
            {"id": "e2", "source": "n2", "target": "n3"},
            {"id": "e3", "source": "n3", "target": "n4"},
        ],
    },
]


# ---- 节点执行器 ----

def _exec_user_input(state: WorkflowState, config: dict) -> WorkflowState:
    return {**state, "step": "user_input", "output": state.get("user_input", "")}


def _exec_parameter_select(state: WorkflowState, config: dict) -> WorkflowState:
    from src.data.connector import get_realtime_data
    realtime = get_realtime_data()
    params = realtime.get("parameters", {})
    selected = config.get("parameters", [])
    result = {k: v for k, v in params.items() if k in selected} if selected else params
    return {**state, "step": "parameter_select", "output": result}


def _exec_intent_recognition(state: WorkflowState, config: dict) -> WorkflowState:
    # 简化版：直接透传（LLM 版本需额外调用）
    return {**state, "step": "intent_recognition", "output": state.get("user_input", "")}


def _exec_model_call(state: WorkflowState, config: dict) -> WorkflowState:
    tool_name = config.get("tool", "")
    from src.agents.optimization_agent import OptimizationAgent
    agent = OptimizationAgent()
    result = agent.run_direct(tool_name)
    return {**state, "step": "model_call", "tool": tool_name, "output": result}


def _exec_reasoning(state: WorkflowState, config: dict) -> WorkflowState:
    return {**state, "step": "reasoning", "output": {"focus": config.get("focus", ""), "data": state.get("output", {})}}


def _exec_code_execute(state: WorkflowState, config: dict) -> WorkflowState:
    code = config.get("code", "")
    local_vars = {"state": state, "result": None}
    try:
        exec(code, {"__builtins__": {}}, local_vars)
    except Exception as e:
        local_vars["result"] = f"执行错误: {e}"
    return {**state, "step": "code_execute", "output": local_vars.get("result")}


def _exec_knowledge_search(state: WorkflowState, config: dict) -> WorkflowState:
    from src.api.routes.knowledge import KNOWLEDGE_BASE
    query = config.get("query", "")
    items = KNOWLEDGE_BASE.get("maintenance", [])
    if query:
        items = [k for k in items if query in k.get("title", "") or any(query in kw for kw in k.get("keywords", []))]
    return {**state, "step": "knowledge_search", "output": {"total": len(items), "items": items}}


def _exec_expert_rules(state: WorkflowState, config: dict) -> WorkflowState:
    from src.api.routes.knowledge import KNOWLEDGE_BASE
    rules = KNOWLEDGE_BASE.get("expert_rules", [])
    return {**state, "step": "expert_rules", "output": {"total": len(rules), "rules": rules}}


def _exec_result_output(state: WorkflowState, config: dict) -> WorkflowState:
    return {**state, "step": "result_output", "output": state.get("output", "无输出数据")}


def _exec_data_output(state: WorkflowState, config: dict) -> WorkflowState:
    return {**state, "step": "data_output", "output": state.get("output", {})}


def _exec_condition_branch(state: WorkflowState, config: dict) -> WorkflowState:
    field = config.get("field", "")
    operator = config.get("operator", ">=")
    threshold = config.get("threshold", 0)

    value = _resolve_field(state, field)
    passed = _compare(value, operator, threshold)
    return {**state, "step": "condition_branch", "branch": "yes" if passed else "no",
            "output": {"field": field, "value": value, "threshold": threshold, "passed": passed}}


def _exec_noop(state: WorkflowState, config: dict) -> WorkflowState:
    return {**state, "output": state.get("output", {})}


def _resolve_field(state: dict, field: str):
    """解析 'result.indicators.发电效率.value' 形式的字段路径。"""
    current = state
    for part in field.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
        if current is None:
            return None
    return current


def _compare(value, operator: str, threshold) -> bool:
    if value is None:
        return False
    try:
        if operator == ">": return value > threshold
        if operator == "<": return value < threshold
        if operator == ">=": return value >= threshold
        if operator == "<=": return value <= threshold
        if operator == "==": return value == threshold
        if operator == "!=": return value != threshold
    except TypeError:
        return False
    return False


EXECUTORS = {
    "user_input": _exec_user_input,
    "parameter_select": _exec_parameter_select,
    "intent_recognition": _exec_intent_recognition,
    "model_call": _exec_model_call,
    "reasoning": _exec_reasoning,
    "code_execute": _exec_code_execute,
    "knowledge_search": _exec_knowledge_search,
    "expert_rules": _exec_expert_rules,
    "result_output": _exec_result_output,
    "data_output": _exec_data_output,
    "condition_branch": _exec_condition_branch,
    "loop": _exec_noop,
    "iterator": _exec_noop,
    "question_classifier": _exec_noop,
    "list_operation": _exec_noop,
    "variable_store": _exec_noop,
}


# ---- 简易 DAG 执行器（不依赖 LangGraph 复杂拓扑，手动按边遍历） ----

def execute_workflow(workflow: dict, user_input: str = "") -> dict:
    """执行工作流：按拓扑序遍历节点，通过 edges 路由数据。"""
    nodes = {n["id"]: n for n in workflow.get("nodes", [])}
    edges = workflow.get("edges", [])

    state: WorkflowState = {"user_input": user_input}
    logs = []
    total_start = time.monotonic()

    # 找起始节点（没有被任何 edge 作为 target 的节点）
    targets = {e["target"] for e in edges}
    start_nodes = [nid for nid in nodes if nid not in targets]
    if not start_nodes:
        start_nodes = [next(iter(nodes))]

    # 按拓扑序执行
    executed = set()
    queue = list(start_nodes)

    while queue:
        node_id = queue.pop(0)
        if node_id in executed:
            continue

        node = nodes.get(node_id)
        if not node:
            continue

        node_type = node.get("type", "")
        config = node.get("config", {})
        executor = EXECUTORS.get(node_type)
        if not executor:
            logs.append({"node": node_id, "type": node_type, "status": "skipped", "detail": "无执行器"})
            executed.add(node_id)
            queue.extend(_next_nodes(node_id, edges, None))
            continue

        step_start = time.monotonic()
        try:
            state = executor(state, config)
            elapsed = round((time.monotonic() - step_start) * 1000)
            logs.append({"node": node_id, "type": node_type, "label": node.get("label", ""),
                          "status": "ok", "elapsed_ms": elapsed})
        except Exception as e:
            elapsed = round((time.monotonic() - step_start) * 1000)
            logs.append({"node": node_id, "type": node_type, "label": node.get("label", ""),
                          "status": "error", "elapsed_ms": elapsed, "detail": str(e)})

        executed.add(node_id)

        # 确定下一个节点（支持条件分支）
        branch = state.get("branch")
        next_ids = _next_nodes(node_id, edges, branch)
        queue.extend(next_ids)

    total_ms = round((time.monotonic() - total_start) * 1000)
    return {
        "status": "completed",
        "total_ms": total_ms,
        "logs": logs,
        "final_output": state.get("output", ""),
        "state_keys": list(state.keys()),
    }


def _next_nodes(node_id: str, edges: list, branch: str | None) -> list[str]:
    """获取当前节点的下游节点，支持条件分支的 sourceHandle。"""
    result = []
    for e in edges:
        if e["source"] != node_id:
            continue
        handle = e.get("sourceHandle")
        if branch and handle:
            if handle == branch:
                result.append(e["target"])
        else:
            result.append(e["target"])
    return result
