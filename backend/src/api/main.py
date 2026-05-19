"""FastAPI 主应用 — 提供所有 REST API 和 WebSocket 接口。v1.6"""

import sys
import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 确保 backend/src 在 Python 路径中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.agents.optimization_agent import OptimizationAgent
from src.core.scheduler import Scheduler
from src.core.trigger_engine import TriggerEngine
from src.knowledge.wiki_manager import WikiManager

from src.api.routes import monitoring, analysis, chat, chat_sessions, schedule, warning, dictionary, knowledge, workflow

logger = logging.getLogger(__name__)


def _migrate_mock_to_wiki(wiki_mgr: WikiManager):
    """首次启动时，将 mock 检维修数据迁移为 wiki 词条。"""
    if not wiki_mgr.is_empty():
        return
    logger.info("Wiki 为空，执行 mock 数据迁移...")

    TYPE_MAP = {
        "检修规程": "content_summary",
        "故障诊断": "content_summary",
        "处理案例": "content_summary",
        "检测标准": "concept",
    }

    for item in knowledge.KNOWLEDGE_BASE["maintenance"]:
        frontmatter = {
            "title": item["title"],
            "type": TYPE_MAP.get(item.get("type", ""), "content_summary"),
            "category": item["category"],
            "tags": item.get("keywords", []),
            "equipment": item.get("equipment", ""),
            "severity": item.get("severity", "中"),
            "source_file": "initial_migration",
            "concept_subcategory": "规程" if item.get("type") == "检修规程" else None,
        }
        content_parts = []
        if item.get("symptoms"):
            content_parts.append(f"## 故障现象\n\n{item['symptoms']}")
        if item.get("analysis"):
            content_parts.append(f"## 原因分析\n\n{item['analysis']}")
        if item.get("solution"):
            content_parts.append(f"## 处理方案\n\n{item['solution']}")
        if item.get("prevention"):
            content_parts.append(f"## 预防措施\n\n{item['prevention']}")
        content = "\n\n".join(content_parts)

        wiki_mgr.create_entry(frontmatter, content)

    wiki_mgr.rebuild_index()
    wiki_mgr.append_log("系统初始化", f"迁移 {len(knowledge.KNOWLEDGE_BASE['maintenance'])} 条 mock 检维修数据为 wiki 词条")
    logger.info("Mock 数据迁移完成，共 %d 条", len(knowledge.KNOWLEDGE_BASE["maintenance"]))


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

    # 初始化 Wiki 知识库管理器
    knowledge_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "knowledge"))
    wiki_manager = WikiManager(knowledge_root)
    _migrate_mock_to_wiki(wiki_manager)

    app.state.scheduler = scheduler
    app.state.trigger_engine = trigger_engine
    app.state.agent = agent
    app.state.wiki_manager = wiki_manager

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
app.include_router(chat_sessions.router, prefix="/api/chat", tags=["智能对话"])
app.include_router(schedule.router, prefix="/api/schedule", tags=["调度管理"])
app.include_router(warning.router, prefix="/api/warning", tags=["预警管理"])
app.include_router(dictionary.router, prefix="/api/dictionary", tags=["数据字典"])
app.include_router(knowledge.router, prefix="/api/knowledge", tags=["模型与知识库"])
app.include_router(workflow.router, prefix="/api/workflow", tags=["工作流编排"])


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}
