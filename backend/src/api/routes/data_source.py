"""数据源管理 API — 配置、测试外部时序数据接口。"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.services.source_service import (
    list_sources, get_source, add_source, update_source,
    delete_source, test_connection,
)

logger = logging.getLogger(__name__)
router = APIRouter()


class SourceCreate(BaseModel):
    name: str
    source_type: str  # http_api / opcua / mqtt
    connection_config: dict = {}
    parameter_mapping: dict = {}
    polling_interval_sec: int = 60
    enabled: bool = False


class SourceUpdate(BaseModel):
    name: str | None = None
    connection_config: dict | None = None
    parameter_mapping: dict | None = None
    polling_interval_sec: int | None = None
    enabled: bool | None = None


@router.get("/list")
async def api_list_sources():
    return {"sources": list_sources(), "total": len(list_sources())}


@router.get("/{source_id}")
async def api_get_source(source_id: str):
    result = get_source(source_id)
    if not result:
        raise HTTPException(404, "数据源不存在")
    return result


@router.post("")
async def api_add_source(data: SourceCreate):
    return add_source(data.model_dump())


@router.put("/{source_id}")
async def api_update_source(source_id: str, data: SourceUpdate):
    result = update_source(source_id, data.model_dump(exclude_unset=True))
    if not result.get("success"):
        raise HTTPException(404, result.get("message"))
    return result


@router.delete("/{source_id}")
async def api_delete_source(source_id: str):
    result = delete_source(source_id)
    if not result.get("success"):
        raise HTTPException(404, result.get("message"))
    return result


@router.post("/{source_id}/test")
async def api_test_connection(source_id: str):
    return test_connection(source_id)
