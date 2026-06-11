"""
MiniClaw Cron — 定时任务服务

对应 OpenClaw 的 Cron 调度功能，提供：
  - CronService: 定时任务调度服务
  - CronStore: JSON 文件持久化
  - Cron 表达式解析器
  - Gateway 方法注册（cron.list / cron.add / cron.update / cron.remove / cron.run）
"""

from .types import CronEvent, CronEventType, CronJob, CronJobStatus, CronRunRecord
from .parse import parse_cron_expression, calculate_next_run
from .store import CronStore
from .service import (
    CronService,
    get_cron_service,
    register_cron_methods,
)

__all__ = [
    "CronEvent",
    "CronEventType",
    "CronJob",
    "CronJobStatus",
    "CronRunRecord",
    "CronService",
    "CronStore",
    "calculate_next_run",
    "get_cron_service",
    "parse_cron_expression",
    "register_cron_methods",
]
