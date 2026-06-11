"""数据库引擎 — SQLAlchemy engine + session 管理 + 初始化。"""

import os
import logging
from contextlib import contextmanager

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session

from src.config import get_settings

logger = logging.getLogger(__name__)

_engine = None
_SessionLocal = None


def _get_db_path() -> str:
    """解析数据库文件路径（相对于 backend/ 根目录）。"""
    settings = get_settings()
    db_path = settings.database_path
    if not os.path.isabs(db_path):
        backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        db_path = os.path.join(backend_root, db_path)
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    return db_path


def engine():
    """获取全局 SQLAlchemy engine（懒加载单例）。"""
    global _engine
    if _engine is None:
        db_path = _get_db_path()
        url = f"sqlite:///{db_path}"
        _engine = create_engine(
            url,
            echo=False,
            pool_pre_ping=True,
            connect_args={"check_same_thread": False},
        )
        # WAL 模式 — 提升并发读写性能
        @event.listens_for(_engine, "connect")
        def _set_sqlite_pragma(dbapi_conn, _connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA cache_size=-64000")  # 64MB cache
            cursor.execute("PRAGMA temp_store=MEMORY")
            cursor.close()
        logger.info("数据库引擎初始化完成: %s", db_path)
    return _engine


def _session_factory() -> sessionmaker:
    """获取全局 session 工厂（懒加载）。"""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=engine(), expire_on_commit=False)
    return _SessionLocal


@contextmanager
def get_session() -> Session:
    """获取数据库 session 的上下文管理器，自动 commit/rollback。"""
    SessionCls = _session_factory()
    session = SessionCls()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _fix_sqlite_autoincrement():
    """修复 tsd_time_series.id 列类型: SQLite 只有 INTEGER PRIMARY KEY 才自增，BIGINT 不会。

    检测旧表 → 创建临时表 → 复制数据 → 删除旧表 → 重命名。保留索引。
    """
    try:
        with engine().connect() as conn:
            # 检查表是否存在
            result = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='tsd_time_series'"
            ))
            if not result.fetchone():
                return

            # 检查 id 列类型
            col_info = conn.execute(text("PRAGMA table_info(tsd_time_series)")).fetchall()
            id_col = next((c for c in col_info if c[1] == 'id'), None)
            if not id_col or id_col[2].upper() == 'INTEGER':
                return  # 已经正确，无需迁移

            logger.info("迁移 tsd_time_series.id: %s → INTEGER（修复自增）", id_col[2])

            # 创建新表（INTEGER PRIMARY KEY AUTOINCREMENT）
            conn.execute(text("""
                CREATE TABLE tsd_time_series_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME NOT NULL,
                    unit_id VARCHAR NOT NULL,
                    parameter_key VARCHAR NOT NULL,
                    value FLOAT NOT NULL,
                    quality VARCHAR DEFAULT 'good',
                    source VARCHAR DEFAULT 'import'
                )
            """))

            # 复制已有数据
            conn.execute(text("""
                INSERT INTO tsd_time_series_new (timestamp, unit_id, parameter_key, value, quality, source)
                SELECT timestamp, unit_id, parameter_key, value, quality, source FROM tsd_time_series
            """))

            conn.execute(text("DROP TABLE tsd_time_series"))
            conn.execute(text("ALTER TABLE tsd_time_series_new RENAME TO tsd_time_series"))

            # 重建索引
            conn.execute(text("CREATE INDEX ix_ts_timestamp ON tsd_time_series (timestamp)"))
            conn.execute(text("CREATE INDEX ix_ts_param_time ON tsd_time_series (parameter_key, timestamp)"))
            conn.execute(text("CREATE INDEX ix_ts_unit_time ON tsd_time_series (unit_id, timestamp)"))
            conn.commit()

            logger.info("tsd_time_series 迁移完成")
    except Exception as e:
        logger.warning("tsd_time_series 迁移检查跳过: %s", e)


def init_db():
    """创建所有表 + 首次 seed 数据。"""
    from src.db.models import Base
    # 导入 auth 模型，确保它们的表也注册到 Base.metadata
    import src.auth.models  # noqa: F401
    Base.metadata.create_all(bind=engine())
    _fix_sqlite_autoincrement()
    _seed_if_empty()
    _seed_auth_if_empty()
    logger.info("数据库表初始化完成")


def _seed_if_empty():
    """首次启动时，从现有 dictionary.py 硬编码数据 seed 到数据库。"""
    with get_session() as session:
        from src.db.models import Parameter, BaselineConfig, BenchmarkIndicator

        # 只在表为空时 seed
        if session.query(Parameter).first() is not None:
            return

        logger.info("参数表为空，执行首次 seed...")

        # --- Seed 参数 ---
        from src.api.routes.dictionary import PARAMETERS, BASELINE_CONFIGS, BENCHMARK_INDICATORS

        SUBSYSTEM_MAP = {
            "P001": "压气机", "P002": "压气机", "P003": "压气机",
            "P004": "压气机", "P005": "压气机",
            "P006": "燃烧室", "P007": "燃烧室", "P008": "燃烧室",
            "P009": "燃烧室", "P010": "燃烧室", "P011": "燃烧室",
            "P012": "燃烧室", "P013": "燃烧室", "P014": "燃烧室",
            "P015": "燃烧室",
            "P016": "透平", "P017": "透平",
            "P018": "发电机", "P019": "发电机",
            "P020": "汽机", "P021": "汽机", "P022": "汽机", "P023": "汽机",
            "P024": "余热锅炉", "P025": "余热锅炉", "P026": "余热锅炉", "P027": "余热锅炉",
            "P028": "辅助", "P029": "辅助",
        }

        for p in PARAMETERS:
            pid = p["id"]
            name = p["name"]
            # key: 用于 API 交互的标识符，用下划线替换空格
            key = name.replace(" ", "_")
            nr = p.get("normal_range", [None, None])
            param = Parameter(
                id=pid,
                name=name,
                key=key,
                unit=p.get("unit", ""),
                subsystem=SUBSYSTEM_MAP.get(pid, "其他"),
                location=p.get("location", ""),
                normal_min=nr[0] if nr and len(nr) > 0 else None,
                normal_max=nr[1] if nr and len(nr) > 1 else None,
                source=p.get("source", "时序数据库"),
                update_freq=p.get("update_freq", "1s"),
            )
            session.add(param)

        # --- Seed 基准值配置 ---
        for b in BASELINE_CONFIGS:
            import json
            bc = BaselineConfig(
                parameter_id=b["parameter_id"],
                parameter_name=b["parameter_name"],
                model_type=b["model_type"],
                features=json.dumps(b.get("features", []), ensure_ascii=False),
                accuracy=b.get("accuracy", 0.95),
            )
            session.add(bc)

        # --- Seed 对标指标 ---
        for bi in BENCHMARK_INDICATORS:
            ind = BenchmarkIndicator(
                id=bi["id"],
                name=bi["name"],
                unit=bi.get("unit", ""),
                source=bi.get("source", "对标分析模型"),
                peer_avg=bi.get("peer_avg"),
                description=bi.get("description", ""),
            )
            session.add(ind)

        session.commit()
        logger.info("Seed 完成: %d 参数, %d 基准配置, %d 对标指标",
                     len(PARAMETERS), len(BASELINE_CONFIGS), len(BENCHMARK_INDICATORS))

    # --- Seed 默认损失项配置（独立检查，升级时也需执行） ---
    _seed_loss_variables_if_empty()


def _seed_loss_variables_if_empty():
    """首次启动或升级时 seed 默认损失项配置。"""
    with get_session() as session:
        from src.db.models import LossVariableConfig

        if session.query(LossVariableConfig).first() is not None:
            return

        logger.info("损失项配置表为空，执行首次 seed...")
        default_vars = [
            {"param_key": "压气机出口温度_T2", "name": "压气机效率损失", "unit": "%", "baseline": 0.50, "best": 0.30},
            {"param_key": "透平进口温度_T3", "name": "燃烧效率损失", "unit": "%", "baseline": 0.30, "best": 0.20},
            {"param_key": "透平出口温度_T4", "name": "透平效率损失", "unit": "%", "baseline": 0.40, "best": 0.25},
            {"param_key": "HRB出口烟温", "name": "排气热损失", "unit": "%", "baseline": 3.50, "best": 3.00},
            {"param_key": "发电机有功功率", "name": "机械损失", "unit": "%", "baseline": 1.00, "best": 0.80},
            {"param_key": "发电机有功功率", "name": "发电机损失", "unit": "%", "baseline": 1.20, "best": 1.00},
            {"param_key": "厂用电率", "name": "厂用电消耗", "unit": "%", "baseline": 4.50, "best": 4.00},
        ]
        for i, v in enumerate(default_vars):
            session.add(LossVariableConfig(
                param_key=v["param_key"],
                name=v["name"],
                unit=v["unit"],
                baseline=v["baseline"],
                best=v["best"],
                sort_order=i,
            ))
        session.commit()
        logger.info("损失项配置 seed 完成: %d 项", len(default_vars))


def _seed_auth_if_empty():
    """首次启动时 seed 默认组织和 admin 用户。"""
    from src.auth.models import User, Organization
    from src.auth.password import hash_password

    with get_session() as session:
        if session.query(User).first() is not None:
            return

        logger.info("用户表为空，执行首次 auth seed...")

        # 创建默认组织
        org = Organization(
            name="系统管理部",
            code="SYS_ADMIN",
            description="系统默认管理部门",
        )
        session.add(org)
        session.flush()  # 获取 org.id

        # 创建 admin 用户
        settings = get_settings()
        admin = User(
            username="admin",
            password_hash=hash_password(settings.admin_default_password),
            display_name="系统管理员",
            role="admin",
            org_id=org.id,
        )
        session.add(admin)
        session.commit()
        logger.info("Auth seed 完成: 组织 '%s', 用户 'admin'", org.name)
