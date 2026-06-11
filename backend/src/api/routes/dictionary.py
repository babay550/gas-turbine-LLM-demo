"""数据字典 API — 参数定义、基准值配置、对标指标。

从 v1.8 起所有数据从 SQLite 数据库读写，首次启动自动 seed。
"""

import json
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.db.engine import get_session
from src.db.models import Parameter, BaselineConfig, BenchmarkIndicator, LossVariableConfig, WaterfallConfig

logger = logging.getLogger(__name__)
router = APIRouter()

# ──────────── 旧硬编码数据（仅用于首次 seed） ────────────
# 保留原列表供 engine.py 的 _seed_if_empty() 使用

PARAMETERS = [
    # === 压气机 ===
    {"id": "P001", "name": "压气机进口温度 T1", "unit": "°C", "location": "压气机进口", "normal_range": [10, 40], "source": "时序数据库", "update_freq": "1s"},
    {"id": "P002", "name": "压气机进口压力 P1", "unit": "MPa", "location": "压气机进口", "normal_range": [0.09, 0.11], "source": "时序数据库", "update_freq": "1s"},
    {"id": "P003", "name": "压气机出口温度 T2", "unit": "°C", "location": "压气机出口", "normal_range": [380, 460], "source": "时序数据库", "update_freq": "1s"},
    {"id": "P004", "name": "压气机出口压力 P2", "unit": "MPa", "location": "压气机出口", "normal_range": [1.2, 1.9], "source": "时序数据库", "update_freq": "1s"},
    {"id": "P005", "name": "空气流量", "unit": "kg/s", "location": "压气机出口", "normal_range": [480, 720], "source": "时序数据库", "update_freq": "1s"},
    # === 燃烧室 ===
    {"id": "P006", "name": "透平进口温度 T3", "unit": "°C", "location": "燃烧室出口", "normal_range": [1050, 1350], "source": "时序数据库", "update_freq": "1s"},
    {"id": "P007", "name": "燃烧室出口压力 P3", "unit": "MPa", "location": "燃烧室出口", "normal_range": [1.1, 1.8], "source": "时序数据库", "update_freq": "1s"},
    {"id": "P008", "name": "天然气瞬时流量", "unit": "万Nm³/h", "location": "燃料入口", "normal_range": [4.0, 7.0], "source": "时序数据库", "update_freq": "1s"},
    {"id": "P009", "name": "天然气累计流量", "unit": "万Nm³", "location": "燃料入口", "normal_range": [0, 99999], "source": "时序数据库", "update_freq": "1h"},
    {"id": "P010", "name": "燃气温度", "unit": "°C", "location": "燃料入口", "normal_range": [0, 40], "source": "时序数据库", "update_freq": "1s"},
    {"id": "P011", "name": "燃气压力", "unit": "MPa", "location": "燃料入口", "normal_range": [1.5, 4.0], "source": "时序数据库", "update_freq": "1s"},
    {"id": "P012", "name": "天然气低位热值", "unit": "MJ/Nm³", "location": "化验室", "normal_range": [31, 38], "source": "定期化验", "update_freq": "1天"},
    {"id": "P013", "name": "排烟含氧量", "unit": "%", "location": "烟囱", "normal_range": [10, 18], "source": "时序数据库", "update_freq": "1s"},
    {"id": "P014", "name": "CO排放", "unit": "ppm", "location": "烟囱", "normal_range": [0, 20], "source": "时序数据库", "update_freq": "1s"},
    {"id": "P015", "name": "未燃碳氢", "unit": "ppm", "location": "烟囱", "normal_range": [0, 10], "source": "时序数据库", "update_freq": "1s"},
    # === 透平 ===
    {"id": "P016", "name": "透平出口温度 T4", "unit": "°C", "location": "透平出口", "normal_range": [500, 600], "source": "时序数据库", "update_freq": "1s"},
    {"id": "P017", "name": "透平出口压力 P4", "unit": "MPa", "location": "透平出口", "normal_range": [0.09, 0.11], "source": "时序数据库", "update_freq": "1s"},
    # === 发电机 ===
    {"id": "P018", "name": "发电机有功功率", "unit": "MW", "location": "发电机出口", "normal_range": [160, 230], "source": "时序数据库", "update_freq": "1s"},
    {"id": "P019", "name": "累计发电量", "unit": "MWh", "location": "发电机出口", "normal_range": [0, 999999], "source": "时序数据库", "update_freq": "1h"},
    # === 汽机侧 ===
    {"id": "P020", "name": "主蒸汽流量", "unit": "t/h", "location": "余热锅炉出口", "normal_range": [50, 100], "source": "时序数据库", "update_freq": "1s"},
    {"id": "P021", "name": "主蒸汽温度", "unit": "°C", "location": "余热锅炉出口", "normal_range": [470, 550], "source": "时序数据库", "update_freq": "1s"},
    {"id": "P022", "name": "主蒸汽压力", "unit": "MPa", "location": "余热锅炉出口", "normal_range": [3.0, 5.5], "source": "时序数据库", "update_freq": "1s"},
    {"id": "P023", "name": "汽机发电功率", "unit": "MW", "location": "汽轮发电机", "normal_range": [70, 130], "source": "时序数据库", "update_freq": "1s"},
    # === 余热锅炉 ===
    {"id": "P024", "name": "HRB进口烟温", "unit": "°C", "location": "余热锅炉进口", "normal_range": [500, 600], "source": "时序数据库", "update_freq": "1s"},
    {"id": "P025", "name": "HRB出口烟温", "unit": "°C", "location": "余热锅炉出口", "normal_range": [70, 130], "source": "时序数据库", "update_freq": "1s"},
    {"id": "P026", "name": "HRB蒸汽温度", "unit": "°C", "location": "余热锅炉", "normal_range": [470, 540], "source": "时序数据库", "update_freq": "1s"},
    {"id": "P027", "name": "HRB蒸汽压力", "unit": "MPa", "location": "余热锅炉", "normal_range": [2.5, 5.0], "source": "时序数据库", "update_freq": "1s"},
    # === 其他 ===
    {"id": "P028", "name": "振动_轴向", "unit": "mm/s", "location": "轴承座", "normal_range": [0, 7.0], "source": "时序数据库", "update_freq": "1s"},
    {"id": "P029", "name": "振动_垂向", "unit": "mm/s", "location": "轴承座", "normal_range": [0, 7.0], "source": "时序数据库", "update_freq": "1s"},
]

BASELINE_CONFIGS = [
    {"parameter_id": "P003", "parameter_name": "压气机出口温度 T2", "model_type": "多元回归", "features": ["负荷率", "进口温度 T1", "进口压力 P1"], "accuracy": 0.98},
    {"parameter_id": "P016", "parameter_name": "透平出口温度 T4", "model_type": "多元回归", "features": ["负荷率", "环境温度", "透平进口温度 T3"], "accuracy": 0.97},
    {"parameter_id": "P008", "parameter_name": "天然气瞬时流量", "model_type": "设计值插值", "features": ["负荷指令", "发电功率"], "accuracy": 0.99},
    {"parameter_id": "P018", "parameter_name": "发电机有功功率", "model_type": "热力模型", "features": ["天然气流量", "热值", "压气机效率"], "accuracy": 0.96},
]

BENCHMARK_INDICATORS = [
    {"id": "B001", "name": "厂用电率", "unit": "%", "source": "对标分析模型", "peer_avg": 4.8},
    {"id": "B002", "name": "利用小时", "unit": "h", "source": "对标分析模型", "peer_avg": 4200},
    {"id": "B003", "name": "平均发电负荷", "unit": "MW", "source": "对标分析模型", "peer_avg": 200},
    {"id": "B004", "name": "负荷率", "unit": "%", "source": "对标分析模型", "peer_avg": 90},
    {"id": "B005", "name": "发电计划完成率", "unit": "%", "source": "对标分析模型", "peer_avg": 95},
    {"id": "B006", "name": "热电比", "unit": "", "source": "对标分析模型", "peer_avg": 0.85},
    {"id": "B007", "name": "售电收入", "unit": "万元", "source": "对标分析模型", "peer_avg": 12000},
]


# ──────────── 请求模型 ────────────

class ParameterCreate(BaseModel):
    name: str
    unit: str
    subsystem: str = "其他"
    location: str = ""
    normal_min: float | None = None
    normal_max: float | None = None
    source: str = "时序数据库"
    update_freq: str = "1s"
    description: str = ""


class ParameterUpdate(BaseModel):
    name: str | None = None
    unit: str | None = None
    subsystem: str | None = None
    location: str | None = None
    normal_min: float | None = None
    normal_max: float | None = None
    source: str | None = None
    update_freq: str | None = None
    description: str | None = None


# ──────────── 参数 CRUD ────────────

@router.get("/parameters")
async def get_parameters():
    """获取监测参数定义列表。"""
    with get_session() as session:
        params = session.query(Parameter).order_by(Parameter.id).all()
        result = [p.to_dict() for p in params]
        return {"parameters": result, "total": len(result)}


@router.post("/parameters")
async def create_parameter(data: ParameterCreate):
    """新增监测参数。"""
    with get_session() as session:
        # 生成 ID
        max_id = session.query(Parameter).order_by(Parameter.id.desc()).first()
        next_num = (int(max_id.id[1:]) + 1) if max_id else 1
        new_id = f"P{next_num:03d}"
        key = data.name.replace(" ", "_")

        param = Parameter(
            id=new_id,
            name=data.name,
            key=key,
            unit=data.unit,
            subsystem=data.subsystem,
            location=data.location,
            normal_min=data.normal_min,
            normal_max=data.normal_max,
            source=data.source,
            update_freq=data.update_freq,
            description=data.description,
        )
        session.add(param)
        session.commit()
        return {"success": True, "id": new_id, "message": f"参数 {data.name} 已添加"}


@router.put("/parameters/{param_id}")
async def update_parameter(param_id: str, data: ParameterUpdate):
    """修改监测参数。"""
    with get_session() as session:
        param = session.query(Parameter).filter(Parameter.id == param_id).first()
        if not param:
            raise HTTPException(404, "参数不存在")
        update_data = data.model_dump(exclude_unset=True)
        for k, v in update_data.items():
            setattr(param, k, v)
        if "name" in update_data:
            param.key = update_data["name"].replace(" ", "_")
        param.updated_at = datetime.now()
        session.commit()
        return {"success": True, "message": "参数已更新"}


@router.delete("/parameters/{param_id}")
async def delete_parameter(param_id: str):
    """删除监测参数。"""
    with get_session() as session:
        param = session.query(Parameter).filter(Parameter.id == param_id).first()
        if not param:
            raise HTTPException(404, "参数不存在")
        session.delete(param)
        session.commit()
        return {"success": True, "message": "参数已删除"}


# ──────────── 基准值配置 CRUD ────────────

@router.get("/baselines")
async def get_baselines():
    """获取动态基准值模型配置。"""
    with get_session() as session:
        configs = session.query(BaselineConfig).all()
        result = [bc.to_dict() for bc in configs]
        return {"baselines": result, "total": len(result)}


# ──────────── 对标指标 CRUD ────────────

@router.get("/benchmark-indicators")
async def get_benchmark_indicators():
    """获取对标指标配置。"""
    with get_session() as session:
        indicators = session.query(BenchmarkIndicator).order_by(BenchmarkIndicator.id).all()
        result = [bi.to_dict() for bi in indicators]
        return {"indicators": result, "total": len(result)}


# ──────────── 损失项配置 CRUD ────────────

class LossVariableCreate(BaseModel):
    param_key: str
    name: str
    unit: str
    baseline: float
    best: float


class LossVariableUpdate(BaseModel):
    param_key: str | None = None
    name: str | None = None
    unit: str | None = None
    baseline: float | None = None
    best: float | None = None
    sort_order: int | None = None


@router.get("/loss-variables")
async def get_loss_variables():
    """获取所有损失项配置。"""
    with get_session() as session:
        items = session.query(LossVariableConfig).order_by(LossVariableConfig.sort_order, LossVariableConfig.id).all()
        return {"variables": [i.to_dict() for i in items], "total": len(items)}


@router.post("/loss-variables")
async def create_loss_variable(data: LossVariableCreate):
    """新增损失项配置。"""
    with get_session() as session:
        max_order = session.query(LossVariableConfig).order_by(LossVariableConfig.sort_order.desc()).first()
        next_order = (max_order.sort_order + 1) if max_order else 0
        item = LossVariableConfig(
            param_key=data.param_key,
            name=data.name,
            unit=data.unit,
            baseline=data.baseline,
            best=data.best,
            sort_order=next_order,
        )
        session.add(item)
        session.commit()
        session.refresh(item)
        return {"success": True, "id": item.id, "variable": item.to_dict()}


@router.put("/loss-variables/{item_id}")
async def update_loss_variable(item_id: int, data: LossVariableUpdate):
    """更新损失项配置。"""
    with get_session() as session:
        item = session.query(LossVariableConfig).filter(LossVariableConfig.id == item_id).first()
        if not item:
            raise HTTPException(404, "损失项不存在")
        update_data = data.model_dump(exclude_unset=True)
        for k, v in update_data.items():
            setattr(item, k, v)
        item.updated_at = datetime.now()
        session.commit()
        session.refresh(item)
        return {"success": True, "variable": item.to_dict()}


@router.delete("/loss-variables/{item_id}")
async def delete_loss_variable(item_id: int):
    """删除损失项配置。"""
    with get_session() as session:
        item = session.query(LossVariableConfig).filter(LossVariableConfig.id == item_id).first()
        if not item:
            raise HTTPException(404, "损失项不存在")
        session.delete(item)
        session.commit()
        return {"success": True, "message": "损失项已删除"}


# ──────────── 瀑布图配置 ────────────

class WaterfallConfigUpdate(BaseModel):
    total_key: str = ""
    subsystem_keys: list[str] = []


@router.get("/waterfall-config")
async def get_waterfall_config():
    """获取瀑布图全局配置。"""
    with get_session() as session:
        config = session.query(WaterfallConfig).first()
        if not config:
            return {"total_key": "", "subsystem_keys": []}
        return config.to_dict()


@router.put("/waterfall-config")
async def save_waterfall_config(data: WaterfallConfigUpdate):
    """保存瀑布图全局配置。"""
    with get_session() as session:
        config = session.query(WaterfallConfig).first()
        if not config:
            config = WaterfallConfig(
                total_key=data.total_key,
                subsystem_keys=json.dumps(data.subsystem_keys, ensure_ascii=False),
            )
            session.add(config)
        else:
            config.total_key = data.total_key
            config.subsystem_keys = json.dumps(data.subsystem_keys, ensure_ascii=False)
            config.updated_at = datetime.now()
        session.commit()
        session.refresh(config)
        return {"success": True, "config": config.to_dict()}
