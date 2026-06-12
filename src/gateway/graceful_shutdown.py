"""
Graceful Shutdown — 多阶段有序关闭

对标 OpenClaw 的 GracefulShutdownManager：
  收到 SIGTERM/SIGINT 后，按优先级分阶段执行关闭流程，
  确保在途请求被排空、WebSocket 连接优雅断开、资源正确释放。

关闭阶段（按优先级从低到高执行）：
  1. 触发 gateway:shutdown hook
  2. 排空在途请求（等待 GRACEFUL_SHUTDOWN_TIMEOUT_MS）
  3. 停止接受新请求
  4. 关闭 Channel
  5. 停止健康监控
  6. 停止配置热重载
  7. 关闭 WebSocket 连接（给 WEBSOCKET_CLOSE_GRACE_MS 宽限期）
  8. 关闭 HTTP 服务器
"""

import asyncio
import signal
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional, Set

from loguru import logger


# ── 常量 ──
GATEWAY_SHUTDOWN_HOOK_TIMEOUT_MS = 5000
WEBSOCKET_CLOSE_GRACE_MS = 1000
GRACEFUL_SHUTDOWN_TIMEOUT_MS = 30000


@dataclass
class _ShutdownHandler:
    """关闭处理器条目"""
    name: str
    handler: Callable[[], Awaitable[None]]
    priority: int  # 数字越小越先执行


class GracefulShutdownManager:
    """
    优雅关闭管理器

    对标 OpenClaw 的 GracefulShutdownManager：
    - 注册关闭处理器，按优先级执行
    - 跟踪在途请求
    - 多阶段有序关闭
    - 支持3次 Ctrl+C 强制退出
    """

    def __init__(self):
        self._handlers: List[_ShutdownHandler] = []
        self._in_flight_requests: Set[str] = set()
        self._in_flight_lock = asyncio.Lock()
        self._shutting_down = False
        self._shutdown_reason: Optional[str] = None
        self._shutdown_event = asyncio.Event()
        self._websockets: Set[Any] = set()
        self._signal_count = 0  # 信号计数器，用于强制退出

    @property
    def is_shutting_down(self) -> bool:
        """是否正在关闭"""
        return self._shutting_down

    def register_handler(
        self,
        name: str,
        handler: Callable[[], Awaitable[None]],
        priority: int,
    ) -> None:
        """
        注册关闭处理器

        Args:
            name: 处理器名称（用于日志）
            handler: 异步关闭函数
            priority: 优先级，数字越小越先执行
        """
        self._handlers.append(_ShutdownHandler(name=name, handler=handler, priority=priority))
        self._handlers.sort(key=lambda h: h.priority)
        logger.debug(f"Shutdown handler registered: {name} (priority={priority})")

    async def add_in_flight_request(self, request_id: str) -> None:
        """添加在途请求"""
        async with self._in_flight_lock:
            self._in_flight_requests.add(request_id)

    async def remove_in_flight_request(self, request_id: str) -> None:
        """移除在途请求"""
        async with self._in_flight_lock:
            self._in_flight_requests.discard(request_id)

    @property
    def in_flight_count(self) -> int:
        """当前在途请求数"""
        return len(self._in_flight_requests)

    def register_websocket(self, ws: Any) -> None:
        """注册活跃 WebSocket 连接"""
        self._websockets.add(ws)

    def unregister_websocket(self, ws: Any) -> None:
        """注销 WebSocket 连接"""
        self._websockets.discard(ws)

    async def shutdown(self, reason: str = "shutdown") -> None:
        """
        执行多阶段优雅关闭

        对标 OpenClaw 的 gracefulShutdown：
        1. 触发 gateway:shutdown hook
        2. 排空在途请求
        3. 停止接受新请求
        4-8. 按优先级执行注册的关闭处理器

        强制退出：3次信号后 os._exit(1) 强制终止进程
        """
        self._signal_count += 1

        if self._signal_count >= 3:
            logger.warning(f"Force exit after {self._signal_count} signals")
            import os
            os._exit(1)

        if self._shutting_down:
            logger.warning(
                f"Shutdown already in progress (signal {self._signal_count}/3), "
                f"press Ctrl+C 3 times to force exit"
            )
            return

        self._shutting_down = True
        self._shutdown_reason = reason
        logger.info(f"Graceful shutdown initiated: {reason}")

        # ── 阶段 1: 触发 gateway:shutdown hook ──
        try:
            from gateway.hooks import hook_runner
            await asyncio.wait_for(
                hook_runner.run_void_hook(
                    "gateway:shutdown",
                    {"reason": reason},
                ),
                timeout=GATEWAY_SHUTDOWN_HOOK_TIMEOUT_MS / 1000,
            )
        except asyncio.TimeoutError:
            logger.warning("Shutdown hook timed out, continuing")
        except Exception as e:
            logger.error(f"Shutdown hook failed: {e}")

        # ── 阶段 2: 排空在途请求 ──
        logger.info(f"Draining in-flight requests: {self.in_flight_count} pending")
        drain_start = time.monotonic()
        drain_timeout = GRACEFUL_SHUTDOWN_TIMEOUT_MS / 1000

        while self.in_flight_count > 0:
            elapsed = time.monotonic() - drain_start
            if elapsed >= drain_timeout:
                logger.warning(
                    f"Drain timeout ({drain_timeout}s), "
                    f"{self.in_flight_count} requests still in flight"
                )
                break
            await asyncio.sleep(0.1)

        # ── 阶段 3: 停止接受新请求（标记已设置）──
        logger.info("Stopped accepting new requests")

        # ── 阶段 4-8: 执行注册的关闭处理器 ──
        for handler_entry in self._handlers:
            try:
                logger.info(f"Shutdown step: {handler_entry.name}")
                await asyncio.wait_for(
                    handler_entry.handler(),
                    timeout=10.0,
                )
            except asyncio.TimeoutError:
                logger.warning(f"Shutdown handler '{handler_entry.name}' timed out")
            except Exception as e:
                logger.error(f"Shutdown handler '{handler_entry.name}' failed: {e}")

        # ── 关闭 WebSocket 连接 ──
        await self._close_websockets()

        self._shutdown_event.set()
        logger.info("Graceful shutdown complete")

    async def _close_websockets(self) -> None:
        """关闭所有 WebSocket 连接"""
        if not self._websockets:
            return

        logger.info(f"Closing {len(self._websockets)} WebSocket connections")

        close_tasks = []
        for ws in list(self._websockets):
            try:
                close_tasks.append(ws.close(code=1001, reason="server shutdown"))
            except Exception:
                pass

        if close_tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*close_tasks, return_exceptions=True),
                    timeout=WEBSOCKET_CLOSE_GRACE_MS / 1000,
                )
            except asyncio.TimeoutError:
                logger.warning("WebSocket close grace period exceeded")

        self._websockets.clear()

    def setup_signal_handlers(self, loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
        """
        注册信号处理器（SIGTERM, SIGINT）

        收到信号后触发优雅关闭流程。
        """
        if loop is None:
            loop = asyncio.get_event_loop()

        async def _signal_handler() -> None:
            logger.info("Received shutdown signal")
            await self.shutdown("signal")

        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(
                    sig,
                    lambda: asyncio.create_task(_signal_handler()),
                )
            except NotImplementedError:
                # Windows 不支持 add_signal_handler
                pass

    async def wait_shutdown(self) -> None:
        """等待关闭完成"""
        await self._shutdown_event.wait()


# ── 全局单例 ──

_shutdown_manager: Optional[GracefulShutdownManager] = None


def get_shutdown_manager() -> GracefulShutdownManager:
    """获取全局 GracefulShutdownManager 单例"""
    global _shutdown_manager
    if _shutdown_manager is None:
        _shutdown_manager = GracefulShutdownManager()
    return _shutdown_manager
