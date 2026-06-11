"""数据源管理服务 — 配置、测试、同步外部时序数据源。

先实现 HTTP API 类型，OPC-UA / MQTT 后续扩展。
"""

import json
import logging
from datetime import datetime

import requests

from src.db.engine import get_session
from src.db.models import DataSource

logger = logging.getLogger(__name__)


def list_sources() -> list[dict]:
    """列出所有数据源。"""
    with get_session() as session:
        sources = session.query(DataSource).order_by(DataSource.id).all()
        return [s.to_dict() for s in sources]


def get_source(source_id: str) -> dict | None:
    with get_session() as session:
        s = session.query(DataSource).filter(DataSource.id == source_id).first()
        return s.to_dict() if s else None


def add_source(data: dict) -> dict:
    """新增数据源。"""
    with get_session() as session:
        # 生成 ID
        max_id = session.query(DataSource).order_by(DataSource.id.desc()).first()
        next_num = (int(max_id.id[2:]) + 1) if max_id else 1
        new_id = f"DS{next_num:03d}"

        source = DataSource(
            id=new_id,
            name=data["name"],
            source_type=data["source_type"],
            connection_config=json.dumps(data.get("connection_config", {}), ensure_ascii=False),
            parameter_mapping=json.dumps(data.get("parameter_mapping", {}), ensure_ascii=False),
            polling_interval_sec=data.get("polling_interval_sec", 60),
            enabled=data.get("enabled", False),
        )
        session.add(source)
        session.commit()
        return {"success": True, "id": new_id, "message": f"数据源 {data['name']} 已添加"}


def update_source(source_id: str, data: dict) -> dict:
    with get_session() as session:
        source = session.query(DataSource).filter(DataSource.id == source_id).first()
        if not source:
            return {"success": False, "message": "数据源不存在"}
        for k, v in data.items():
            if k in ("connection_config", "parameter_mapping") and isinstance(v, dict):
                v = json.dumps(v, ensure_ascii=False)
            if hasattr(source, k):
                setattr(source, k, v)
        source.updated_at = datetime.now()
        session.commit()
        return {"success": True, "message": "数据源已更新"}


def delete_source(source_id: str) -> dict:
    with get_session() as session:
        source = session.query(DataSource).filter(DataSource.id == source_id).first()
        if not source:
            return {"success": False, "message": "数据源不存在"}
        session.delete(source)
        session.commit()
        return {"success": True, "message": "数据源已删除"}


def test_connection(source_id: str) -> dict:
    """测试数据源连通性。"""
    with get_session() as session:
        source = session.query(DataSource).filter(DataSource.id == source_id).first()
        if not source:
            return {"success": False, "message": "数据源不存在"}

    config = json.loads(source.connection_config) if source.connection_config else {}

    if source.source_type == "http_api":
        return _test_http_api(config)
    elif source.source_type == "opcua":
        return {"success": False, "message": "OPC-UA 暂未实现"}
    elif source.source_type == "mqtt":
        return {"success": False, "message": "MQTT 暂未实现"}
    else:
        return {"success": False, "message": f"不支持的数据源类型: {source.source_type}"}


def _test_http_api(config: dict) -> dict:
    """测试 HTTP API 连通性。"""
    url = config.get("url")
    if not url:
        return {"success": False, "message": "缺少 url 配置"}

    method = config.get("method", "GET").upper()
    headers = config.get("headers", {})
    timeout = config.get("timeout", 10)

    try:
        start = datetime.now()
        if method == "GET":
            resp = requests.get(url, headers=headers, timeout=timeout)
        else:
            resp = requests.post(url, headers=headers, timeout=timeout)
        elapsed = (datetime.now() - start).total_seconds() * 1000

        return {
            "success": resp.status_code < 400,
            "status_code": resp.status_code,
            "latency_ms": round(elapsed, 1),
            "message": f"HTTP {resp.status_code}, {elapsed:.0f}ms",
        }
    except Exception as e:
        return {"success": False, "message": str(e)}
