"""数据保留策略 — 按配置天数自动清理过期时序数据。"""

import logging
from datetime import datetime, timedelta

from src.config import get_settings
from src.db.engine import get_session
from src.db.models import TimeSeriesPoint

logger = logging.getLogger(__name__)


def run_retention_cleanup():
    """执行数据保留清理。删除超过 retention_days 的时序数据。"""
    settings = get_settings()
    retention_days = settings.data_retention_days
    cutoff = datetime.now() - timedelta(days=retention_days)

    batch_size = 10000
    total_deleted = 0

    with get_session() as session:
        while True:
            count = (
                session.query(TimeSeriesPoint)
                .filter(TimeSeriesPoint.timestamp < cutoff)
                .limit(batch_size)
                .delete()
            )
            session.commit()
            total_deleted += count
            if count < batch_size:
                break
            logger.info("保留策略: 已删除 %d 条过期数据，继续...", total_deleted)

    if total_deleted > 0:
        logger.info("保留策略: 共清理 %d 条过期数据 (保留 %d 天)", total_deleted, retention_days)
    return total_deleted
