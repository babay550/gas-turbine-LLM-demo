"""预警管理 API — 预警列表、预警详情。"""

from datetime import datetime
import random
from fastapi import APIRouter

router = APIRouter()

# Mock 预警数据
MOCK_WARNINGS = [
    {"id": "W001", "level": "高", "source": "预警诊断模型", "message": "排气温度超限", "parameter": "排气温度", "value": 585.2, "threshold": 580.0, "unit": "°C", "time": "2026-05-10 08:32:15", "status": "active"},
    {"id": "W002", "level": "中", "source": "预警诊断模型", "message": "压气机效率下降趋势", "parameter": "压气机效率", "value": 86.2, "threshold": 88.0, "unit": "%", "time": "2026-05-10 07:15:42", "status": "active"},
    {"id": "W003", "level": "低", "source": "能效分析模型", "message": "热耗率偏差增大", "parameter": "热耗率", "value": 8450, "threshold": 8200, "unit": "kJ/kWh", "time": "2026-05-10 06:00:00", "status": "active"},
    {"id": "W004", "level": "中", "source": "振动监测", "message": "透平轴向振动偏高", "parameter": "振动_轴向", "value": 5.8, "threshold": 5.0, "unit": "mm/s", "time": "2026-05-09 22:10:33", "status": "resolved"},
    {"id": "W005", "level": "高", "source": "预警诊断模型", "message": "燃烧器喷嘴压差异常", "parameter": "燃烧器压差", "value": 2.1, "threshold": 1.8, "unit": "kPa", "time": "2026-05-09 18:45:20", "status": "resolved"},
]


@router.get("/list")
async def get_warnings(status: str = None):
    """获取预警列表。"""
    warnings = MOCK_WARNINGS
    if status:
        warnings = [w for w in warnings if w["status"] == status]
    return {"warnings": warnings, "total": len(warnings)}


@router.get("/{warning_id}")
async def get_warning_detail(warning_id: str):
    """获取预警详情。"""
    warning = next((w for w in MOCK_WARNINGS if w["id"] == warning_id), None)
    if warning is None:
        return {"error": "预警不存在"}
    return {
        **warning,
        "suggestions": [
            "检查燃烧器状态和燃气品质",
            "对比历史同工况参数趋势",
            "关注关联参数变化（振动、温度场）",
        ],
        "history": [
            {"time": "2026-05-08 10:00:00", "value": 575.1, "status": "正常"},
            {"time": "2026-05-09 10:00:00", "value": 579.8, "status": "临界"},
            {"time": "2026-05-10 08:00:00", "value": 585.2, "status": "超限"},
        ],
    }
