"""燃气轮机运行优化智能体 — Streamlit 主应用。"""

import json
import logging
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from datetime import datetime

from src.agents.optimization_agent import OptimizationAgent
from src.core.scheduler import Scheduler
from src.core.trigger_engine import TriggerEngine
from src.data.connector import get_realtime_data, get_efficiency_trend

logging.basicConfig(level=logging.INFO)

# ============================================================
# 页面配置
# ============================================================
st.set_page_config(
    page_title="燃气轮机运行优化智能体",
    page_icon="⚙️",
    layout="wide",
)

# ============================================================
# 初始化 session state
# ============================================================
if "scheduler" not in st.session_state:
    agent = OptimizationAgent()
    scheduler = Scheduler()
    scheduler.register_agent(agent)
    trigger_engine = TriggerEngine()

    # 注册触发回调
    for tool_name in ["efficiency_analysis", "loss_analysis", "benchmark_analysis"]:
        trigger_engine.register_callback(
            tool_name,
            lambda tt, t=tool_name: scheduler.trigger_direct("optimization_agent", t),
        )
    trigger_engine.start()

    st.session_state.scheduler = scheduler
    st.session_state.trigger_engine = trigger_engine
    st.session_state.agent = agent
    st.session_state.chat_history = []
    st.session_state.analysis_results = {
        "efficiency_analysis": None,
        "loss_analysis": None,
        "benchmark_analysis": None,
    }
    st.session_state.realtime_data = get_realtime_data()
    st.session_state.last_refresh = datetime.now()


def refresh_realtime_data():
    st.session_state.realtime_data = get_realtime_data()
    st.session_state.last_refresh = datetime.now()


def execute_analysis(tool_name: str):
    """执行分析并将结果存入 session_state。"""
    with st.spinner(f"正在执行 {TOOL_LABELS[tool_name]}..."):
        result = st.session_state.scheduler.trigger_direct(
            "optimization_agent", tool_name
        )
        if "error" not in result:
            st.session_state.analysis_results[tool_name] = result.get("result")
        return result


TOOL_LABELS = {
    "efficiency_analysis": "能效分析",
    "loss_analysis": "耗差分析",
    "benchmark_analysis": "对标分析",
}


# ============================================================
# 主布局
# ============================================================
title_col, refresh_col = st.columns([6, 1])
with title_col:
    st.title("燃气轮机运行优化智能体")
with refresh_col:
    st.write("")
    st.write("")
    if st.button("刷新数据", use_container_width=True):
        refresh_realtime_data()

# ============================================================
# 顶部: 状态总览
# ============================================================
st.subheader("机组运行状态总览")

data = st.session_state.realtime_data
params = data.get("parameters", {})
status = data.get("status", "未知")
warnings = data.get("warnings", [])

# 状态指标卡片
cols = st.columns(4)
metric_items = [
    ("发电功率", "MW", 180, 220),
    ("排气温度", "°C", 520, 580),
    ("热耗率", "kJ/kWh", 7800, 8600),
    ("负荷率", "%", 75, 100),
]

for i, (name, unit, low, high) in enumerate(metric_items):
    val = params.get(name)
    if val is None:
        # 从已有参数中估算负荷率
        if name == "负荷率" and params.get("发电功率"):
            val = round(params["发电功率"] / 220 * 100, 1)
        else:
            continue
    with cols[i]:
        delta = None
        if name == "热耗率":
            design = 8000
            delta = f"偏差 {val - design:+.0f}"
        elif name == "发电功率":
            design = 220
            delta = f"额定 {design}"
        st.metric(name, f"{val} {unit}", delta)

# 预警信息
if warnings:
    st.warning("当前预警: " + " | ".join(warnings))
else:
    st.success("无活跃预警")

st.caption(f"数据更新时间: {st.session_state.last_refresh.strftime('%H:%M:%S')}")

st.divider()

# ============================================================
# 中部: 运营优化面板
# ============================================================
st.subheader("运营优化面板")

# 一键触发按钮
st.write("**快速分析**")
btn_cols = st.columns(3)
for i, (tool_name, label) in enumerate(TOOL_LABELS.items()):
    with btn_cols[i]:
        if st.button(f"执行{label}", key=f"btn_{tool_name}", use_container_width=True):
            execute_analysis(tool_name)
            st.rerun()

# 分析结果展示 — 三个 Tab
tab_eff, tab_loss, tab_bench = st.tabs(["能效分析", "耗差分析", "对标分析"])

# ---- 能效分析 Tab ----
with tab_eff:
    eff_result = st.session_state.analysis_results.get("efficiency_analysis")
    if eff_result:
        try:
            eff_data = json.loads(eff_result) if isinstance(eff_result, str) else eff_result
        except (json.JSONDecodeError, TypeError):
            eff_data = None

        if eff_data and "current" in eff_data:
            current = eff_data["current"]
            design = eff_data["design"]

            # 指标对比表
            common_keys = [k for k in current if k in design]
            comp_data = {
                "指标": common_keys,
                "当前值": [current[k] for k in common_keys],
                "设计值": [design[k] for k in common_keys],
                "偏差": [round(current[k] - design[k], 2) for k in common_keys],
            }
            st.dataframe(pd.DataFrame(comp_data), use_container_width=True, hide_index=True)

            # 能效趋势图
            trend = get_efficiency_trend(7)
            trend_df = pd.DataFrame(trend["data"])
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=[str(d)[:10] for d in trend_df["日期"]],
                y=trend_df["热耗率_kJ/kWh"],
                mode="lines+markers",
                name="热耗率",
            ))
            fig.add_hline(y=8000, line_dash="dash", line_color="green", annotation_text="设计值")
            fig.update_layout(title="近 7 天热耗率趋势", yaxis_title="kJ/kWh", height=350)
            st.plotly_chart(fig, use_container_width=True)

            # 优化建议
            if eff_data.get("suggestions"):
                st.write("**优化建议:**")
                for s in eff_data["suggestions"]:
                    st.write(f"- {s}")
        else:
            st.info("点击上方'执行能效分析'按钮获取分析结果")
    else:
        # 展示默认趋势图
        trend = get_efficiency_trend(7)
        trend_df = pd.DataFrame(trend["data"])
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=[str(d)[:10] for d in trend_df["日期"]],
            y=trend_df["热耗率_kJ/kWh"],
            mode="lines+markers",
            name="热耗率",
        ))
        fig.add_hline(y=8000, line_dash="dash", line_color="green", annotation_text="设计值")
        fig.update_layout(title="近 7 天热耗率趋势", yaxis_title="kJ/kWh", height=350)
        st.plotly_chart(fig, use_container_width=True)
        st.info("点击上方'执行能效分析'按钮获取完整分析结果")

# ---- 耗差分析 Tab ----
with tab_loss:
    loss_result = st.session_state.analysis_results.get("loss_analysis")
    if loss_result:
        try:
            loss_data = json.loads(loss_result) if isinstance(loss_result, str) else loss_result
        except (json.JSONDecodeError, TypeError):
            loss_data = None

        if loss_data and "items" in loss_data:
            # 各项损失柱状图
            fig = go.Figure()
            names = [item["name"] for item in loss_data["items"]]
            values = [item["value"] for item in loss_data["items"]]
            designs = [item["design"] for item in loss_data["items"]]

            fig.add_trace(go.Bar(name="当前值", x=names, y=values, marker_color="#e74c3c"))
            fig.add_trace(go.Bar(name="设计值", x=names, y=designs, marker_color="#2ecc71"))
            fig.update_layout(
                title="耗差分析 — 各项损失占比 (%)",
                barmode="group",
                yaxis_title="损失占比 (%)",
                height=400,
            )
            st.plotly_chart(fig, use_container_width=True)

            st.metric("总损失", f"{loss_data['total_loss']}%", f"设计值 {loss_data['total_design_loss']}%")

            if loss_data.get("major_losses"):
                st.write("**主要异常损失项:**")
                for item in loss_data["major_losses"]:
                    st.write(
                        f"- {item['name']}: 当前 {item['value']}% / 设计 {item['design']}%"
                    )
        else:
            st.info("点击上方'执行耗差分析'按钮获取分析结果")
    else:
        st.info("点击上方'执行耗差分析'按钮获取分析结果")

# ---- 对标分析 Tab ----
with tab_bench:
    bench_result = st.session_state.analysis_results.get("benchmark_analysis")
    if bench_result:
        try:
            bench_data = json.loads(bench_result) if isinstance(bench_result, str) else bench_result
        except (json.JSONDecodeError, TypeError):
            bench_data = None

        if bench_data and "gaps" in bench_data:
            st.caption(f"对标组: {bench_data.get('peer_group', '')} | 统计周期: {bench_data.get('period', '')}")

            # 对标对比图
            indicators = [g["indicator"] for g in bench_data["gaps"]]
            this_vals = [g["this_unit"] for g in bench_data["gaps"]]
            peer_vals = [g["peer_avg"] for g in bench_data["gaps"]]

            fig = go.Figure()
            fig.add_trace(go.Bar(name="本机组", x=indicators, y=this_vals, marker_color="#3498db"))
            fig.add_trace(go.Bar(name="同类均值", x=indicators, y=peer_vals, marker_color="#95a5a6"))
            fig.update_layout(
                title="机组对标分析",
                barmode="group",
                height=400,
            )
            st.plotly_chart(fig, use_container_width=True)

            # 差距表
            gap_df = pd.DataFrame(bench_data["gaps"])
            st.dataframe(gap_df, use_container_width=True, hide_index=True)

            if bench_data.get("weaknesses"):
                st.write("**主要差距项:**")
                for w in bench_data["weaknesses"][:3]:
                    direction = "优于" if w["gap"] < 0 else "落后"
                    st.write(f"- {w['indicator']}: {direction}同类均值 {abs(w['gap'])} {w['unit']}")
        else:
            st.info("点击上方'执行对标分析'按钮获取分析结果")
    else:
        st.info("点击上方'执行对标分析'按钮获取分析结果")

st.divider()

# ============================================================
# 底部: 定时任务配置
# ============================================================
st.subheader("定时任务")
task_col1, task_col2, task_col3 = st.columns(3)

with task_col1:
    task_type = st.selectbox("分析类型", list(TOOL_LABELS.keys()), format_func=lambda x: TOOL_LABELS[x])
with task_col2:
    interval = st.selectbox("执行周期", [300, 600, 1800, 3600], format_func=lambda x: f"每 {x // 60} 分钟")
with task_col3:
    st.write("")
    st.write("")
    if st.button("添加定时任务", use_container_width=True):
        st.session_state.trigger_engine.add_scheduled_task(task_type, interval)
        st.success(f"已添加: 每 {interval // 60} 分钟执行{TOOL_LABELS[task_type]}")
        st.rerun()

# 已配置的定时任务
tasks = st.session_state.trigger_engine.get_scheduled_tasks()
if tasks:
    for task in tasks:
        t_col1, t_col2, t_col3 = st.columns([3, 2, 1])
        with t_col1:
            st.write(f"**{TOOL_LABELS.get(task['task_type'], task['task_type'])}**")
        with t_col2:
            st.write(f"每 {task['interval_seconds'] // 60} 分钟")
        with t_col3:
            if st.button("删除", key=f"del_{task['job_id']}"):
                st.session_state.trigger_engine.remove_scheduled_task(task["task_type"])
                st.rerun()
else:
    st.info("暂无定时任务，请在上方配置")

# 执行日志
log = st.session_state.trigger_engine.get_execution_log(5)
if log:
    with st.expander("执行日志（最近 5 条）"):
        for entry in reversed(log):
            icon = "✅" if entry["status"] == "success" else "❌"
            st.write(
                f"{icon} [{entry['timestamp'][:19]}] "
                f"{entry['trigger_type']} - {TOOL_LABELS.get(entry['task_type'], entry['task_type'])}"
            )


# ============================================================
# 侧边栏: Agent 对话
# ============================================================
with st.sidebar:
    st.header("Agent 对话")
    st.caption("与运营优化 Agent 对话，支持自然语言查询")

    # 显示对话历史
    for msg in st.session_state.chat_history:
        role = msg["role"]
        content = msg["content"]
        if role == "user":
            st.chat_message("user").write(content)
        else:
            st.chat_message("assistant").write(content)

    # 对话输入
    if prompt := st.chat_input("输入你的问题..."):
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        st.chat_message("user").write(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Agent 分析中..."):
                try:
                    result = st.session_state.scheduler.dispatch(prompt)
                    answer = result.get("answer", "抱歉，分析过程中出现问题。")
                    st.write(answer)

                    st.session_state.chat_history.append({"role": "assistant", "content": answer})

                    # 对话中触发的分析结果同步到面板
                    for tr in result.get("tool_results", []):
                        tool_name = tr.get("tool")
                        if tool_name in st.session_state.analysis_results:
                            st.session_state.analysis_results[tool_name] = tr.get("result")
                except Exception as e:
                    error_msg = f"分析出错: {e}"
                    st.error(error_msg)
                    st.session_state.chat_history.append({"role": "assistant", "content": error_msg})
