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
    plugin_registry =await trace.measure("plugin-bootstrap",lambda: _auto_enable_plugins(cfg))
    # 🔗 连接点：后续实现 plugin_bootstrap 后接入

    # Phase 4: 运行时配置解析
    print("[gateway] Phase 4: 运行时配置解析")
    runtime_cfg = await trace.measure("runtime-config",lambda: _resolve_runtime_config(cfg))
    # 🔗 连接点：后续实现 runtime_config 后接入

    # Phase 5: 创建 HTTP/WS 服务器（aiohttp）
    print("[gateway] Phase 5: 创建 HTTP/WS 服务器")
    app = await _create_http_ws_server(runtime_cfg,auth)
    # 🔗 连接点：后续实现 aiohttp 服务器后接入

    # Phase 6-8: 早期运行时 + WS处理器 + 监听
    print("[gateway] Phase 6-8: WS处理器 + 监听")
    early_runtime = await trace.measure("runtime.early",lambda: _start_early_runtime(app, runtime_cfg))

    # ★ Phase 7: 事件订阅 ★
    await trace.measure("runtime.subscriptions",lambda: _start_event_subscriptions(early_runtime))

    # ★ Phase 8: 方法处理器注册 + 开始监听 ★
    await trace.measure("gateway.handlers",lambda: _register_handlers_and_listen(app, runtime_cfg, plugin_registry, early_runtime))
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

def _parse_and_validate_frame(data: str) -> dict:
    """协议层帧校验：对应 AJV JSON Schema 校验

    解析 JSON 文本并校验帧格式：
    1. JSON 解析 — json.loads(data)
    2. 必需字段检查 — type, method, id
    3. 类型校验 — type 必须是 "request" | "response" | "event"
    4. 方法名格式 — "namespace.method" 格式

    对应 OpenClaw 的 AJV JSON Schema 校验。
    Python 等价方案：jsonschema 库 或 手动校验。

    Args:
        data: WebSocket 接收到的文本消息

    Returns:
        {"valid": True, "type": ..., "method": ..., "id": ..., "params": ...}
        或 {"valid": False, "error": "..."}
    """
    raise NotImplementedError("TODO: 后续章节实现")

async def _dispatch_method(frame: dict, auth: dict) -> dict:
    """方法层分发：
    根据帧中的 method 字段分发到对应的 handler：
    1. 查找方法注册表 — method_registry[frame["method"]]
    2. 权限校验 — authorize_gateway_method()
    3. 调用 handler — handler(frame["params"], auth)
    4. 返回结果 — {"type": "response", "id": ..., "result": ...}

    对应 OpenClaw 的方法分发器。
    方法注册表由 Phase 8 填充。

    Args:
        frame: 已校验的帧 dict
        auth: 用户认证信息

    Returns:
        响应 dict
    """
    raise NotImplementedError("TODO: 后续章节实现")

async def _start_early_runtime(
        app: web.Application,
        runtime_cfg: RuntimeConfig,
) -> dict:
    """对应 startGatewayEarlyRuntime: 早期运行时

    启动早期运行时组件：
    1. 创建 broadcast 实例 — 事件广播器
    2. 创建 nodeRegistry — 节点注册表
    3. 注册本机节点
    4. (可选) 启动 Bonjour/mDNS 服务发现

    为什么在 Phase 5 之后？
    - broadcast 和 nodeRegistry 需要 HTTP 服务器实例
    - 注册自己需要知道实际监听地址和端口

    Python 简化：跳过 Bonjour/mDNS，只保留核心组件。

    Args:
        app: Phase 5 创建的 aiohttp Application
        runtime_cfg: 运行时配置

    Returns:
        {"broadcast": ..., "node_registry": ...}
    """
    raise NotImplementedError("TODO: 后续章节实现")

async def _start_event_subscriptions(
        early_runtime: dict,
) -> None:
    """对应 startGatewayEventSubscriptions: 事件订阅

    注册内部事件监听器：
    1. agent.complete — Agent 完成任务
    2. chat.delta — 聊天流式增量
    3. tool.invoke — 工具调用
    4. node.status — 节点状态变更

    事件驱动架构：Gateway 不主动轮询，
    而是订阅 broadcast 事件后被动响应。

    Args:
        early_runtime: Phase 6 返回的运行时组件
    """
    raise NotImplementedError("TODO: 后续章节实现")


async def _register_handlers_and_listen(
        app: web.Application,
        runtime_cfg: RuntimeConfig,
        plugin_registry: PluginRegistry,
        early_runtime: dict,
) -> None:
    """对应 gateway.handlers + startListening

    两步流程：
    1. 注册方法处理器
       - 核心方法（agent.list, agent.create 等）
       - 插件方法（从 PluginRegistry 提取）
       - 合并到方法注册表 method_registry
    2. 开始监听
       - web.run_app(app, host=bind_host, port=port)

    方法注册表模式：
    method_registry = {
        "agent.list": {
            "handler": handle_agent_list,
            "requiredRole": "user",
            "requiredScopes": ["agent:read"],
        },
        ...
    }

    Args:
        app: Phase 5 创建的 aiohttp Application
        runtime_cfg: 运行时配置
        plugin_registry: Phase 3 返回的插件注册表
        early_runtime: Phase 6 返回的运行时组件
    """
    raise NotImplementedError("TODO: 后续章节实现")