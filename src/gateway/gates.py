import hmac
from typing import Optional

MAX_PAYLOAD_BYTES = 1024 * 1024  # 1MB，对应MAX_PAYLOAD_BYTES

def authenticate_handshake(
        token: Optional[str],
        auth: dict,
) -> dict:
    """连接总闸：对应 auth.ts 的 authorizeGatewayConnect

    校验 WebSocket 握手阶段的 token/password。
    使用 hmac.compare_digest 防止时序攻击。

    Args:
        token: 客户端提供的 token（来自 query 或 Authorization header）
        auth: 认证配置 dict，包含 mode/token/password

    Returns:
        {"ok": True, "role": "..."} 或 {"ok": False}
    """
    raise NotImplementedError("TODO: 后续章节实现")

def authorize_gateway_method(
        method: str,
        auth: dict,
        descriptor: dict,
) -> dict:
    """权限总闸：对应 server-methods.ts 的 authorizeGatewayMethod

    校验 role + scope 双重权限。
    先验 role，再验 scope 的 every() 语义。

    Args:
        method: 方法名，如 "agent.list"
        auth: 用户认证信息，包含 role 和 scope
        descriptor: 方法描述符，包含 requiredRole 和 requiredScopes

    Returns:
        {"allowed": True} 或 {"allowed": False, "reason": "..."}
    """
    raise NotImplementedError("TODO: 后续章节实现")

def validate_payload_size(
        data: str,
        max_bytes: int = MAX_PAYLOAD_BYTES,
) -> dict:
    """带宽总闸：对应 net.ts 的 validatePayloadSize

    检查消息字节数是否超过上限。

    Args:
        data: 消息文本
        max_bytes: 最大字节数，默认 1MB

    Returns:
        {"ok": True, "size": N} 或 {"ok": False, "size": N}
    """
    raise NotImplementedError("TODO: 后续章节实现")