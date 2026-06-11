"""ORM 模型 — 时序数据系统全部表定义。"""

from datetime import datetime

from sqlalchemy import (
    Column, Integer, Float, String, Text, Boolean,
    DateTime, Index, ForeignKey,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Parameter(Base):
    """参数定义 — 替代 dictionary.py 硬编码列表。"""
    __tablename__ = "tsd_parameters"

    id = Column(String, primary_key=True)          # P001
    name = Column(String, nullable=False)           # 压气机进口温度 T1
    key = Column(String, nullable=False, unique=True)  # API key
    unit = Column(String, nullable=False)           # °C, MPa, ...
    subsystem = Column(String, nullable=False)      # 压气机, 燃烧室, ...
    location = Column(String)                       # 测点位置
    normal_min = Column(Float)                      # 正常范围下限
    normal_max = Column(Float)                      # 正常范围上限
    source = Column(String, default="时序数据库")
    update_freq = Column(String, default="1s")
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "key": self.key,
            "unit": self.unit,
            "subsystem": self.subsystem,
            "location": self.location or "",
            "normal_range": [self.normal_min, self.normal_max],
            "source": self.source,
            "update_freq": self.update_freq,
            "description": self.description or "",
        }


class TimeSeriesPoint(Base):
    """时序数据点 — 窄表 (timestamp, parameter_key, value)。"""
    __tablename__ = "tsd_time_series"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False)
    unit_id = Column(String, nullable=False, default="GT-01")
    parameter_key = Column(String, nullable=False)
    value = Column(Float, nullable=False)
    quality = Column(String, default="good")        # good / suspect / bad
    source = Column(String, default="import")       # import / scada / manual

    __table_args__ = (
        Index("ix_ts_timestamp", "timestamp"),
        Index("ix_ts_param_time", "parameter_key", "timestamp"),
        Index("ix_ts_unit_time", "unit_id", "timestamp"),
    )


class ImportJob(Base):
    """文件导入任务追踪。"""
    __tablename__ = "tsd_import_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String, nullable=False)
    file_type = Column(String, nullable=False)      # xlsx / csv / json
    file_size = Column(Integer)
    status = Column(String, default="pending")      # pending/parsing/validating/storing/completed/error
    total_rows = Column(Integer, default=0)
    imported_rows = Column(Integer, default=0)
    skipped_rows = Column(Integer, default=0)
    error_message = Column(Text)
    column_mapping = Column(Text)                   # JSON: 用户配置的列映射
    format_type = Column(String, default="wide")    # wide / long
    unit_id = Column(String, default="GT-01")
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.now)

    def to_dict(self):
        return {
            "id": self.id,
            "filename": self.filename,
            "file_type": self.file_type,
            "file_size": self.file_size,
            "status": self.status,
            "total_rows": self.total_rows,
            "imported_rows": self.imported_rows,
            "skipped_rows": self.skipped_rows,
            "error_message": self.error_message,
            "format_type": self.format_type,
            "unit_id": self.unit_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class DataSource(Base):
    """时序数据源配置 — OPC-UA / HTTP API / MQTT 等。"""
    __tablename__ = "tsd_data_sources"

    id = Column(String, primary_key=True)           # DS001
    name = Column(String, nullable=False)
    source_type = Column(String, nullable=False)    # opcua / http_api / mqtt
    connection_config = Column(Text, nullable=False)  # JSON: host/port/auth等
    parameter_mapping = Column(Text)                # JSON: source_tag → parameter_key
    polling_interval_sec = Column(Integer, default=60)
    enabled = Column(Boolean, default=False)
    last_sync = Column(DateTime)
    status = Column(String, default="disconnected")  # connected / disconnected / error
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        import json
        return {
            "id": self.id,
            "name": self.name,
            "source_type": self.source_type,
            "connection_config": json.loads(self.connection_config) if self.connection_config else {},
            "parameter_mapping": json.loads(self.parameter_mapping) if self.parameter_mapping else {},
            "polling_interval_sec": self.polling_interval_sec,
            "enabled": self.enabled,
            "last_sync": self.last_sync.isoformat() if self.last_sync else None,
            "status": self.status,
        }


class BaselineConfig(Base):
    """基准值模型配置。"""
    __tablename__ = "tsd_baseline_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    parameter_id = Column(String, nullable=False)
    parameter_name = Column(String, nullable=False)
    model_type = Column(String, nullable=False)
    features = Column(Text, nullable=False)         # JSON array
    accuracy = Column(Float, default=0.95)
    config_json = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        import json
        return {
            "id": self.id,
            "parameter_id": self.parameter_id,
            "parameter_name": self.parameter_name,
            "model_type": self.model_type,
            "features": json.loads(self.features) if self.features else [],
            "accuracy": self.accuracy,
        }


class BenchmarkIndicator(Base):
    """对标指标配置。"""
    __tablename__ = "tsd_benchmark_indicators"

    id = Column(String, primary_key=True)           # B001
    name = Column(String, nullable=False)
    unit = Column(String)
    source = Column(String, default="对标分析模型")
    peer_avg = Column(Float)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "unit": self.unit or "",
            "source": self.source,
            "peer_avg": self.peer_avg,
            "description": self.description or "",
        }


class LossVariableConfig(Base):
    """耗差分析损失项配置 — 用户配置的损失项变量。"""
    __tablename__ = "tsd_loss_variables"

    id = Column(Integer, primary_key=True, autoincrement=True)
    param_key = Column(String, nullable=False)     # 数据字典参数 key
    name = Column(String, nullable=False)           # 显示名称
    unit = Column(String, nullable=False)
    baseline = Column(Float, nullable=False)         # 基准值（用户配置）
    best = Column(Float, nullable=False)             # 最优值（用户配置）
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        return {
            "id": self.id,
            "param_key": self.param_key,
            "name": self.name,
            "unit": self.unit,
            "baseline": self.baseline,
            "best": self.best,
            "sort_order": self.sort_order,
        }


class WaterfallConfig(Base):
    """瀑布图全局配置。"""
    __tablename__ = "tsd_waterfall_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    total_key = Column(String, default="")           # 总损失变量 key
    subsystem_keys = Column(Text, default="[]")      # JSON: 子系统变量 key 列表
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        import json
        return {
            "id": self.id,
            "total_key": self.total_key or "",
            "subsystem_keys": json.loads(self.subsystem_keys) if self.subsystem_keys else [],
        }
