"""
ACP (Agent Client Protocol) 协议类型定义

对应 OpenClaw 的 ACP 类型系统：
  - AcpRequest / AcpResponse: 请求-响应帧
  - AcpEvent: 事件推送帧
  - Session 管理类型
  - 速率限制配置

ACP 是 IDE 与 Agent 之间的标准通信协议，
使用 ndJson 流格式传输。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


# ── ACP 帧类型 ──

class AcpFrameType(str, Enum):
    """ACP 帧类型"""
    REQUEST = "request"
    RESPONSE = "response"
    EVENT = "event"


class AcpCommand(str, Enum):
    """ACP 命令"""
    PROMPT = "prompt"
    CREATE_SESSION = "createSession"
    LIST_SESSIONS = "listSessions"
    CLOSE_SESSION = "closeSession"


class AcpEventType(str, Enum):
    """ACP 事件类型"""
    CHAT_DELTA = "chat_delta"
    CHAT_FINAL = "chat_final"
    CHAT_ABORTED = "chat_aborted"
    CHAT_ERROR = "chat_error"
    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_UPDATE = "tool_call_update"
    TOOL_CALL_RESULT = "tool_call_result"
    SESSION_CREATED = "session_created"
    SESSION_CLOSED = "session_closed"


# ── 请求 / 响应 ──

@dataclass
class AcpRequest:
    """ACP 请求帧"""
    id: str
    command: AcpCommand
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class AcpResponse:
    """ACP 响应帧"""
    id: str
    ok: bool
    payload: Optional[Any] = None
    error: Optional[str] = None


@dataclass
class AcpEvent:
    """ACP 事件帧"""
    event: AcpEventType
    payload: dict[str, Any] = field(default_factory=dict)
    session_id: Optional[str] = None


# ── Session 管理 ──

@dataclass
class AcpSession:
    """ACP 会话"""
    id: str
    created_at: float
    agent_id: str = "agentic_loop"
    status: str = "active"  # active / closed
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AcpSessionInfo:
    """ACP 会话摘要信息"""
    id: str
    agent_id: str
    status: str
    created_at: float


# ── 速率限制 ──

@dataclass
class AcpRateLimitConfig:
    """ACP 速率限制配置"""
    max_requests: int = 120
    window_seconds: float = 10.0


@dataclass
class AcpRateLimitEntry:
    """速率限制追踪条目"""
    timestamps: list[float] = field(default_factory=list)

    def check(self, now: float, config: AcpRateLimitConfig) -> bool:
        """检查是否超过速率限制，返回 True 表示允许"""
        cutoff = now - config.window_seconds
        self.timestamps = [t for t in self.timestamps if t > cutoff]
        if len(self.timestamps) >= config.max_requests:
            return False
        self.timestamps.append(now)
        return True
