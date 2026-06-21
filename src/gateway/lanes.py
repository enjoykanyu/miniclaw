"""
Lane Queue — 会话级并发控制

对标 OpenClaw 的 CommandLane 机制：
  不同类型的命令（主循环、Cron、子 Agent 等）走不同的车道，
  每个车道按 session_key 隔离，同一会话内按并发度串行/并行执行。

车道类型：
  - MAIN:       主 Agent 推理（用户直接对话）
  - CRON:       定时任务
  - CRON_NESTED: 定时任务中嵌套的子调用
  - SUBAGENT:   子 Agent 调用
  - NESTED:     嵌套调用

默认并发度：
  Main=3, Subagent=2, Cron=1, CronNested=1, Nested=2
"""

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Coroutine, Dict, Optional

from loguru import logger


class CommandLane(str, Enum):
    """命令车道枚举"""
    MAIN = "main"
    CRON = "cron"
    CRON_NESTED = "cron-nested"
    SUBAGENT = "subagent"
    NESTED = "nested"


# 每条车道的默认并发度
DEFAULT_LANE_CONCURRENCY: Dict[CommandLane, int] = {
    CommandLane.MAIN: 3,
    CommandLane.SUBAGENT: 2,
    CommandLane.CRON: 1,
    CommandLane.CRON_NESTED: 1,
    CommandLane.NESTED: 2,
}


@dataclass
class _QueueEntry:
    """队列中的待执行条目"""
    coro: Coroutine
    lane: CommandLane
    session_key: str
    future: asyncio.Future = field(default_factory=lambda: asyncio.get_event_loop().create_future())


class LaneQueue:
    """
    单条车道的会话隔离队列

    每个 session_key 拥有独立的 FIFO 队列和信号量，
    互不影响，避免一个会话阻塞其他会话。
    """

    def __init__(self, lane: CommandLane, concurrency: int):
        self.lane = lane
        self.concurrency = concurrency
        # session_key → asyncio.Semaphore
        self._semaphores: Dict[str, asyncio.Semaphore] = {}
        # session_key → deque[_QueueEntry]
        self._queues: Dict[str, list[_QueueEntry]] = {}
        self._lock = asyncio.Lock()

    def _get_semaphore(self, session_key: str) -> asyncio.Semaphore:
        """获取或创建会话级信号量"""
        if session_key not in self._semaphores:
            self._semaphores[session_key] = asyncio.Semaphore(self.concurrency)
        return self._semaphores[session_key]

    def enqueue(self, entry: _QueueEntry) -> None:
        """将命令加入队列"""
        if entry.session_key not in self._queues:
            self._queues[entry.session_key] = []
        self._queues[entry.session_key].append(entry)

    def dequeue(self, session_key: str) -> Optional[_QueueEntry]:
        """从队列取出下一个命令"""
        queue = self._queues.get(session_key)
        if not queue:
            return None
        entry = queue.pop(0)
        if not queue:
            del self._queues[session_key]
        return entry

    def is_busy(self, session_key: str) -> bool:
        """检查该会话是否有正在运行的命令"""
        sem = self._semaphores.get(session_key)
        if sem is None:
            return False
        return sem._value < self.concurrency

    @property
    def pending_count(self) -> int:
        """当前队列中等待的命令数"""
        return sum(len(q) for q in self._queues.values())


class LaneManager:
    """
    车道管理器 — 管理多条车道的并发执行

    对标 OpenClaw 的 LaneManager：
    - 按车道类型和会话键隔离并发
    - 命令入队后自动在有槽位时执行
    - 支持动态调整并发度
    """

    def __init__(
        self,
        concurrency_overrides: Optional[Dict[CommandLane, int]] = None,
    ):
        overrides = concurrency_overrides or {}
        self._lanes: Dict[CommandLane, LaneQueue] = {}
        for lane in CommandLane:
            concurrency = overrides.get(lane, DEFAULT_LANE_CONCURRENCY[lane])
            self._lanes[lane] = LaneQueue(lane, concurrency)

    async def enqueue_command_in_lane(
        self,
        lane: CommandLane,
        session_key: str,
        coro: Coroutine,
    ) -> Any:
        """
        将协程加入指定车道执行

        当该会话的车道有可用槽位时立即执行，
        否则排队等待。返回协程的执行结果。
        """
        queue = self._lanes[lane]
        entry = _QueueEntry(coro=coro, lane=lane, session_key=session_key)

        semaphore = queue._get_semaphore(session_key)

        # 尝试立即获取槽位
        acquired = semaphore.locked() is False and semaphore._value > 0
        if not acquired:
            # 没有空闲槽位，入队等待
            queue.enqueue(entry)
            logger.debug(
                f"Lane[{lane.value}] session={session_key} queued, "
                f"pending={queue.pending_count}"
            )
            # 等待轮到自己
            await semaphore.acquire()
            # 从队列中取出（可能是自己）
            next_entry = queue.dequeue(session_key)
            if next_entry is None:
                # 队列已空，直接执行当前
                next_entry = entry
        else:
            await semaphore.acquire()
            next_entry = entry

        try:
            result = await next_entry.coro
            if not next_entry.future.done():
                next_entry.future.set_result(result)
            return result
        except Exception as e:
            if not next_entry.future.done():
                next_entry.future.set_exception(e)
            raise
        finally:
            semaphore.release()
            # 释放后检查是否有排队的命令可以执行
            self._try_drain_queue(queue, session_key)

    def _try_drain_queue(self, queue: LaneQueue, session_key: str) -> None:
        """尝试排空队列中的等待命令（通过创建后台任务）"""
        while True:
            entry = queue.dequeue(session_key)
            if entry is None:
                break
            asyncio.create_task(self._execute_queued_entry(queue, entry))

    async def _execute_queued_entry(self, queue: LaneQueue, entry: _QueueEntry) -> None:
        """执行队列中的条目"""
        semaphore = queue._get_semaphore(entry.session_key)
        await semaphore.acquire()
        try:
            result = await entry.coro
            if not entry.future.done():
                entry.future.set_result(result)
        except Exception as e:
            if not entry.future.done():
                entry.future.set_exception(e)
        finally:
            semaphore.release()
            self._try_drain_queue(queue, entry.session_key)

    def is_busy(self, lane: CommandLane, session_key: str) -> bool:
        """检查指定车道和会话是否有正在运行的命令"""
        return self._lanes[lane].is_busy(session_key)

    def get_queue_depth(self, lane: CommandLane, session_key: str) -> int:
        """获取指定车道和会话的排队深度"""
        queue = self._lanes[lane]
        q = queue._queues.get(session_key, [])
        return len(q)

    def update_concurrency(self, lane: CommandLane, concurrency: int) -> None:
        """动态更新车道并发度（仅影响新创建的会话信号量）"""
        self._lanes[lane].concurrency = concurrency
        logger.info(f"Lane[{lane.value}] concurrency updated to {concurrency}")


# ── 全局单例 ──

_lane_manager: Optional[LaneManager] = None


def get_lane_manager() -> LaneManager:
    """获取全局 LaneManager 单例"""
    global _lane_manager
    if _lane_manager is None:
        from config.settings import settings
        overrides: Dict[CommandLane, int] = {}
        if hasattr(settings, "GATEWAY_AGENT_MAX_CONCURRENT"):
            overrides[CommandLane.MAIN] = settings.GATEWAY_AGENT_MAX_CONCURRENT
        if hasattr(settings, "GATEWAY_SUBAGENT_MAX_CONCURRENT"):
            overrides[CommandLane.SUBAGENT] = settings.GATEWAY_SUBAGENT_MAX_CONCURRENT
        _lane_manager = LaneManager(concurrency_overrides=overrides)
    return _lane_manager
