"""
Gateway Server Implementation — FastAPI 版

迁移方法论：
  aiohttp → FastAPI 的核心变化是"从手动路由到声明式路由"。

  为什么迁移？
  1. FastAPI 是 AI 生态事实标准（LangServe/LangGraph Platform 均基于 FastAPI）
  2. 自动 OpenAPI 文档 → 前端/客户端可直接生成 SDK
  3. Pydantic 请求/响应验证 → 类型安全，减少手动校验代码
  4. StaticFiles 内置支持 → 零成本接入 WebUI
  5. WebSocket 原生支持 → 不丢失任何现有功能

  迁移对照表：
  ┌─────────────────────────┬──────────────────────────────┐
  │ aiohttp                 │ FastAPI                       │
  ├─────────────────────────┼──────────────────────────────┤
  │ web.Application()       │ FastAPI()                     │
  │ app.router.add_get()    │ @app.get()                    │
  │ web.WebSocketResponse() │ WebSocket (参数注入)           │
  │ web.json_response()     │ return dict (自动序列化)       │
  │ web.AppRunner + TCPSite │ uvicorn.Server                │
  │ 手动 JSON 校验          │ Pydantic BaseModel 自动校验    │
  │ 无 API 文档             │ 自动 /docs (Swagger UI)       │
  │ 无静态文件支持           │ StaticFiles 中间件             │
  └─────────────────────────┴──────────────────────────────┘
"""

import time
import os
import sys
import json
import re
import asyncio
from dataclasses import dataclass, field
from typing import Optional, Callable, Awaitable, Any
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from channel.health_monitor import ChannelHealthMonitor
from channel.runtime_store import ChannelRuntimeStore
from gateway.startup_auth import ensure_gateway_startup_auth
from gateway.gates import (
    authenticate_handshake,
    validate_payload_size,
    authorize_gateway_method,
)
from gateway.config_reload import _watch_config_reload
from gateway.graceful_shutdown import (
    get_shutdown_manager,
)


# ──────────────────────────────────────────────────────────
# 数据模型：Pydantic BaseModel 替代手动 JSON 校验
#
# 为什么用 Pydantic？
# 1. 自动类型校验：字段类型不对直接 422，无需手动检查
# 2. 自动生成 OpenAPI Schema → /docs 可视化
# 3. IDE 自动补全：字段名拼写错误在编辑时就能发现
# ──────────────────────────────────────────────────────────

class AgentRunRequest(BaseModel):
    """agent.run REST API 请求体"""
    message: str
    user_id: str = "default"
    session_id: str = "default"
    thread_id: str = ""
    force_think: bool = False
    force_search: bool = False
    selected_kbs: list[str] | None = None
    kb_retrieval_mode: str = "intent"
    run_id: str = ""  # 幂等性去重键，对标 OpenClaw runId


class AgentRunResponse(BaseModel):
    """agent.run REST API 响应体"""
    response: str
    agent: str = "agentic_loop"
    status: str = "completed"
    error: str | None = None


# ──────────────────────────────────────────────────────────
# 配置与启动追踪（与 aiohttp 版完全相同，无需迁移）
# ──────────────────────────────────────────────────────────

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


class GatewayServer:
    def __init__(self, close: Callable[[], Awaitable[None]], runtime: dict | None = None):
        self._close = close
        self._runtime = runtime or {}
        self._channel_store = ChannelRuntimeStore()
        self._health_monitor = ChannelHealthMonitor(
            self._channel_store,
            check_interval_s=300.0,
            cooldown_cycles=2,
            max_restarts_per_hour=10,
        )

    async def close(self, reason: str = "shutdown") -> None:
        await self._close(reason)

    async def start(self):
        self._health_monitor.start()

    async def shutdown(self):
        self._health_monitor.stop()

    @property
    def runtime(self) -> dict:
        return self._runtime


# ──────────────────────────────────────────────────────────
# 配置加载（与 aiohttp 版完全相同）
# ──────────────────────────────────────────────────────────

def _resolve_config_path() -> Path:
    """解析配置文件路径，优先使用环境变量，回退到项目根目录"""
    env_path = os.environ.get("MINICLAW_CONFIG_PATH")
    if env_path:
        return Path(env_path)
    # 项目根目录（src 的上级目录）
    project_root = Path(__file__).parent.parent
    return project_root / "openclaw.json"


async def _load_config_snapshot() -> dict:
    config_path = _resolve_config_path()
    if not config_path.exists():
        return _default_config()
    raw = config_path.read_text(encoding="utf-8")
    parsed = json.loads(raw)
    return {**_default_config(), **parsed}


def _default_config() -> dict:
    return {
        "gateway": {
            "port": 18789,
            "auth": {"mode": "token"},
            "maxPayloadBytes": 1048576,
            "logLevel": "info",
        }
    }


@dataclass
class PluginRegistry:
    plugins: dict[str, Any] = field(default_factory=dict)
    methods: dict[str, dict] = field(default_factory=dict)


async def _auto_enable_plugins(cfg: dict) -> PluginRegistry:
    registry = PluginRegistry()
    return registry


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
    gw = cfg.get("gateway", {})
    bind_mode = gw.get("bind", "loopback")
    if bind_mode == "loopback":
        bind_host = "127.0.0.1"
    elif bind_mode == "lan":
        bind_host = "0.0.0.0"
    else:
        bind_host = gw.get("bind", "0.0.0.0")
    return RuntimeConfig(
        bind_host=bind_host,
        port=gw.get("port", 18789),
        auth=gw.get("auth"),
        tls=gw.get("tls"),
        cors_origins=gw.get("corsOrigins", []),
        max_payload_bytes=gw.get("maxPayloadBytes", 1048576),
        log_level=gw.get("logLevel", "info"),
    )


# ──────────────────────────────────────────────────────────
# 帧协议（与 aiohttp 版完全相同，这是业务逻辑不依赖框架）
# ──────────────────────────────────────────────────────────

_METHOD_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+$")


def _parse_and_validate_frame(data: str) -> dict:
    try:
        parsed = json.loads(data)
    except (json.JSONDecodeError, TypeError):
        return {"valid": False, "error": "invalid JSON"}

    if not isinstance(parsed, dict):
        return {"valid": False, "error": "frame must be a JSON object"}

    frame_type = parsed.get("type")
    if frame_type == "req":
        method = parsed.get("method")
        frame_id = parsed.get("id")
        if not isinstance(method, str) or not method:
            return {"valid": False, "error": "request frame missing 'method'"}
        if not isinstance(frame_id, str) or not frame_id:
            return {"valid": False, "error": "request frame missing 'id'"}
        if not _METHOD_NAME_PATTERN.match(method):
            return {"valid": False, "error": f"invalid method name format: {method}"}
        return {
            "valid": True, "type": "req", "method": method,
            "id": frame_id, "params": parsed.get("params", {}),
        }
    elif frame_type == "res":
        frame_id = parsed.get("id")
        ok = parsed.get("ok")
        if not isinstance(frame_id, str) or not frame_id:
            return {"valid": False, "error": "response frame missing 'id'"}
        if not isinstance(ok, bool):
            return {"valid": False, "error": "response 'ok' must be boolean"}
        return {
            "valid": True, "type": "res", "id": frame_id,
            "ok": ok, "payload": parsed.get("payload"), "error": parsed.get("error"),
        }
    elif frame_type == "event":
        event = parsed.get("event")
        if not isinstance(event, str) or not event:
            return {"valid": False, "error": "event frame missing 'event'"}
        return {
            "valid": True, "type": "event", "event": event,
            "payload": parsed.get("payload"), "seq": parsed.get("seq"),
        }
    else:
        return {"valid": False, "error": f"unknown frame type: {frame_type!r}"}


# ──────────────────────────────────────────────────────────
# 方法注册表（与 aiohttp 版完全相同）
# ──────────────────────────────────────────────────────────

_METHOD_REGISTRY: dict[str, dict] = {}
_METHOD_REGISTRY_LOCK = asyncio.Lock()
_METHOD_REGISTRY_SEALED = False  # 启动完成后封印，运行时只读


def register_method(name: str, handler, *, required_role: str = "user", required_scopes: list[str] | None = None):
    """注册方法处理器。启动阶段可写，运行时封印后禁止修改（对标 OpenClaw 启动时一次性注册）。"""
    if _METHOD_REGISTRY_SEALED:
        raise RuntimeError(f"Method registry is sealed (runtime read-only). Cannot register '{name}'")
    _METHOD_REGISTRY[name] = {
        "handler": handler,
        "required_role": required_role,
        "required_scopes": required_scopes or [],
    }


def seal_method_registry():
    """封印方法注册表，启动完成后调用，运行时禁止新增方法"""
    global _METHOD_REGISTRY_SEALED
    _METHOD_REGISTRY_SEALED = True


async def _dispatch_method(frame: dict, auth: dict) -> dict:
    method = frame.get("method", "")
    frame_id = frame.get("id", "unknown")

    entry = _METHOD_REGISTRY.get(method)
    descriptor = entry if entry else None
    auth_error = authorize_gateway_method(method, auth, descriptor)
    if auth_error:
        return {"type": "res", "id": frame_id, "ok": False, "error": auth_error}

    if not entry:
        return {
            "type": "res", "id": frame_id, "ok": False,
            "error": {"code": "METHOD_NOT_FOUND", "message": f"unknown method: {method}"},
        }

    try:
        result = await entry["handler"](frame.get("params", {}), auth)
        return {"type": "res", "id": frame_id, "ok": True, "payload": result}
    except Exception as exc:
        return {
            "type": "res", "id": frame_id, "ok": False,
            "error": {"code": "INTERNAL_ERROR", "message": str(exc)},
        }


# ──────────────────────────────────────────────────────────
# FastAPI 应用工厂
#
# 核心迁移点：aiohttp 的 web.Application() → FastAPI()
#
# 为什么用工厂函数而非全局 app？
# 1. 测试时可以创建多个独立 app 实例
# 2. 配置可以在工厂中注入，而非依赖全局变量
# 3. 生命周期管理更清晰（lifespan 参数）
# ──────────────────────────────────────────────────────────

def create_app(runtime_cfg: RuntimeConfig, auth: dict) -> FastAPI:
    """
    创建 FastAPI 应用实例

    迁移对照：
    - aiohttp: app = web.Application() → app.router.add_get("/ws", handler)
    - FastAPI: app = FastAPI()         → @app.websocket("/ws") async def handler(ws)
    """
    app = FastAPI(
        title="MiniClaw Gateway",
        description="MiniClaw AI Agent Gateway — 对标 OpenClaw Gateway",
        version="0.1.0",
        docs_url="/docs",          # Swagger UI
        redoc_url="/redoc",        # ReDoc
    )

    # ── CORS 中间件 ──
    # aiohttp 版需要手动处理 CORS，FastAPI 一行搞定
    if runtime_cfg.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=runtime_cfg.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # ── 存储运行时配置供路由使用 ──
    app.state.runtime_cfg = runtime_cfg
    app.state.auth = auth

    # ── 优雅关闭中间件 ──
    # 关闭期间拒绝新请求
    shutdown_mgr = get_shutdown_manager()

    @app.middleware("http")
    async def shutdown_middleware(request, call_next):
        if shutdown_mgr.is_shutting_down:
            return JSONResponse(
                status_code=503,
                content={"detail": "Server is shutting down"},
            )
        # 跟踪在途请求
        request_id = f"rest-{id(request)}"
        await shutdown_mgr.add_in_flight_request(request_id)
        try:
            response = await call_next(request)
            return response
        finally:
            await shutdown_mgr.remove_in_flight_request(request_id)

    # ── 初始化 Broadcaster（对标 OpenClaw GatewayBroadcaster）──
    from gateway.broadcast import GatewayBroadcaster
    app.state.broadcaster = GatewayBroadcaster()

    # ══════════════════════════════════════════════════════
    # HTTP REST 路由（新增！aiohttp 版没有）
    #
    # 为什么新增 REST API？
    # 1. WebUI 前端需要 HTTP 接口（浏览器不方便用 WebSocket）
    # 2. OpenAI 兼容接口需要 REST（/v1/chat/completions）
    # 3. 自动 /docs 文档让开发者快速了解 API
    # ══════════════════════════════════════════════════════

    @app.get("/healthz", tags=["系统"])
    async def health_check():
        """健康检查 — 对标 OpenClaw /healthz"""
        return {"status": "ok", "port": runtime_cfg.port}

    @app.get("/readyz", tags=["系统"])
    async def readiness_check():
        """就绪检查 — 对标 OpenClaw /readyz"""
        return {"ready": True}

    @app.post("/api/v1/agent/run", response_model=AgentRunResponse, tags=["Agent"])
    async def rest_agent_run(req: AgentRunRequest):
        """
        Agent 对话 REST API（新增！）

        为什么需要这个？
        - WebUI 前端用 HTTP POST 比 WebSocket 更简单
        - curl 测试更方便
        - 自动出现在 /docs 文档中

        对比 WebSocket 版 agent.run：
        - WS 版: 发送 JSON 帧 → 接收 JSON 帧
        - REST 版: POST JSON → 返回 JSON（更符合 HTTP 语义）
        """
        try:
            from gateway.agent_methods import handle_agent_run
            result = await handle_agent_run(req.model_dump(), {"ok": True, "role": "user"})
            return AgentRunResponse(**result)
        except Exception as e:
            return AgentRunResponse(response="", status="failed", error=str(e)[:200])

    @app.get("/api/v1/agent/list", tags=["Agent"])
    async def rest_agent_list():
        """列出可用 Agent（新增 REST 端点）"""
        from gateway.agent_methods import handle_agent_list
        return await handle_agent_list({}, {"ok": True, "role": "user"})

    @app.get("/api/v1/agent/status", tags=["Agent"])
    async def rest_agent_status():
        """查询 Agent 状态（新增 REST 端点）"""
        from gateway.agent_methods import handle_agent_status
        return await handle_agent_status({}, {"ok": True, "role": "user"})

    # ── Chat REST 端点（对标 OpenClaw chat.history / chat.list）──

    @app.get("/api/v1/chat/history", tags=["Chat"])
    async def rest_chat_history(
        thread_id: str = Query(default=""),
        limit: int = Query(default=50, ge=1, le=500),
    ):
        """查询会话历史 — 对标 OpenClaw chat.history"""
        from gateway.chat_history import handle_chat_history
        return await handle_chat_history(
            {"thread_id": thread_id, "limit": limit},
            {"ok": True, "role": "user"},
        )

    @app.get("/api/v1/chat/list", tags=["Chat"])
    async def rest_chat_list(agent_id: str = Query(default="default")):
        """列出所有会话 — 对标 OpenClaw chat.list"""
        from gateway.chat_history import handle_chat_list
        return await handle_chat_list(
            {"agent_id": agent_id},
            {"ok": True, "role": "user"},
        )

    # ── OpenAI 兼容接口（对标 OpenClaw /v1/chat/completions）──

    @app.post("/v1/chat/completions", tags=["OpenAI"])
    async def rest_openai_chat_completions(request: Request):
        """OpenAI 兼容接口 — 对标 OpenClaw /v1/chat/completions"""
        from gateway.openai_compat import openai_chat_completions
        return await openai_chat_completions(request)

    # ══════════════════════════════════════════════════════
    # WebSocket 路由（迁移自 aiohttp）
    #
    # 迁移对照：
    # aiohttp:
    #   async def ws_handler(request):
    #       ws = web.WebSocketResponse()
    #       await ws.prepare(request)
    #       async for msg in ws:
    #           if msg.type == WSMsgType.TEXT: ...
    #
    # FastAPI:
    #   @app.websocket("/ws")
    #   async def ws_endpoint(ws: WebSocket):
    #       await ws.accept()
    #       while True:
    #           data = await ws.receive_text()
    #           ...
    #
    # 关键差异：
    # 1. FastAPI 的 WebSocket 是参数注入，不需要 prepare()
    # 2. FastAPI 用 WebSocketDisconnect 异常处理断开，而非 for 循环
    # 3. 认证通过 Query 参数传递（与 aiohttp 版一致）
    # ══════════════════════════════════════════════════════

    @app.websocket("/ws")
    async def websocket_endpoint(
        ws: WebSocket,
        token: str = Query(default=""),
    ):
        """
        WebSocket 帧协议端点 — 对标 OpenClaw Gateway WebSocket

        认证流程（与 aiohttp 版完全一致）：
        1. 客户端连接 ws://host:port/ws?token=xxx
        2. 服务端验证 token → 401 或接受连接
        3. 客户端发送 req 帧 → 服务端返回 res 帧
        """
        # 先 accept 连接，再验证 token
        # 修复: FastAPI 的 WebSocket 在 accept 之前调用 close 会抛异常
        # OpenClaw 做法: 先建立连接，发送 challenge，客户端回传后验证

        # ── 关闭期间拒绝新 WebSocket 连接 ──
        if shutdown_mgr.is_shutting_down:
            await ws.close(code=1001, reason="Server is shutting down")
            return

        await ws.accept()

        # ── 注册 WebSocket 到关闭管理器 ──
        shutdown_mgr.register_websocket(ws)

        # ── 跟踪在途请求 ──
        ws_request_id = f"ws-{id(ws)}"
        await shutdown_mgr.add_in_flight_request(ws_request_id)

        # ── 认证（第1闸）──
        auth_result = authenticate_handshake(token, auth)
        if not auth_result.get("ok"):
            await ws.close(code=4001, reason=f"Unauthorized: {auth_result.get('reason', '')}")
            return

        # ── 注册到 Broadcaster ──
        import uuid as _uuid
        conn_id = f"ws-{_uuid.uuid4().hex[:12]}"
        broadcaster = getattr(app.state, "broadcaster", None)
        if broadcaster:
            await broadcaster.add_client(conn_id, ws, auth_result)

        try:
            while True:
                data = await ws.receive_text()

                # ── 载荷验证（第3闸）──
                size_result = validate_payload_size(data, runtime_cfg.max_payload_bytes)
                if not size_result.get("ok"):
                    await ws.close(code=4000, reason="Payload too large")
                    break

                # ── 帧解析 ──
                frame = _parse_and_validate_frame(data)
                if not frame["valid"]:
                    await ws.close(code=4000, reason=f"Invalid frame: {frame['error']}")
                    break

                # ── 方法调度（含第2闸授权）──
                result = await _dispatch_method(frame, auth_result)
                await ws.send_json(result)

        except WebSocketDisconnect:
            pass  # 客户端正常断开
        except Exception as e:
            print(f"[gateway] WebSocket error: {e}", file=sys.stderr)
        finally:
            # ── 从 Broadcaster 移除 ──
            if broadcaster:
                await broadcaster.remove_client(conn_id)
            # ── 从关闭管理器注销 ──
            shutdown_mgr.unregister_websocket(ws)
            await shutdown_mgr.remove_in_flight_request(ws_request_id)

    # ══════════════════════════════════════════════════════
    # WebUI 静态文件（新增！aiohttp 版没有）
    #
    # 为什么需要这个？
    # 1. 用户通过浏览器访问 http://host:port/ 即可使用 WebUI
    # 2. 前端 React/Vue 构建产物放到 webui/ 目录即可
    # 3. 无需额外部署 Nginx
    # ══════════════════════════════════════════════════════

    webui_path = Path(__file__).parent.parent / "webui"
    if webui_path.exists() and webui_path.is_dir():
        app.mount("/", StaticFiles(directory=str(webui_path), html=True), name="webui")

    return app


# ──────────────────────────────────────────────────────────
# 早期运行时 / 事件订阅 / 后附加运行时（占位，与 aiohttp 版相同）
# ──────────────────────────────────────────────────────────

async def _start_early_runtime(app: FastAPI, runtime_cfg: RuntimeConfig) -> dict:
    return {
        "health_route_added": True,
        "cors_configured": len(runtime_cfg.cors_origins) > 0,
    }


async def _start_event_subscriptions(early_runtime: dict) -> None:
    pass


async def _register_handlers_and_listen(
    app: FastAPI,
    runtime_cfg: RuntimeConfig,
    plugin_registry: PluginRegistry,
    early_runtime: dict,
) -> None:
    """注册插件方法到全局注册表"""
    for method_name, method_entry in plugin_registry.methods.items():
        register_method(
            method_name,
            method_entry.get("handler"),
            required_role=method_entry.get("required_role", "user"),
        )


async def _start_post_attach_runtime(
    app: FastAPI,
    runtime_cfg: RuntimeConfig,
    early_runtime: dict,
) -> None:
    pass


# ──────────────────────────────────────────────────────────
# Gateway 主启动函数
#
# 核心迁移点：
# aiohttp: web.AppRunner + web.TCPSite → 手动管理服务器生命周期
# FastAPI: uvicorn.Server → 配置化启动，自动管理生命周期
#
# 为什么 uvicorn 比 aiohttp AppRunner 更好？
# 1. uvicorn 是 ASGI 服务器，支持 HTTP/1.1、HTTP/2、WebSocket
# 2. 内置 graceful shutdown（信号处理）
# 3. 性能更好（基于 httptools 或 uvloop）
# 4. 与 FastAPI 生态深度集成
# ──────────────────────────────────────────────────────────

async def start_gateway_server(
    port: int = 18789,
    opts: GatewayServerOptions | None = None,
) -> GatewayServer:
    if opts is None:
        opts = GatewayServerOptions()

    os.environ["OPENCLAW_GATEWAY_PORT"] = str(port)
    trace = StartupTrace()

    # ── Phase 1-4：与 aiohttp 版完全相同 ──
    print(f"[gateway] Phase 1: 配置快照 port={port}")
    cfg = await trace.measure("config-snapshot", lambda: _load_config_snapshot())

    print("[gateway] Phase 2: 认证配置准备")
    auth_result = await trace.measure("startup-auth", lambda: ensure_gateway_startup_auth(cfg))
    cfg = auth_result.cfg
    auth = auth_result.auth
    if auth_result.generated_token:
        print(f"[gateway] 🔑 Generated auth token: {auth_result.generated_token}")
        print(f"[gateway]    Use: ws://127.0.0.1:{port}/ws?token={auth_result.generated_token}")

    print("[gateway] Phase 3: 插件引导")
    plugin_registry = await trace.measure("plugin-bootstrap", lambda: _auto_enable_plugins(cfg))

    print("[gateway] Phase 4: 运行时配置解析")
    runtime_cfg = await trace.measure("runtime-config", lambda: _resolve_runtime_config(cfg))

    # ── Phase 5：创建 FastAPI 应用（核心变化）──
    print("[gateway] Phase 5: 创建 FastAPI 应用")
    app = create_app(runtime_cfg, auth)

    print("[gateway] Phase 6: 早期运行时")
    early_runtime = await trace.measure("runtime.early", lambda: _start_early_runtime(app, runtime_cfg))

    print("[gateway] Phase 7: 事件订阅")
    await trace.measure("runtime.subscriptions", lambda: _start_event_subscriptions(early_runtime))

    print("[gateway] Phase 8: 方法处理器注册")
    await trace.measure("gateway.handlers", lambda: _register_handlers_and_listen(app, runtime_cfg, plugin_registry, early_runtime))

    try:
        from gateway.agent_methods import register_agent_methods
        register_agent_methods()
        print("[gateway] Agent methods registered (agent.run, agent.list, agent.status)")
    except Exception as e:
        print(f"[gateway] Warning: Agent methods registration failed: {e}", file=sys.stderr)

    try:
        from gateway.chat_history import register_chat_methods
        register_chat_methods()
        print("[gateway] Chat methods registered (chat.history, chat.list)")
    except Exception as e:
        print(f"[gateway] Warning: Chat methods registration failed: {e}", file=sys.stderr)

    print("[gateway] Phase 9: 后附加运行时")
    await trace.measure("runtime.post-attach", lambda: _start_post_attach_runtime(app, runtime_cfg, early_runtime))

    # 封印方法注册表：启动阶段结束，运行时禁止新增方法（对标 OpenClaw 启动时一次性注册）
    seal_method_registry()
    print(f"[gateway] Method registry sealed: {len(_METHOD_REGISTRY)} methods registered")

    print("[gateway] Phase 10: 配置热重载")
    config_path = str(_resolve_config_path())
    runtime = {"app": app, "cfg": cfg, "auth": auth, "early_runtime": early_runtime}
    asyncio.create_task(_watch_config_reload(config_path, runtime))

    # ── 启动 uvicorn 服务器 ──
    # aiohttp 版: runner = web.AppRunner(app) → runner.setup() → site = web.TCPSite(runner, host, port)
    # FastAPI 版: config = uvicorn.Config(app, host, port) → server = uvicorn.Server(config)
    print(f"[gateway] ✅ 10 阶段启动完成，监听 port={port}")
    print(f"[gateway] 📖 API 文档: http://127.0.0.1:{port}/docs")

    shutdown_event = asyncio.Event()

    # ── 初始化优雅关闭管理器 ──
    shutdown_mgr = get_shutdown_manager()

    # 先创建 GatewayServer（close 函数稍后赋值）
    server = GatewayServer(close=lambda reason="shutdown": None, runtime=runtime)

    # 注册关闭处理器
    channel_store = server._channel_store
    health_monitor = server._health_monitor

    async def _close_channels():
        """关闭 Channel"""
        try:
            channel_store.stop_all()
        except Exception as e:
            logger.error(f"Close channels failed: {e}")

    async def _stop_health_monitor():
        """停止健康监控"""
        try:
            health_monitor.stop()
        except Exception as e:
            logger.error(f"Stop health monitor failed: {e}")

    async def _stop_config_reload():
        """停止配置热重载（由 _watch_config_reload 的 CancelledError 处理）"""
        logger.info("Config reload will stop on task cancellation")

    async def _close_http_server():
        """关闭 HTTP 服务器"""
        uv_server.should_exit = True

    shutdown_mgr.register_handler("close_channels", _close_channels, priority=10)
    shutdown_mgr.register_handler("stop_health_monitor", _stop_health_monitor, priority=20)
    shutdown_mgr.register_handler("stop_config_reload", _stop_config_reload, priority=30)
    shutdown_mgr.register_handler("close_http_server", _close_http_server, priority=40)

    # 注册信号处理器
    shutdown_mgr.setup_signal_handlers()

    async def close(reason: str = "shutdown") -> None:
        """触发优雅关闭"""
        await shutdown_mgr.shutdown(reason)
        shutdown_event.set()

    # 更新 server 的 close 方法
    server._close = close

    # 启动 uvicorn（在后台运行）
    uv_config = uvicorn.Config(
        app,
        host=runtime_cfg.bind_host,
        port=runtime_cfg.port,
        log_level=runtime_cfg.log_level,
        access_log=False,
    )
    uv_server = uvicorn.Server(uv_config)

    # uvicorn.serve() 会阻塞直到服务器关闭
    serve_task = asyncio.create_task(uv_server.serve())

    try:
        await shutdown_event.wait()
    except asyncio.CancelledError:
        pass
    finally:
        uv_server.should_exit = True
        await serve_task

    return server
