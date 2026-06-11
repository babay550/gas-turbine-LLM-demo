"""数据导入 API — 历史数据文件上传、预览、列映射、入库。"""

import logging

from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel

from src.services.import_service import (
    upload_file,
    execute_import,
    get_job_status,
    get_job_preview,
    list_jobs,
    delete_job,
    ALLOWED_EXTENSIONS,
    get_timestamp_format_presets,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ────────────────── 请求模型 ──────────────────

class ColumnMapping(BaseModel):
    timestamp_column: str
    timestamp_format: str | None = None
    format_type: str = "wide"  # wide / long
    unit_id: str = "GT-01"
    # 宽表: 文件列名 → 参数key (值 "skip" 表示跳过该列)
    column_map: dict[str, str] | None = None
    # 长表额外字段
    long_param_column: str | None = None
    long_value_column: str | None = None


# ────────────────── API 端点 ──────────────────

@router.post("/upload")
async def api_upload_file(file: UploadFile = File(...)):
    """上传历史数据文件，解析表头和预览数据。

    返回: job_id, columns, preview_rows, row_count, detected_timestamp_column, format_hint
    """
    filename = file.filename or "unknown"
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"不支持的文件格式: {ext}，支持: {ALLOWED_EXTENSIONS}")

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(400, "文件为空")

    result = upload_file(content, filename)
    if result.get("status") == "error":
        raise HTTPException(400, result.get("error_message", "文件解析失败"))

    return result


@router.get("/jobs")
async def api_list_jobs():
    """列出所有导入任务。"""
    return {"jobs": list_jobs(), "total": len(list_jobs())}


@router.post("/{job_id}/execute")
async def api_execute_import(job_id: int, mapping: ColumnMapping):
    """执行数据导入（需先上传文件获取 job_id）。"""
    try:
        result = execute_import(job_id, mapping.model_dump())
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.exception("导入执行失败 job_id=%d", job_id)
        raise HTTPException(500, f"导入失败: {e}")


@router.get("/{job_id}/status")
async def api_get_job_status(job_id: int):
    """查询导入任务状态。"""
    result = get_job_status(job_id)
    if not result:
        raise HTTPException(404, "任务不存在")
    return result


@router.get("/{job_id}/preview")
async def api_get_job_preview(job_id: int):
    """从历史任务恢复文件预览数据（用于重新配置列映射）。"""
    result = get_job_preview(job_id)
    if not result:
        raise HTTPException(404, "任务不存在或文件已丢失")
    return result


@router.get("/time-formats")
async def api_get_time_formats():
    """返回客户端可用的时间格式预设（用于下拉选择）。"""
    try:
        presets = get_timestamp_format_presets()
        return {"presets": presets}
    except Exception as e:
        logger.exception("获取时间格式预设失败: %s", e)
        raise HTTPException(500, "无法获取时间格式预设")


@router.delete("/{job_id}")
async def api_delete_job(job_id: int):
    """删除导入任务及其关联数据。"""
    result = delete_job(job_id)
    if not result.get("success"):
        raise HTTPException(404, result.get("message", "删除失败"))
    return result
