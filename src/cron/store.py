"""
Cron Store — 定时任务持久化

对应 OpenClaw 的 Cron 存储：
  - JSON 文件持久化任务定义
  - 支持增删改查操作
  - 原子写入保证数据安全
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Optional

from loguru import logger

from .types import CronJob


class CronStore:
    """Cron 任务存储

    使用 JSON 文件持久化任务定义。
    写入时使用临时文件 + 原子重命名保证数据完整性。
    """

    def __init__(self, store_path: str | Path) -> None:
        self._path = Path(store_path)
        self._jobs: dict[str, CronJob] = {}
        self._loaded: bool = False

    def load(self) -> None:
        """从文件加载任务定义"""
        if not self._path.exists():
            self._loaded = True
            logger.info(f"Cron store file not found, starting fresh: {self._path}")
            return

        try:
            raw = self._path.read_text(encoding="utf-8")
            data = json.loads(raw)
            if not isinstance(data, dict):
                logger.warning(f"Invalid cron store format, starting fresh: {self._path}")
                self._loaded = True
                return

            for job_id, job_data in data.items():
                if isinstance(job_data, dict):
                    self._jobs[job_id] = CronJob(**job_data)

            self._loaded = True
            logger.info(f"Cron store loaded: {len(self._jobs)} jobs from {self._path}")
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Failed to load cron store: {e}")
            self._loaded = True

    def save(self) -> None:
        """保存任务定义到文件（原子写入）"""
        data = {}
        for job_id, job in self._jobs.items():
            data[job_id] = {
                "id": job.id,
                "name": job.name,
                "schedule": job.schedule,
                "prompt": job.prompt,
                "agent_id": job.agent_id,
                "enabled": job.enabled,
                "last_run_at": job.last_run_at,
                "next_run_at": job.next_run_at,
                "run_count": job.run_count,
                "error_count": job.error_count,
                "created_at": job.created_at,
                "metadata": job.metadata,
            }

        # 原子写入：先写临时文件，再重命名
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            dir=str(self._path.parent),
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, str(self._path))
        except Exception:
            # 清理临时文件
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def add_job(self, job: CronJob) -> None:
        """添加任务"""
        self._jobs[job.id] = job

    def update_job(self, job_id: str, updates: dict) -> Optional[CronJob]:
        """更新任务字段"""
        job = self._jobs.get(job_id)
        if not job:
            return None
        for key, value in updates.items():
            if hasattr(job, key):
                setattr(job, key, value)
        return job

    def remove_job(self, job_id: str) -> bool:
        """移除任务"""
        if job_id in self._jobs:
            del self._jobs[job_id]
            return True
        return False

    def get_job(self, job_id: str) -> Optional[CronJob]:
        """获取指定任务"""
        return self._jobs.get(job_id)

    def list_jobs(self) -> list[CronJob]:
        """列出所有任务"""
        return list(self._jobs.values())
