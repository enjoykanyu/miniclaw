from __future__ import annotations
import asyncio
import random
from dataclasses import dataclass, field
from typing import Any
import time

@dataclass
class BackoffPolicy:
    """对应 CHANNEL_RESTART_POLICY"""
    initial_ms: int = 5_000
    max_ms: int = 300_000
    factor: float = 2.0
    jitter: float = 0.1

    def delay_for_attempt(self, attempt: int) -> float:
        """计算第 N 次重试的等待秒数（含抖动）"""
        base = self.initial_ms * (self.factor ** attempt)
        capped = min(base, self.max_ms)
        jitter_range = capped * self.jitter
        return (capped + random.uniform(
            -jitter_range, jitter_range)) / 1000.0

@dataclass
class ChannelAccountSnapshot:
    """对应 ChannelAccountSnapshot"""
    running: bool = False
    connected: bool = False
    last_event_at: float = 0.0
    started_at: float = 0.0
    restart_attempts: int = 0

class ChannelRuntimeStore:
    """对应 server-channels.ts ChannelRuntimeStore

    键格式: channelId:accountId
    每个账号维度独立管理。
    """

    MAX_RESTART_ATTEMPTS = 10
    STARTUP_CONCURRENCY = 4

    def __init__(self) -> None:
        self._aborts: dict[str, asyncio.Event] = {}
        self._starting: dict[str, asyncio.Task] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._snapshots: dict[str, ChannelAccountSnapshot] = {}
        self._restart_policy = BackoffPolicy()

    def _key(self, channel_id: str,
             account_id: str) -> str:
        return f"{channel_id}:{account_id}"

    def get_snapshot(self, channel_id: str,
                     account_id: str) -> ChannelAccountSnapshot:
        key = self._key(channel_id, account_id)
        if key not in self._snapshots:
            self._snapshots[key] = ChannelAccountSnapshot()
        return self._snapshots[key]

    def set_starting(self, channel_id: str,
                     account_id: str,
                     task: asyncio.Task) -> None:
        self._starting[self._key(channel_id, account_id)] = task

    def cancel(self, channel_id: str,
               account_id: str) -> None:
        key = self._key(channel_id, account_id)
        if key in self._aborts:
            self._aborts[key].set()
        if key in self._tasks:
            self._tasks[key].cancel()

    def reset_restart_attempts(self, channel_id: str,
                               account_id: str) -> None:
        snap = self.get_snapshot(channel_id, account_id)
        snap.restart_attempts = 0

    def record_restart(self, channel_id: str,
                       account_id: str) -> float:
        snap = self.get_snapshot(channel_id, account_id)
        delay = self._restart_policy.delay_for_attempt(
            snap.restart_attempts)
        snap.restart_attempts += 1
        return delay