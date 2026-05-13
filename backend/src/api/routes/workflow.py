"""工作流编排 API — 工作流 CRUD、执行、模板、组件定义。"""

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.core.workflow_engine import NODE_TYPES, TEMPLATES, execute_workflow

router = APIRouter()

# 内存存储（演示用）
_WORKFLOWS: dict[str, dict] = {}


class WorkflowCreateRequest(BaseModel):
    id: str | None = None
    name: str
    description: str = ""
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []


class WorkflowExecuteRequest(BaseModel):
    user_input: str = ""


@router.get("/list")
async def list_workflows():
    return list(_WORKFLOWS.values())


@router.get("/templates")
async def get_templates():
    return TEMPLATES


@router.get("/node-types")
async def get_node_types():
    return NODE_TYPES


@router.get("/{workflow_id}")
async def get_workflow(workflow_id: str):
    wf = _WORKFLOWS.get(workflow_id)
    if not wf:
        raise HTTPException(404, "工作流不存在")
    return wf


@router.post("")
async def save_workflow(req: WorkflowCreateRequest):
    wf_id = req.id or f"wf-{uuid.uuid4().hex[:8]}"
    wf = {
        "id": wf_id,
        "name": req.name,
        "description": req.description,
        "nodes": req.nodes,
        "edges": req.edges,
        "updated_at": datetime.now().isoformat(),
    }
    _WORKFLOWS[wf_id] = wf
    return {"success": True, "id": wf_id}


@router.delete("/{workflow_id}")
async def delete_workflow(workflow_id: str):
    if workflow_id not in _WORKFLOWS:
        raise HTTPException(404, "工作流不存在")
    del _WORKFLOWS[workflow_id]
    return {"success": True}


@router.post("/{workflow_id}/execute")
async def exec_workflow(workflow_id: str, req: WorkflowExecuteRequest):
    # 先查找已保存的工作流，再查模板
    wf_def = _WORKFLOWS.get(workflow_id)
    if not wf_def:
        wf_def = next((t for t in TEMPLATES if t["id"] == workflow_id), None)
    if not wf_def:
        raise HTTPException(404, "工作流不存在")

    result = execute_workflow(wf_def, user_input=req.user_input)
    return result
