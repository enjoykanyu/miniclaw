"""
Gateway Broadcaster — 事件广播与慢消费者保护

对标 OpenClaw 的 Gateway Broadcaster：
  - 维护已连接的 WebSocket 客户端列表及其认证 scope
  - 事件 scope 守卫：将事件名映射到所需 scope（read/write/admin）
  - 慢消费者检测：当客户端缓冲字节数超过阈值时，丢弃事件或关闭连接
  - 每客户端序列号：保证有序投递
  - 帧格式: {"type": "event", "event": "...", "payload": {...}, "seq": N, "stateVersion": V}

映射关系：
  OpenClaw GatewayBroadcaster  → GatewayBroadcaster
  OpenClaw broadcast()         → broadcast()
  OpenClaw broadcastToConnIds → broadcast_to_conn_ids()
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Optional, Callable, Awaitable, Any

from loguru import logger


# ──────────────────────────────────────────────────────────
# 事件 scope 映射：事件名前缀 → 所需 scope
# ──────────────────────────────────────────────────────────

_EVENT_SCOPE_MAP: dict[str, str] = {
    "agent.": "read",
    "chat.": "read",
    "session.": "read",
    "config.": "admin",
    "system.": "read",
    "tool.": "write",
}

_DEFAULT_EVENT_SCOPE = "read"


def _resolve_event_scope(event_name: str) -> str:
    """根据事件名前缀解析所需 scope"""
    for prefix, scope in _EVENT_SCOPE_MAP.items():
        if event_name.startswith(prefix):
            return scope
    return _DEFAULT_EVENT_SCOPE


# ──────────────────────────────────────────────────────────
# 客户端连接信息
# ──────────────────────────────────────────────────────────

@dataclass
class ClientConnection:
    """已连接的 WebSocket 客户端"""
    conn_id: str
    ws: Any  # FastAPI WebSocket 对象
    auth_scopes: list[str] = field(default_factory=list)
    auth_role: str = "user"
    seq: int = 0
    buffered_bytes: int = 0
    connected_at: float = field(default_factory=time.time)
    last_active_at: float = field(default_factory=time.time)


# ──────────────────────────────────────────────────────────
# GatewayBroadcaster
# ──────────────────────────────────────────────────────────

class GatewayBroadcaster:
    """
    事件广播器 — 对标 OpenClaw GatewayBroadcaster

    职责：
    1. 维护已连接客户端列表
    2. 广播事件到所有符合条件的客户端
    3. 慢消费者检测与保护
    4. 每客户端序列号保证有序投递
    """

    def __init__(
        self,
        max_buffered_bytes: int = 1024 * 1024,  # 1MB
        slow_consumer_action: str = "drop",  # "drop" 或 "close"
        state_version: int = 0,
    ):
        self._clients: dict[str, ClientConnection] = {}
        self._max_buffered_bytes = max_buffered_bytes
        self._slow_consumer_action = slow_consumer_action
        self._state_version = state_version
        self._lock = asyncio.Lock()

    @property
    def client_count(self) -> int:
        return len(self._clients)

    @property
    def state_version(self) -> int:
        return self._state_version

    def increment_state_version(self) -> int:
        """递增状态版本号，用于帧的 stateVersion 字段"""
        self._state_version += 1
        return self._state_version

    async def add_client(self, conn_id: str, ws, auth: dict) -> None:
        """
        注册新的 WebSocket 客户端

        Args:
            conn_id: 连接唯一标识
            ws: FastAPI WebSocket 对象
            auth: 认证结果 dict，包含 role 和 scopes
        """
        async with self._lock:
            self._clients[conn_id] = ClientConnection(
                conn_id=conn_id,
                ws=ws,
                auth_scopes=auth.get("scopes", []),
                auth_role=auth.get("role", "user"),
            )
            logger.info(f"Broadcaster: client connected conn_id={conn_id}, total={len(self._clients)}")

    async def remove_client(self, conn_id: str) -> None:
        """移除 WebSocket 客户端"""
        async with self._lock:
            removed = self._clients.pop(conn_id, None)
            if removed:
                logger.info(f"Broadcaster: client disconnected conn_id={conn_id}, total={len(self._clients)}")

    async def broadcast(self, event: str, payload: dict) -> int:
        """
        广播事件到所有符合条件的客户端

        Args:
            event: 事件名（如 "agent.run.completed"）
            payload: 事件载荷

        Returns:
            成功投递的客户端数量
        """
        required_scope = _resolve_event_scope(event)
        delivered = 0

        async with self._lock:
            clients_to_notify = list(self._clients.values())

        for client in clients_to_notify:
            # scope 守卫：检查客户端是否有权限接收此事件
            if not self._check_scope(client, required_scope):
                continue

            # 构建帧
            client.seq += 1
            frame = {
                "type": "event",
                "event": event,
                "payload": payload,
                "seq": client.seq,
                "stateVersion": self._state_version,
            }

            frame_str = json.dumps(frame, ensure_ascii=False)
            frame_bytes = len(frame_str.encode("utf-8"))

            # 慢消费者检测
            if client.buffered_bytes + frame_bytes > self._max_buffered_bytes:
                if self._slow_consumer_action == "close":
                    logger.warning(
                        f"Broadcaster: slow consumer detected conn_id={client.conn_id}, "
                        f"buffered={client.buffered_bytes}, closing connection"
                    )
                    try:
                        await client.ws.close(code=4002, reason="Slow consumer: buffer overflow")
                    except Exception:
                        pass
                    await self.remove_client(client.conn_id)
                else:
                    logger.debug(
                        f"Broadcaster: dropping event for slow consumer conn_id={client.conn_id}, "
                        f"buffered={client.buffered_bytes}"
                    )
                continue

            # 投递
            try:
                await client.ws.send_json(frame)
                client.last_active_at = time.time()
                delivered += 1
            except Exception as e:
                logger.warning(f"Broadcaster: failed to send to conn_id={client.conn_id}: {e}")
                await self.remove_client(client.conn_id)

        return delivered

    async def broadcast_to_conn_ids(
        self,
        conn_ids: list[str],
        event: str,
        payload: dict,
    ) -> int:
        """
        向指定连接 ID 列表广播事件

        Args:
            conn_ids: 目标连接 ID 列表
            event: 事件名
            payload: 事件载荷

        Returns:
            成功投递的客户端数量
        """
        required_scope = _resolve_event_scope(event)
        delivered = 0

        for conn_id in conn_ids:
            async with self._lock:
                client = self._clients.get(conn_id)
            if client is None:
                continue

            # scope 守卫
            if not self._check_scope(client, required_scope):
                continue

            # 构建帧
            client.seq += 1
            frame = {
                "type": "event",
                "event": event,
                "payload": payload,
                "seq": client.seq,
                "stateVersion": self._state_version,
            }

            # 慢消费者检测
            frame_str = json.dumps(frame, ensure_ascii=False)
            frame_bytes = len(frame_str.encode("utf-8"))
            if client.buffered_bytes + frame_bytes > self._max_buffered_bytes:
                if self._slow_consumer_action == "close":
                    try:
                        await client.ws.close(code=4002, reason="Slow consumer: buffer overflow")
                    except Exception:
                        pass
                    await self.remove_client(client.conn_id)
                continue

            try:
                await client.ws.send_json(frame)
                client.last_active_at = time.time()
                delivered += 1
            except Exception as e:
                logger.warning(f"Broadcaster: failed to send to conn_id={conn_id}: {e}")
                await self.remove_client(conn_id)

        return delivered

    def _check_scope(self, client: ClientConnection, required_scope: str) -> bool:
        """
        检查客户端是否有指定 scope

        scope 层级: admin > write > read
        """
        scope_hierarchy = {"read": 0, "write": 1, "admin": 2}
        client_level = 0
        for scope in client.auth_scopes:
            client_level = max(client_level, scope_hierarchy.get(scope, 0))
        required_level = scope_hierarchy.get(required_scope, 0)
        return client_level >= required_level

    def get_client_info(self) -> list[dict]:
        """获取所有客户端信息（用于调试/监控）"""
        return [
            {
                "conn_id": c.conn_id,
                "auth_role": c.auth_role,
                "auth_scopes": c.auth_scopes,
                "seq": c.seq,
                "buffered_bytes": c.buffered_bytes,
                "connected_at": c.connected_at,
                "last_active_at": c.last_active_at,
            }
            for c in self._clients.values()
        ]
