"""触发引擎 — 管理一键触发、定时触发和条件触发。"""

import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)


class TriggerEngine:
    """统一管理三种触发方式。"""

    def __init__(self):
        self._scheduler = BackgroundScheduler()
        self._callbacks: dict[str, callable] = {}
        self._task_configs: dict[str, dict] = {}
        self._execution_log: list[dict] = []

    def register_callback(self, task_type: str, callback: callable):
        """注册任务回调函数。当触发执行时调用此函数。"""
        self._callbacks[task_type] = callback

    def trigger_now(self, task_type: str) -> dict:
        """一键触发 — 立即执行指定分析任务。"""
        callback = self._callbacks.get(task_type)
        if callback is None:
            return {"error": f"未注册的任务类型: {task_type}"}

        logger.info("一键触发执行: %s", task_type)
        result = callback(task_type)
        self._log_execution(task_type, "manual", result)
        return result

    def add_scheduled_task(self, task_type: str, interval_seconds: int) -> bool:
        """添加定时触发任务。"""
        job_id = f"scheduled_{task_type}"

        # 移除已有任务
        if self._scheduler.get_job(job_id):
            self._scheduler.remove_job(job_id)

        callback = self._callbacks.get(task_type)
        if callback is None:
            logger.error("未注册的任务类型: %s", task_type)
            return False

        self._scheduler.add_job(
            func=self._execute_scheduled,
            trigger=IntervalTrigger(seconds=interval_seconds),
            id=job_id,
            args=[task_type],
            name=f"定时{task_type}",
        )

        self._task_configs[job_id] = {
            "task_type": task_type,
            "interval_seconds": interval_seconds,
            "enabled": True,
        }

        logger.info("添加定时任务: %s, 间隔 %d 秒", task_type, interval_seconds)
        return True

    def remove_scheduled_task(self, task_type: str):
        """移除定时触发任务。"""
        job_id = f"scheduled_{task_type}"
        if self._scheduler.get_job(job_id):
            self._scheduler.remove_job(job_id)
        self._task_configs.pop(job_id, None)

    def start(self):
        """启动调度器。"""
        if not self._scheduler.running:
            self._scheduler.start()
            logger.info("触发引擎已启动")

    def stop(self):
        """停止调度器。"""
        if self._scheduler.running:
            self._scheduler.shutdown()
            logger.info("触发引擎已停止")

    def get_scheduled_tasks(self) -> list[dict]:
        """获取所有定时任务配置。"""
        return [
            {
                "job_id": job_id,
                **config,
            }
            for job_id, config in self._task_configs.items()
        ]

    def get_execution_log(self, limit: int = 20) -> list[dict]:
        """获取执行日志。"""
        return self._execution_log[-limit:]

    def _execute_scheduled(self, task_type: str):
        """定时任务执行回调。"""
        callback = self._callbacks.get(task_type)
        if callback is None:
            return

        logger.info("定时触发执行: %s", task_type)
        result = callback(task_type)
        self._log_execution(task_type, "scheduled", result)

    def _log_execution(self, task_type: str, trigger_type: str, result: dict):
        self._execution_log.append({
            "timestamp": datetime.now().isoformat(),
            "task_type": task_type,
            "trigger_type": trigger_type,
            "status": "success" if "error" not in result else "error",
        })
