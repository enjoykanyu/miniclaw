import time
import sys
import os
import importlib
from typing import Any

_server_impl: Any | None = None

def emit_startup_trace(name: str, duration_ms: float, total_ms: float) -> None:
    """对应 emitStartupTrace(): 启动追踪输出"""
    if not os.environ.get("OPENCLAW_GATEWAY_STARTUP_TRACE"):
        return
    sys.stderr.write(
        f"[gateway] startup trace: {name} "
        f"{duration_ms:.1f}ms total={total_ms:.1f}ms\n"
    )

async def load_server_impl():
    """对应 loadServerImpl(): 懒加载核心实现"""
    global _server_impl
    startup_started = time.perf_counter()
    before = time.perf_counter()
    try:
        _server_impl = importlib.import_module(
            ".gateway.server_impl", __package__
        )
        return _server_impl
    finally:
        now = time.perf_counter()
        emit_startup_trace(
            "gateway.server-impl-import",
            (now - before) * 1000,
            (now - startup_started) * 1000,
            )

async def start_gateway_server(port: int = 18789, **kwargs) -> Any:
    """对应 startGatewayServer(): 门面函数"""
    mod = await load_server_impl()
    return await mod.start_gateway_server(port=port, **kwargs)