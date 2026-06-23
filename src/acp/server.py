"""
ACP Gateway Server — IDE 集成协议

对应 OpenClaw 的 ACP (Agent Client Protocol) 网关：
  - 桥接 ACP 客户端（IDE）到 Gateway
  - 使用 ndJson 流格式通信
  - 翻译 ACP 请求为 Gateway RPC 调用
  - 翻译 Gateway 事件回 ACP 格式
  - 会话管理和速率限制

ACP 协议让 IDE（如 VS Code、JetBrains）能够
直接与 Agent 交互，实现代码补全、重构建议等能力。
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Any, Callable, Optional

from loguru import logger

from .types import (
    AcpCommand,
    AcpEvent,
    AcpEventType,
    AcpRateLimitConfig,
    AcpRateLimitEntry,
    AcpRequest,
    AcpResponse,
    AcpSession,
    AcpSessionInfo,
)


class AcpGatewayAgent:
    """ACP 网关代理

    桥接 ACP 客户端到 Gateway：
    1. 接收 ACP 请求（ndJson 流）
    2. 翻译为 Gateway RPC 调用
    3. 将 Gateway 事件翻译回 ACP 格式
    4. 推送 ACP 事件到客户端
    """

    def __init__(self, gateway_url: str = "ws://127.0.0.1:18789/ws") -> None:
        self._gateway_url = gateway_url
        self._sessions: dict[str, AcpSession] = {}
        self._rate_limiter = AcpRateLimitEntry()
        self._rate_limit_config = AcpRateLimitConfig()
        self._event_handlers: dict[str, Callable] = {}
        self._ws: Optional[Any] = None

    async def connect_to_gateway(self) -> None:
        """建立到 Gateway 的 WebSocket 连接"""
        try:
            import aiohttp
            self._ws_session = aiohttp.ClientSession()
            self._ws = await self._ws_session.ws_connect(self._gateway_url)
            logger.info(f"ACP connected to Gateway: {self._gateway_url}")
        except ImportError:
            logger.warning("aiohttp not installed, Gateway WebSocket connection skipped")
        except Exception as e:
            logger.error(f"ACP Gateway connection failed: {e}")

    async def disconnect_from_gateway(self) -> None:
        """断开 Gateway 连接"""
        if self._ws:
            await self._ws.close()
            self._ws = None
        if hasattr(self, "_ws_session") and self._ws_session:
            await self._ws_session.close()
        logger.info("ACP disconnected from Gateway")

    async def call_gateway(self, method: str, params: dict) -> dict:
        """调用 Gateway RPC 方法"""
        if not self._ws:
            # 回退到直接调用
            return await self._call_gateway_direct(method, params)

        frame_id = str(uuid.uuid4())
        frame = {
            "type": "req",
            "method": method,
            "id": frame_id,
            "params": params,
        }
        await self._ws.send_json(frame)

        # 等待响应
        async for msg in self._ws:
            if msg.type == 1:  # TEXT
                data = json.loads(msg.data)
                if data.get("id") == frame_id:
                    return data
        return {"ok": False, "error": "Connection closed"}

    async def _call_gateway_direct(self, method: str, params: dict) -> dict:
        """直接调用 Gateway 方法（不通过 WebSocket）"""
        try:
            if method == "agent.run":
                from gateway.agent_methods import handle_agent_run
                result = await handle_agent_run(params, {"ok": True, "role": "user"})
                return {"ok": True, "payload": result}
            elif method == "agent.list":
                from gateway.agent_methods import handle_agent_list
                result = await handle_agent_list(params, {"ok": True, "role": "user"})
                return {"ok": True, "payload": result}
            elif method == "agent.status":
                from gateway.agent_methods import handle_agent_status
                result = await handle_agent_status(params, {"ok": True, "role": "user"})
                return {"ok": True, "payload": result}
        except Exception as e:
            return {"ok": False, "error": str(e)}
        return {"ok": False, "error": f"unknown method: {method}"}

    # ── ACP 命令处理 ──

    async def handle_prompt(self, params: dict) -> AcpResponse:
        """处理 prompt 命令：发送消息到 Agent"""
        session_id = params.get("session_id", "default")
        message = params.get("message", "")

        if not message:
            return AcpResponse(id="", ok=False, error="message is required")

        # 调用 Gateway agent.run
        result = await self.call_gateway("agent.run", {
            "message": message,
            "session_id": session_id,
        })

        if result.get("ok"):
            payload = result.get("payload", {})
            return AcpResponse(id="", ok=True, payload=payload)
        else:
            return AcpResponse(id="", ok=False, error=result.get("error", "unknown error"))

    async def handle_create_session(self, params: dict) -> AcpResponse:
        """处理 createSession 命令"""
        now = time.time()

        # 速率限制检查
        if not self._rate_limiter.check(now, self._rate_limit_config):
            return AcpResponse(id="", ok=False, error="rate limit exceeded")

        session_id = params.get("session_id") or str(uuid.uuid4())
        session = AcpSession(
            id=session_id,
            created_at=now,
            agent_id=params.get("agent_id", "agentic_loop"),
            metadata=params.get("metadata", {}),
        )
        self._sessions[session_id] = session
        logger.info(f"ACP session created: {session_id}")
        return AcpResponse(id="", ok=True, payload={"session_id": session_id})

    async def handle_list_sessions(self, params: dict) -> AcpResponse:
        """处理 listSessions 命令"""
        sessions = [
            AcpSessionInfo(
                id=s.id,
                agent_id=s.agent_id,
                status=s.status,
                created_at=s.created_at,
            )
            for s in self._sessions.values()
            if s.status == "active"
        ]
        return AcpResponse(id="", ok=True, payload={
            "sessions": [
                {"id": s.id, "agent_id": s.agent_id, "status": s.status, "created_at": s.created_at}
                for s in sessions
            ],
        })

    async def handle_close_session(self, params: dict) -> AcpResponse:
        """处理 closeSession 命令"""
        session_id = params.get("session_id", "")
        session = self._sessions.get(session_id)
        if not session:
            return AcpResponse(id="", ok=False, error="session not found")
        session.status = "closed"
        logger.info(f"ACP session closed: {session_id}")
        return AcpResponse(id="", ok=True, payload={"session_id": session_id})

    # ── 事件翻译 ──

    def handle_chat_event(self, event_type: str, data: dict) -> AcpEvent:
        """翻译聊天事件

        将 Gateway 的聊天事件翻译为 ACP 格式：
        - delta → chat_delta
        - final → chat_final
        - aborted → chat_aborted
        - error → chat_error
        """
        event_map = {
            "delta": AcpEventType.CHAT_DELTA,
            "final": AcpEventType.CHAT_FINAL,
            "aborted": AcpEventType.CHAT_ABORTED,
            "error": AcpEventType.CHAT_ERROR,
        }
        acp_type = event_map.get(event_type, AcpEventType.CHAT_DELTA)
        return AcpEvent(
            event=acp_type,
            payload=data,
            session_id=data.get("session_id"),
        )

    def handle_agent_event(self, event_type: str, data: dict) -> AcpEvent:
        """翻译 Agent 工具调用事件

        将 Gateway 的工具调用事件翻译为 ACP 格式：
        - tool_call_start → tool_call_start
        - tool_call_update → tool_call_update
        - tool_call_result → tool_call_result
        """
        event_map = {
            "tool_call_start": AcpEventType.TOOL_CALL_START,
            "tool_call_update": AcpEventType.TOOL_CALL_UPDATE,
            "tool_call_result": AcpEventType.TOOL_CALL_RESULT,
        }
        acp_type = event_map.get(event_type, AcpEventType.TOOL_CALL_START)
        return AcpEvent(
            event=acp_type,
            payload=data,
            session_id=data.get("session_id"),
        )

    # ── 命令分发 ──

    async def dispatch(self, request: AcpRequest) -> AcpResponse:
        """分发 ACP 请求到对应的处理器"""
        handlers = {
            AcpCommand.PROMPT: self.handle_prompt,
            AcpCommand.CREATE_SESSION: self.handle_create_session,
            AcpCommand.LIST_SESSIONS: self.handle_list_sessions,
            AcpCommand.CLOSE_SESSION: self.handle_close_session,
        }
        handler = handlers.get(request.command)
        if not handler:
            return AcpResponse(id=request.id, ok=False, error=f"unknown command: {request.command}")
        response = await handler(request.params)
        response.id = request.id
        return response


async def serve_acp_gateway(
    host: str = "127.0.0.1",
    port: int = 18790,
    gateway_url: str = "ws://127.0.0.1:18789/ws",
) -> None:
    """ACP 网关入口点

    启动 ACP 服务器，接受 ndJson 流连接，
    处理 prompt/createSession/listSessions/closeSession 命令。

    Args:
        host: 绑定地址
        port: 绑定端口
        gateway_url: Gateway WebSocket 地址
    """
    import aiohttp
    from aiohttp import web

    agent = AcpGatewayAgent(gateway_url=gateway_url)
    await agent.connect_to_gateway()

    async def handle_ndjson_stream(request: web.Request) -> web.StreamResponse:
        """处理 ndJson 流连接"""
        response = web.StreamResponse(
            status=200,
            headers={"Content-Type": "application/x-ndjson"},
        )
        await response.prepare(request)

        try:
            async for line in request.content:
                line_str = line.decode("utf-8").strip()
                if not line_str:
                    continue

                try:
                    data = json.loads(line_str)
                except json.JSONDecodeError:
                    error_resp = AcpResponse(id="", ok=False, error="invalid JSON")
                    await response.write(
                        (json.dumps({"type": "response", **error_resp.__dict__}) + "\n").encode()
                    )
                    continue

                # 解析 ACP 请求
                command_str = data.get("command", "")
                try:
                    command = AcpCommand(command_str)
                except ValueError:
                    error_resp = AcpResponse(
                        id=data.get("id", ""),
                        ok=False,
                        error=f"unknown command: {command_str}",
                    )
                    await response.write(
                        (json.dumps({"type": "response", **error_resp.__dict__}) + "\n").encode()
                    )
                    continue

                request_obj = AcpRequest(
                    id=data.get("id", str(uuid.uuid4())),
                    command=command,
                    params=data.get("params", {}),
                )

                # 分发处理
                resp = await agent.dispatch(request_obj)
                resp_line = json.dumps({
                    "type": "response",
                    "id": resp.id,
                    "ok": resp.ok,
                    "payload": resp.payload,
                    "error": resp.error,
                }) + "\n"
                await response.write(resp_line.encode())

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"ACP stream error: {e}")

        return response

    app = web.Application()
    app.router.add_post("/acp", handle_ndjson_stream)
    app.router.add_get("/healthz", lambda r: web.json_response({"status": "ok"}))

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()

    logger.info(f"ACP Gateway server started on {host}:{port}")

    # 保持运行
    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        pass
    finally:
        await agent.disconnect_from_gateway()
        await runner.cleanup()
