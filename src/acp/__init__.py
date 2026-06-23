"""
MiniClaw ACP (Agent Client Protocol) — IDE 集成

对应 OpenClaw 的 ACP 协议支持，提供：
  - AcpGatewayAgent: 桥接 ACP 客户端到 Gateway
  - serve_acp_gateway(): ACP 服务器入口点
  - ACP 协议类型定义
"""

from .types import (
    AcpCommand,
    AcpEvent,
    AcpEventType,
    AcpFrameType,
    AcpRateLimitConfig,
    AcpRateLimitEntry,
    AcpRequest,
    AcpResponse,
    AcpSession,
    AcpSessionInfo,
)
from .server import AcpGatewayAgent, serve_acp_gateway

__all__ = [
    "AcpCommand",
    "AcpEvent",
    "AcpEventType",
    "AcpFrameType",
    "AcpGatewayAgent",
    "AcpRateLimitConfig",
    "AcpRateLimitEntry",
    "AcpRequest",
    "AcpResponse",
    "AcpSession",
    "AcpSessionInfo",
    "serve_acp_gateway",
]
