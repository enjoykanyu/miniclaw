import time
import os
import sys
from dataclasses import dataclass
from typing import Optional, Callable, Awaitable, Any

@dataclass
class GatewayServer:
    close: Callable[[], Awaitable[None]]

@dataclass
class GatewayServerOptions:
    bind: Optional[str] = None
    host: Optional[str] = None
    control_ui_enabled: bool = True
    openai_chat_enabled: bool = True
    auth: Optional[dict] = None
    tailscale: Optional[dict] = None
    defer_startup_sidecars: bool = False

class StartupTrace:
    """对应 createGatewayStartupTrace(): 启动追踪器"""
    def __init__(self):
        self._started = time.perf_counter()

    async def measure(self, name: str, fn) -> Any:
        before = time.perf_counter()
        try:
            return await fn()
        finally:
            elapsed = (time.perf_counter() - before) * 1000
            total = (time.perf_counter() - self._started) * 1000
            if os.environ.get("OPENCLAW_GATEWAY_STARTUP_TRACE"):
                sys.stderr.write(
                    f"[gateway] trace: {name} "
                    f"{elapsed:.1f}ms total={total:.1f}ms\n"
                )

async def start_gateway_server(
        port: int = 18789,
        opts: GatewayServerOptions | None = None,
) -> GatewayServer:
    """对应 startGatewayServer(): 核心启动流程"""
    if opts is None:
        opts = GatewayServerOptions()

    os.environ["OPENCLAW_GATEWAY_PORT"] = str(port)
    trace = StartupTrace()

    # Phase 1: 加载配置快照
    print(f"[gateway] Phase 1: 配置快照 port={port}")
    cfg = await trace.measure("config-snapshot",lambda: _load_config_snapshot())
    # 🔗 连接点：后续实现 config_snapshot 后接入

    # Phase 2: 认证配置准备
    print("[gateway] Phase 2: 认证配置准备")
    from src.gateway.startup_auth import ensure_gateway_startup_auth
    auth_result = await trace.measure("startup-auth",lambda: ensure_gateway_startup_auth(cfg))
    cfg = auth_result.cfg
    auth = auth_result.auth
    # 🔗 连接点：后续实现 startup_auth 后接入

    # Phase 3: 插件引导
    print("[gateway] Phase 3: 插件引导")
    await trace.measure("plugin-bootstrap",lambda: _auto_enable_plugins(cfg))
    # 🔗 连接点：后续实现 plugin_bootstrap 后接入

    # Phase 4: 运行时配置解析
    print("[gateway] Phase 4: 运行时配置解析")
    runtime_cfg = await trace.measure("runtime-config",lambda: _resolve_runtime_config(cfg))
    # 🔗 连接点：后续实现 runtime_config 后接入

    # Phase 5: 创建 HTTP/WS 服务器（aiohttp）
    print("[gateway] Phase 5: 创建 HTTP/WS 服务器")
    await _create_http_ws_server(runtime_cfg,auth)
    # 🔗 连接点：后续实现 aiohttp 服务器后接入

    # Phase 6-8: 早期运行时 + WS处理器 + 监听
    print("[gateway] Phase 6-8: WS处理器 + 监听")

    # Phase 9: 后附加运行时
    print("[gateway] Phase 9: 后附加运行时")

    # Phase 10: 配置热重载
    print("[gateway] Phase 10: 配置热重载")

    print(f"[gateway] ✅ 10 阶段启动完成，监听 port={port}")

    async def close(reason: str = "shutdown") -> None:
        print(f"[gateway] Closing: {reason}")

    return GatewayServer(close=close)



from aiohttp import web
import aiohttp
from src.gateway.gates import (
    authenticate_handshake,   # 🔗 待实现
    validate_payload_size,    # 🔗 待实现
    authorize_gateway_method, # 🔗 待实现
)
async def _create_http_ws_server(runtime_cfg, auth):
    """对应 createHttpWsServer: 用 aiohttp 替代 Node.js http/ws"""
    app = web.Application()

    # 连接总闸：WebSocket 握手认证
    async def ws_handler(request):
        ws = web.WebSocketResponse()

        # 连接总闸：握手认证
        token = request.query.get("token") or \
                request.headers.get("Authorization", "").replace("Bearer ", "")
        # TODO 未实现 握手认证
        if not authenticate_handshake(token, auth):
            return web.Response(status=401, text="Unauthorized")

        await ws.prepare(request)

        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                # 带宽总闸 TODO未实现
                if not validate_payload_size(msg.data):
                    await ws.close(code=4000,
                                   message="Payload too large")
                    break

                # 协议层：帧校验 TOTO未实现
                frame = _parse_and_validate_frame(msg.data)
                if not frame["valid"]:
                    await ws.close(code=4000,
                                   message="Invalid frame")
                    break

                # 方法层：权限校验 + 分发 TODO 未实现
                result = await _dispatch_method(frame, auth)
                await ws.send_json(result)

        return ws

    app.router.add_get("/ws", ws_handler)
    return app


import json
from pathlib import Path

async def _load_config_snapshot() -> dict:
    """读取JSON配置文件，返回dict"""
    config_path = Path("openclaw.json")
    if not config_path.exists():
        return _default_config()

    raw = config_path.read_text(encoding="utf-8")
    parsed = json.loads(raw)
    return {**_default_config(), **parsed}

def _default_config() -> dict:
    """默认配置"""
    return {
        "gateway": {
            "port": 18789,
            "auth": {"mode": "token"},
            "maxPayloadBytes": 1048576,
            "logLevel": "info",
        }
    }

from dataclasses import dataclass, field
from typing import Any

@dataclass
class PluginRegistry:
    plugins: dict[str, Any] = field(default_factory=dict)
    methods: dict[str, dict] = field(default_factory=dict)

async def _auto_enable_plugins(cfg: dict) -> PluginRegistry:
    """对应 prepareGatewayPluginBootstrap: 插件引导

    三步流程：
    1. discover — 用 importlib.metadata.entry_points() 发现插件
    2. register — 读取插件 manifest，构建注册表
    3. extract  — 提取 Gateway 方法描述符

    Args:
        cfg: Phase 1 返回的配置 dict

    Returns:
        PluginRegistry 包含插件注册表和方法描述符
    """
    raise NotImplementedError("TODO: 后续章节实现")

@dataclass
class RuntimeConfig:
    bind_host: str = "0.0.0.0"
    port: int = 18789
    auth: dict | None = None
    tls: dict | None = None
    cors_origins: list[str] = field(default_factory=list)
    max_payload_bytes: int = 1048576
    log_level: str = "info"

async def _resolve_runtime_config(cfg: dict) -> RuntimeConfig:
    """对应 resolveGatewayRuntimeConfig: 运行时配置解析

    将启动配置「编译」为运行时配置：
    1. 合并环境变量覆盖（PORT, BIND_HOST 等）
    2. 解析 bind 地址
    3. 解析 TLS 配置
    4. 解析认证配置
    5. 解析 CORS 来源

    Args:
        cfg: Phase 1-3 处理后的配置 dict

    Returns:
        RuntimeConfig dataclass，所有字段已解析
    """
    raise NotImplementedError("TODO: 后续章节实现")