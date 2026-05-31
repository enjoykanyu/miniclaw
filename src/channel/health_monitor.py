from __future__ import annotations
import asyncio
import time
from dataclasses import dataclass
from enum import Enum
from .runtime_store import (
    ChannelRuntimeStore, ChannelAccountSnapshot,
)

class HealthReason(str, Enum):
    HEALTHY = "healthy"
    UNMANAGED = "unmanaged"
    BUSY = "busy"
    STARTUP_GRACE = "startup-connect-grace"
    NOT_RUNNING = "not-running"
    DISCONNECTED = "disconnected"
    STALE_SOCKET = "stale-socket"
    STUCK = "stuck"

@dataclass
class HealthEvaluation:
    healthy: bool
    reason: HealthReason

@dataclass
class HealthPolicy:
    channel_connect_grace_ms: int = 120_000
    stale_event_threshold_ms: int = 1_800_000
    busy_threshold_ms: int = 1_500_000
    stuck_threshold_ms: int = 1_500_000

def evaluate_channel_health(
        snapshot: ChannelAccountSnapshot,
        policy: HealthPolicy,
        now: float | None = None,
) -> HealthEvaluation:
    """对应 evaluateChannelHealth: 6级评估"""
    now = now or time.monotonic()
    up_duration = (now - snapshot.started_at) * 1000
    event_age = (now - snapshot.last_event_at) * 1000

    if not snapshot.running:
        return HealthEvaluation(
            False, HealthReason.NOT_RUNNING)
    if up_duration < policy.channel_connect_grace_ms:
        return HealthEvaluation(
            True, HealthReason.STARTUP_GRACE)
    if not snapshot.connected:
        return HealthEvaluation(
            False, HealthReason.DISCONNECTED)
    if event_age > policy.stale_event_threshold_ms:
        return HealthEvaluation(
            False, HealthReason.STALE_SOCKET)
    return HealthEvaluation(
        True, HealthReason.HEALTHY)

class ChannelHealthMonitor:
    """对应 startChannelHealthMonitor"""

    def __init__(
            self,
            store: ChannelRuntimeStore,
            policy: HealthPolicy | None = None,
            *,
            check_interval_s: float = 300.0,
            cooldown_cycles: int = 2,
            max_restarts_per_hour: int = 10,
    ) -> None:
        self._store = store
        self._policy = policy or HealthPolicy()
        self._check_interval = check_interval_s
        self._cooldown_s = cooldown_cycles * check_interval_s
        self._max_restarts = max_restarts_per_hour
        self._restart_log: dict[str, list[float]] = {}
        self._task: asyncio.Task | None = None

    def _prune_old(self, key: str, now: float) -> None:
        cutoff = now - 3600.0
        self._restart_log[key] = [
            t for t in self._restart_log.get(key, [])
            if t > cutoff]

    async def _run_check(self) -> None:
        now = time.monotonic()
        for key, snap in self._store._snapshots.items():
            health = evaluate_channel_health(
                snap, self._policy, now)
            if health.healthy:
                continue
            self._prune_old(key, now)
            restarts = self._restart_log.get(key, [])
            if restarts:
                last = max(restarts)
                if now - last < self._cooldown_s:
                    continue
            if len(restarts) >= self._max_restarts:
                continue
            self._restart_log.setdefault(
                key, []).append(now)
            ch_id, acc_id = key.split(":", 1)
            self._store.cancel(ch_id, acc_id)
            self._store.reset_restart_attempts(ch_id, acc_id)

    async def _loop(self) -> None:
        while True:
            await asyncio.sleep(self._check_interval)
            await self._run_check()

    def start(self) -> None:
        self._task = asyncio.ensure_future(
            self._loop())

    def stop(self) -> None:
        if self._task:
            self._task.cancel()
            self._task = None