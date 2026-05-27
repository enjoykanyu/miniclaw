import sys
import os
from typing import Any

# from version import VERSION


class StartupTrace:
    def __init__(self):
        import time
        self._started = time.perf_counter()

    async def measure(self, name: str, fn):
        import time
        before = time.perf_counter()
        try: return await fn()
        finally:
            elapsed = (time.perf_counter() - before) * 1000
            if os.environ.get("OPENCLAW_GATEWAY_STARTUP_TRACE"):
                total = (time.perf_counter() - self._started) * 1000
                print(f"[gateway] trace: {name} {elapsed:.1f}ms total={total:.1f}ms",
                      file=sys.stderr)


ROOT_OPTIONS = frozenset({"--no-color", "--color"})
RUN_OPTIONS = frozenset({"--port", "--bind"})


def is_gateway_run_fast_path_argv(argv):
    """完整 token 消费逻辑的 Python 复刻"""
    tokens = argv[1:]
    i = 0
    saw_gateway = False
    saw_run = False
    while i < len(tokens):
        token = tokens[i]
        if token == "--": break
        if token in ("--help", "-h", "--version", "-V"): return False
        if token in ROOT_OPTIONS: i += 1; continue
        if token == "gateway" and not saw_gateway: saw_gateway = True; i += 1; continue
        if token == "run" and saw_gateway and not saw_run: saw_run = True; i += 1; continue
        if saw_run and token in RUN_OPTIONS: i += 2; continue
        if saw_run and token.startswith("-"): return False
        if not saw_gateway: return False
        i += 1
    return saw_gateway and saw_run

def _emit_startup_banner():
    """启动横幅 →TODO  从 logo.txt 读取 ↩"""
    print("[miniclaw] Starting WebSocket Gateway...", file=sys.stderr)


def _resolve_startup_policy(argv):
    """解析端口/bind/代理 → TODO 实现 argv 解析 ↩"""
    policy = {"port": 18789, "bind": "loopback"}
    for i, arg in enumerate(argv):
        if arg == "--port" and i + 1 < len(argv):
            policy["port"] = int(argv[i + 1])
        elif arg == "--bind" and i + 1 < len(argv):
            policy["bind"] = argv[i + 1]
    return policy

def _enable_console_capture():
    """启用日志捕获 → 第2章 Phase7 实现 log-capture.py ↩"""
    pass
async def try_run_gateway_run_fast_path(
        argv: list[str],
        startup_trace: StartupTrace | None = None,
) -> bool:
    if not is_gateway_run_fast_path_argv(argv):
        return False
    _emit_startup_banner()
    print("[openclaw] Gateway fast path detected...", file=sys.stderr)
    policy = _resolve_startup_policy(argv)
    _enable_console_capture()
    from src.gateway.server import start_gateway_server
    await start_gateway_server(**policy)
    return True


def should_use_root_help_fast_path(argv: list[str]) -> bool:
    return "--help" in argv or "-h" in argv


def should_load_dotenv() -> bool:
    return os.path.exists(".env")


async def run_cli(argv=None):
    if argv is None: argv = sys.argv
    startup_trace = StartupTrace()
    if await try_run_gateway_run_fast_path(argv, startup_trace):
        return
    # ── 慢速路径（本节仅占位）──
    # 🔗 第2章实现：注册全部子命令 → command-bootstrap → 匹配执行 ↩
    print("[run_main] 慢速路径暂未实现（第2章完成）", file=sys.stderr)