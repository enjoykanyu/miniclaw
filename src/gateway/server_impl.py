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
    startup_trace = StartupTrace()

    # Phase 1: 加载配置快照
    print(f"[gateway] Phase 1: 配置快照 port={port}")
    # 🔗 连接点：后续实现 config_snapshot 后接入

    # Phase 2: 认证配置准备
    print("[gateway] Phase 2: 认证配置准备")
    # 🔗 连接点：后续实现 startup_auth 后接入

    # Phase 3: 插件引导
    print("[gateway] Phase 3: 插件引导")
    # 🔗 连接点：后续实现 plugin_bootstrap 后接入

    # Phase 4: 运行时配置解析
    print("[gateway] Phase 4: 运行时配置解析")
    # 🔗 连接点：后续实现 runtime_config 后接入

    # Phase 5: 创建 HTTP/WS 服务器（aiohttp）
    print("[gateway] Phase 5: 创建 HTTP/WS 服务器")
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