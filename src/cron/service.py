"""
Cron Service — 定时任务服务

对应 OpenClaw 的 Cron 调度服务：
  - 管理定时任务的生命周期（启动、停止、状态查询）
  - 基于 cron 表达式调度 Agent 任务
  - 支持手动触发和队列执行
  - 注册 Gateway 方法：cron.list / cron.add / cron.update / cron.remove / cron.run

设计原则：
  1. 启动时加载存储，标记中断的任务
  2. 运行错过的任务（可选）
  3. 使用 asyncio 定时器调度
  4. 任务执行通过 Lane 队列异步化
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional

from loguru import logger

from .parse import calculate_next_run, parse_cron_expression
from .store import CronStore
from .types import CronEvent, CronEventType, CronJob, CronJobStatus, CronRunRecord


class CronService:
    """定时任务服务

    对应 OpenClaw 的 CronService，管理定时任务的调度和执行。
    """

    def __init__(self, store_path: str = "") -> None:
        self._store = CronStore(store_path) if store_path else CronStore("cron_jobs.json")
        self._timer: Optional[asyncio.Task] = None
        self._running_tasks: dict[str, asyncio.Task] = {}
        self._status: str = "stopped"
        self._run_history: list[CronRunRecord] = []

    # ── 生命周期 ──

    async def start(self) -> None:
        """启动 Cron 服务

        1. 加载存储
        2. 标记中断的运行
        3. 计算错过的任务
        4. 设置定时器
        """
        self._store.load()
        self._status = "running"

        # 标记中断的任务
        for job in self._store.list_jobs():
            if job.id in self._running_tasks:
                job.metadata["interrupted"] = True

        # 计算下次运行时间
        now = time.time()
        for job in self._store.list_jobs():
            if job.enabled:
                try:
                    next_time = calculate_next_run(job.schedule, datetime.fromtimestamp(now))
                    job.next_run_at = next_time.timestamp()
                except ValueError as e:
                    logger.error(f"Invalid cron expression for job {job.id}: {e}")
                    job.enabled = False
                    job.error_count += 1

        self._store.save()

        # 启动调度循环
        self._timer = asyncio.create_task(self._schedule_loop())
        logger.info("Cron service started")

    async def stop(self) -> None:
        """停止 Cron 服务"""
        self._status = "stopping"

        # 取消定时器
        if self._timer:
            self._timer.cancel()
            try:
                await self._timer
            except asyncio.CancelledError:
                pass
            self._timer = None

        # 等待运行中的任务完成
        if self._running_tasks:
            logger.info(f"Waiting for {len(self._running_tasks)} running cron tasks...")
            await asyncio.gather(*self._running_tasks.values(), return_exceptions=True)
            self._running_tasks.clear()

        self._store.save()
        self._status = "stopped"
        logger.info("Cron service stopped")

    def status(self) -> dict[str, Any]:
        """获取服务状态"""
        jobs = self._store.list_jobs()
        return {
            "status": self._status,
            "total_jobs": len(jobs),
            "enabled_jobs": sum(1 for j in jobs if j.enabled),
            "running_tasks": len(self._running_tasks),
        }

    # ── 任务管理 ──

    def list(self) -> list[dict[str, Any]]:
        """列出所有任务"""
        return [
            {
                "id": j.id,
                "name": j.name,
                "schedule": j.schedule,
                "prompt": j.prompt,
                "agent_id": j.agent_id,
                "enabled": j.enabled,
                "last_run_at": j.last_run_at,
                "next_run_at": j.next_run_at,
                "run_count": j.run_count,
                "error_count": j.error_count,
            }
            for j in self._store.list_jobs()
        ]

    def add(self, job_data: dict[str, Any]) -> dict[str, Any]:
        """添加新任务"""
        job_id = job_data.get("id") or str(uuid.uuid4())
        now = time.time()

        # 验证 cron 表达式
        schedule = job_data.get("schedule", "")
        try:
            parse_cron_expression(schedule)
        except ValueError as e:
            return {"ok": False, "error": f"Invalid cron expression: {e}"}

        # 计算下次运行时间
        try:
            next_dt = calculate_next_run(schedule, datetime.fromtimestamp(now))
            next_run_at = next_dt.timestamp()
        except ValueError as e:
            return {"ok": False, "error": f"Cannot calculate next run: {e}"}

        job = CronJob(
            id=job_id,
            name=job_data.get("name", job_id),
            schedule=schedule,
            prompt=job_data.get("prompt", ""),
            agent_id=job_data.get("agent_id", "agentic_loop"),
            enabled=job_data.get("enabled", True),
            next_run_at=next_run_at,
            created_at=now,
        )

        self._store.add_job(job)
        self._store.save()
        logger.info(f"Cron job added: {job_id} ({schedule})")
        return {"ok": True, "job_id": job_id}

    def update(self, job_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        """更新任务"""
        job = self._store.get_job(job_id)
        if not job:
            return {"ok": False, "error": "job not found"}

        # 如果更新了 schedule，重新验证和计算
        if "schedule" in updates:
            try:
                parse_cron_expression(updates["schedule"])
                next_dt = calculate_next_run(updates["schedule"])
                updates["next_run_at"] = next_dt.timestamp()
            except ValueError as e:
                return {"ok": False, "error": f"Invalid cron expression: {e}"}

        self._store.update_job(job_id, updates)
        self._store.save()
        logger.info(f"Cron job updated: {job_id}")
        return {"ok": True, "job_id": job_id}

    def remove(self, job_id: str) -> dict[str, Any]:
        """移除任务"""
        if self._store.remove_job(job_id):
            self._store.save()
            logger.info(f"Cron job removed: {job_id}")
            return {"ok": True, "job_id": job_id}
        return {"ok": False, "error": "job not found"}

    async def run(self, job_id: str) -> dict[str, Any]:
        """手动触发任务"""
        job = self._store.get_job(job_id)
        if not job:
            return {"ok": False, "error": "job not found"}

        if job_id in self._running_tasks:
            return {"ok": False, "error": "job already running"}

        await self._execute_job(job)
        return {"ok": True, "job_id": job_id}

    async def enqueue_run(self, job_id: str) -> dict[str, Any]:
        """通过队列异步执行任务"""
        job = self._store.get_job(job_id)
        if not job:
            return {"ok": False, "error": "job not found"}

        if job_id in self._running_tasks:
            return {"ok": False, "error": "job already running"}

        task = asyncio.create_task(self._execute_job(job))
        self._running_tasks[job_id] = task
        task.add_done_callback(lambda t: self._running_tasks.pop(job_id, None))
        return {"ok": True, "job_id": job_id, "queued": True}

    # ── 内部方法 ──

    async def _execute_job(self, job: CronJob) -> None:
        """执行一个定时任务"""
        now = time.time()
        record = CronRunRecord(job_id=job.id, started_at=now)
        logger.info(f"Cron job executing: {job.id} ({job.name})")

        try:
            # 调用 Agent 执行
            from gateway.agent_methods import handle_agent_run
            result = await handle_agent_run(
                {"message": job.prompt, "session_id": f"cron-{job.id}"},
                {"ok": True, "role": "system"},
            )
            record.completed_at = time.time()
            record.success = True
            record.result = result
            job.run_count += 1
            job.last_run_at = now
        except Exception as e:
            record.completed_at = time.time()
            record.success = False
            record.error = str(e)
            job.error_count += 1
            logger.error(f"Cron job failed: {job.id} - {e}")
        finally:
            # 计算下次运行时间
            try:
                next_dt = calculate_next_run(job.schedule)
                job.next_run_at = next_dt.timestamp()
            except ValueError:
                job.enabled = False

            self._store.save()
            self._run_history.append(record)
            # 保留最近 100 条记录
            if len(self._run_history) > 100:
                self._run_history = self._run_history[-100:]

    async def _schedule_loop(self) -> None:
        """调度循环：每 30 秒检查一次是否有需要执行的任务"""
        while self._status == "running":
            try:
                now = time.time()
                for job in self._store.list_jobs():
                    if not job.enabled:
                        continue
                    if job.next_run_at and job.next_run_at <= now:
                        if job.id not in self._running_tasks:
                            await self.enqueue_run(job.id)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Cron schedule loop error: {e}")

            await asyncio.sleep(30)


# ── Gateway 方法注册 ──

_cron_service: Optional[CronService] = None


def get_cron_service() -> CronService:
    """获取全局 CronService 实例"""
    global _cron_service
    if _cron_service is None:
        from config.settings import settings
        store_path = getattr(settings, "CRON_STORE_PATH", "cron_jobs.json")
        _cron_service = CronService(store_path=store_path)
    return _cron_service


async def handle_cron_list(params: dict, auth: dict) -> dict:
    """cron.list 方法处理器"""
    service = get_cron_service()
    return {"jobs": service.list(), **service.status()}


async def handle_cron_add(params: dict, auth: dict) -> dict:
    """cron.add 方法处理器"""
    service = get_cron_service()
    return service.add(params)


async def handle_cron_update(params: dict, auth: dict) -> dict:
    """cron.update 方法处理器"""
    service = get_cron_service()
    job_id = params.get("job_id", "")
    updates = params.get("updates", {})
    return service.update(job_id, updates)


async def handle_cron_remove(params: dict, auth: dict) -> dict:
    """cron.remove 方法处理器"""
    service = get_cron_service()
    job_id = params.get("job_id", "")
    return service.remove(job_id)


async def handle_cron_run(params: dict, auth: dict) -> dict:
    """cron.run 方法处理器"""
    service = get_cron_service()
    job_id = params.get("job_id", "")
    return await service.run(job_id)


def register_cron_methods() -> None:
    """注册 Cron 相关的 Gateway 方法"""
    from gateway.server_impl import register_method

    register_method("cron.list", handle_cron_list, required_role="user")
    register_method("cron.add", handle_cron_add, required_role="admin")
    register_method("cron.update", handle_cron_update, required_role="admin")
    register_method("cron.remove", handle_cron_remove, required_role="admin")
    register_method("cron.run", handle_cron_run, required_role="admin")

    logger.info("Cron methods registered: cron.list, cron.add, cron.update, cron.remove, cron.run")
