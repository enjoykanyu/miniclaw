import time
import os
import sys
import json
import re
import asyncio
from dataclasses import dataclass, field
from typing import Optional, Callable, Awaitable, Any
from pathlib import Path
from src.channel.health_monitor import ChannelHealthMonitor
from src.channel.runtime_store import ChannelRuntimeStore
from aiohttp import web
import aiohttp

from src.gateway.startup_auth import ensure_gateway_startup_auth
from src.gateway.gates import (
    authenticate_handshake,
    validate_payload_size,
    authorize_gateway_method,
)


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
        # ... 启动所有通道后 ...
        self._health_monitor.start()

    async def shutdown(self):
        self._health_monitor.stop()

    @property
    def runtime(self) -> dict:
        return self._runtime


async def _load_config_snapshot() -> dict:
    config_path = Path("openclaw.json")
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
    raise NotImplementedError("TODO: 后续章节实现")


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
            "valid": True,
            "type": "req",
            "method": method,
            "id": frame_id,
            "params": parsed.get("params", {}),
        }
    elif frame_type == "res":
        frame_id = parsed.get("id")
        ok = parsed.get("ok")
        if not isinstance(frame_id, str) or not frame_id:
            return {"valid": False, "error": "response frame missing 'id'"}
        if not isinstance(ok, bool):
            return {"valid": False, "error": "response frame 'ok' must be boolean"}
        return {
            "valid": True,
            "type": "res",
            "id": frame_id,
            "ok": ok,
            "payload": parsed.get("payload"),
            "error": parsed.get("error"),
        }
    elif frame_type == "event":
        event = parsed.get("event")
        if not isinstance(event, str) or not event:
            return {"valid": False, "error": "event frame missing 'event'"}
        return {
            "valid": True,
            "type": "event",
            "event": event,
            "payload": parsed.get("payload"),
            "seq": parsed.get("seq"),
        }
    else:
        return {"valid": False, "error": f"unknown frame type: {frame_type!r}"}


_METHOD_REGISTRY: dict[str, dict] = {}


def register_method(name: str, handler, *, required_role: str = "user", required_scopes: list[str] | None = None):
    _METHOD_REGISTRY[name] = {
        "handler": handler,
        "required_role": required_role,
        "required_scopes": required_scopes or [],
    }


async def _dispatch_method(frame: dict, auth: dict) -> dict:
    method = frame.get("method", "")
    frame_id = frame.get("id", "unknown")

    auth_error = authorize_gateway_method(method, auth)
    if auth_error:
        return {
            "type": "res",
            "id": frame_id,
            "ok": False,
            "error": auth_error,
        }

    entry = _METHOD_REGISTRY.get(method)
    if not entry:
        return {
            "type": "res",
            "id": frame_id,
            "ok": False,
            "error": {"code": "METHOD_NOT_FOUND", "message": f"unknown method: {method}"},
        }

    try:
        result = await entry["handler"](frame.get("params", {}), auth)
        return {
            "type": "res",
            "id": frame_id,
            "ok": True,
            "payload": result,
        }
    except Exception as exc:
        return {
            "type": "res",
            "id": frame_id,
            "ok": False,
            "error": {"code": "INTERNAL_ERROR", "message": str(exc)},
        }


async def _create_http_ws_server(runtime_cfg, auth):
    app = web.Application()

    async def ws_handler(request):
        ws = web.WebSocketResponse()

        token = request.query.get("token") or \
                request.headers.get("Authorization", "").replace("Bearer ", "")
        if not authenticate_handshake(token, auth):
            return web.Response(status=401, text="Unauthorized")

        await ws.prepare(request)

        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                if not validate_payload_size(msg.data):
                    await ws.close(code=4000, message="Payload too large")
                    break

                frame = _parse_and_validate_frame(msg.data)
                if not frame["valid"]:
                    await ws.close(code=4000, message="Invalid frame")
                    break

                result = await _dispatch_method(frame, auth)
                await ws.send_json(result)

        return ws

    app.router.add_get("/ws", ws_handler)
    return app


async def _start_early_runtime(
        app: web.Application,
        runtime_cfg: RuntimeConfig,
) -> dict:
    raise NotImplementedError("TODO: 后续章节实现")


async def _start_event_subscriptions(
        early_runtime: dict,
) -> None:
    raise NotImplementedError("TODO: 后续章节实现")


async def _register_handlers_and_listen(
        app: web.Application,
        runtime_cfg: RuntimeConfig,
        plugin_registry: PluginRegistry,
        early_runtime: dict,
) -> None:
    raise NotImplementedError("TODO: 后续章节实现")


async def _start_post_attach_runtime(
        app: web.Application,
        runtime_cfg: RuntimeConfig,
        early_runtime: dict,
) -> None:
    raise NotImplementedError("TODO: 后续章节实现")


HOT_RELOADABLE_KEYS = {
    "gateway.logLevel",
    "gateway.maxPayloadBytes",
    "gateway.broadcast.bufferSize",
    "gateway.cron",
}

RESTART_REQUIRED_KEYS = {
    "gateway.port",
    "gateway.bind",
    "gateway.auth",
    "gateway.tls",
}


async def _watch_config_reload(
        config_path: str,
        runtime: dict,
) -> None:
    raise NotImplementedError("TODO: 后续章节实现")


async def start_gateway_server(
        port: int = 18789,
        opts: GatewayServerOptions | None = None,
) -> GatewayServer:
    if opts is None:
        opts = GatewayServerOptions()

    os.environ["OPENCLAW_GATEWAY_PORT"] = str(port)
    trace = StartupTrace()

    print(f"[gateway] Phase 1: 配置快照 port={port}")
    cfg = await trace.measure("config-snapshot", lambda: _load_config_snapshot())

    print("[gateway] Phase 2: 认证配置准备")
    auth_result = await trace.measure("startup-auth", lambda: ensure_gateway_startup_auth(cfg))
    cfg = auth_result.cfg
    auth = auth_result.auth

    print("[gateway] Phase 3: 插件引导")
    plugin_registry = await trace.measure("plugin-bootstrap", lambda: _auto_enable_plugins(cfg))

    print("[gateway] Phase 4: 运行时配置解析")
    runtime_cfg = await trace.measure("runtime-config", lambda: _resolve_runtime_config(cfg))

    print("[gateway] Phase 5: 创建 HTTP/WS 服务器")
    app = await _create_http_ws_server(runtime_cfg, auth)

    print("[gateway] Phase 6: 早期运行时")
    early_runtime = await trace.measure("runtime.early", lambda: _start_early_runtime(app, runtime_cfg))

    print("[gateway] Phase 7: 事件订阅")
    await trace.measure("runtime.subscriptions", lambda: _start_event_subscriptions(early_runtime))

    print("[gateway] Phase 8: 方法处理器注册 + 开始监听")
    await trace.measure("gateway.handlers", lambda: _register_handlers_and_listen(app, runtime_cfg, plugin_registry, early_runtime))

    print("[gateway] Phase 9: 后附加运行时")
    await trace.measure("runtime.post-attach", lambda: _start_post_attach_runtime(app, runtime_cfg, early_runtime))

    print("[gateway] Phase 10: 配置热重载")
    config_path = str(Path("openclaw.json"))
    runtime = {"app": app, "cfg": cfg, "auth": auth, "early_runtime": early_runtime}
    asyncio.create_task(_watch_config_reload(config_path, runtime))

    print(f"[gateway] ✅ 10 阶段启动完成，监听 port={port}")

    async def close(reason: str = "shutdown") -> None:
        print(f"[gateway] Closing: {reason}")

    return GatewayServer(close=close, runtime=runtime)
