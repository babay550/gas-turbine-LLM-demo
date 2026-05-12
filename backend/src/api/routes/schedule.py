"""调度管理 API — 定时任务、条件触发、执行日志。"""

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/tasks")
async def get_scheduled_tasks(request: Request):
    """获取所有定时任务。"""
    engine = request.app.state.trigger_engine
    return engine.get_scheduled_tasks()


@router.post("/tasks")
async def add_scheduled_task(request: Request):
    """添加定时任务。"""
    body = await request.json()
    task_type = body.get("task_type")
    interval_seconds = body.get("interval_seconds", 3600)

    engine = request.app.state.trigger_engine
    success = engine.add_scheduled_task(task_type, interval_seconds)
    return {"success": success}


@router.delete("/tasks/{task_type}")
async def remove_scheduled_task(task_type: str, request: Request):
    """移除定时任务。"""
    engine = request.app.state.trigger_engine
    engine.remove_scheduled_task(task_type)
    return {"success": True}


@router.post("/trigger")
async def trigger_now(request: Request):
    """一键触发执行。"""
    body = await request.json()
    task_type = body.get("task_type")

    engine = request.app.state.trigger_engine
    result = engine.trigger_now(task_type)
    return result


@router.get("/logs")
async def get_execution_logs(request: Request, limit: int = 20):
    """获取执行日志。"""
    engine = request.app.state.trigger_engine
    return engine.get_execution_log(limit)
