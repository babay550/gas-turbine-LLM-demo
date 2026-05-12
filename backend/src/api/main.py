"""FastAPI 主应用 — 提供所有 REST API 和 WebSocket 接口。"""

import sys
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 确保 backend/src 在 Python 路径中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.agents.optimization_agent import OptimizationAgent
from src.core.scheduler import Scheduler
from src.core.trigger_engine import TriggerEngine

from src.api.routes import monitoring, analysis, chat, schedule, warning, dictionary, knowledge


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化 Agent、调度器、触发引擎
    agent = OptimizationAgent()
    scheduler = Scheduler()
    scheduler.register_agent(agent)

    trigger_engine = TriggerEngine()
    for tool_name in ["efficiency_analysis", "loss_analysis", "benchmark_analysis"]:
        trigger_engine.register_callback(
            tool_name,
            lambda tt, t=tool_name: scheduler.trigger_direct("optimization_agent", t),
        )
    trigger_engine.start()

    app.state.scheduler = scheduler
    app.state.trigger_engine = trigger_engine
    app.state.agent = agent

    yield

    trigger_engine.stop()


app = FastAPI(
    title="燃气轮机运行优化智能体 API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(monitoring.router, prefix="/api/monitoring", tags=["能效监测"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["分析诊断"])
app.include_router(chat.router, prefix="/api/chat", tags=["智能对话"])
app.include_router(schedule.router, prefix="/api/schedule", tags=["调度管理"])
app.include_router(warning.router, prefix="/api/warning", tags=["预警管理"])
app.include_router(dictionary.router, prefix="/api/dictionary", tags=["数据字典"])
app.include_router(knowledge.router, prefix="/api/knowledge", tags=["模型与知识库"])


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}
