"""
Cron 类型定义

对应 OpenClaw 的 Cron 类型系统：
  - CronJob: 定时任务定义
  - CronJobStatus: 任务运行状态
  - CronEvent: 任务事件
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class CronJobStatus(str, Enum):
    """定时任务状态"""
    IDLE = "idle"
    RUNNING = "running"
    DISABLED = "disabled"
    ERROR = "error"


class CronEventType(str, Enum):
    """定时任务事件类型"""
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    MISSED = "missed"


@dataclass
class CronJob:
    """定时任务定义

    对应 OpenClaw 的 CronJob，描述一个定时执行的 Agent 任务。
    """
    id: str
    name: str
    schedule: str  # cron 表达式
    prompt: str    # 执行时发送给 Agent 的提示
    agent_id: str = "agentic_loop"
    enabled: bool = True
    last_run_at: Optional[float] = None
    next_run_at: Optional[float] = None
    run_count: int = 0
    error_count: int = 0
    created_at: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CronEvent:
    """定时任务事件"""
    job_id: str
    event_type: CronEventType
    timestamp: float
    error: Optional[str] = None
    result: Optional[Any] = None


@dataclass
class CronRunRecord:
    """任务执行记录"""
    job_id: str
    started_at: float
    completed_at: Optional[float] = None
    success: bool = False
    error: Optional[str] = None
    result: Optional[Any] = None
