import sys
import os
from typing import Any


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
    print("[miniclaw] Gateway fast path detected...", file=sys.stderr)
    policy = _resolve_startup_policy(argv)
    _enable_console_capture()
    from gateway.server import start_gateway_server
    from gateway.server_impl import GatewayServerOptions
    bind = policy.pop("bind", "loopback")
    opts = GatewayServerOptions(bind=bind)
    # 当用户执行了 gateway run 时，直接启动 Gateway 服务器，不加载 run_main
    await start_gateway_server(port=policy.get("port", 18789), opts=opts)
    return True


def should_use_root_help_fast_path(argv: list[str]) -> bool:
    return "--help" in argv or "-h" in argv


def should_load_dotenv() -> bool:
    return os.path.exists(".env")


# ── TUI / Chat 命令检测与解析 ──
# 对标 OpenClaw: openclaw chat → miniclaw chat

TUI_OPTIONS = frozenset({"--user-id", "--session-id", "-m", "--message"})
TUI_FLAGS = frozenset({"--think", "--search", "--verbose", "--usage"})


def is_tui_chat_argv(argv: list[str]) -> bool:
    """
    检测是否是 chat/tui 命令

    支持的调用方式（对标 OpenClaw）：
      miniclaw chat
      miniclaw chat -m "hello"
      miniclaw chat --think --search
      miniclaw chat --verbose
    """
    tokens = argv[1:]
    i = 0
    saw_chat = False

    while i < len(tokens):
        token = tokens[i]
        if token == "--":
            break
        if token in ("--help", "-h", "--version", "-V"):
            return False
        if token in ROOT_OPTIONS:
            i += 1
            continue
        if token == "chat" and not saw_chat:
            saw_chat = True
            i += 1
            continue
        if saw_chat and token in TUI_OPTIONS:
            i += 2
            continue
        if saw_chat and token in TUI_FLAGS:
            i += 1
            continue
        if saw_chat and token.startswith("-"):
            return False
        if not saw_chat:
            return False
        i += 1

    return saw_chat


def parse_tui_chat_argv(argv: list[str]) -> dict:
    """解析 chat 命令参数"""
    result = {
        "user_id": "cli",
        "session_id": None,
        "message": None,
        "force_think": False,
        "force_search": False,
        "verbose": False,
        "show_usage": False,
    }

    tokens = argv[1:]
    i = 0

    while i < len(tokens):
        token = tokens[i]

        if token == "chat":
            i += 1
            continue

        if token in ("-m", "--message") and i + 1 < len(tokens):
            result["message"] = tokens[i + 1]
            i += 2
            continue

        if token == "--user-id" and i + 1 < len(tokens):
            result["user_id"] = tokens[i + 1]
            i += 2
            continue

        if token == "--session-id" and i + 1 < len(tokens):
            result["session_id"] = tokens[i + 1]
            i += 2
            continue

        if token == "--think":
            result["force_think"] = True
            i += 1
            continue

        if token == "--search":
            result["force_search"] = True
            i += 1
            continue

        if token == "--verbose":
            result["verbose"] = True
            i += 1
            continue

        if token == "--usage":
            result["show_usage"] = True
            i += 1
            continue

        i += 1

    return result


def is_bare_root_argv(argv: list[str]) -> bool:
    """
    检测是否是裸根命令（无子命令）

    对标 OpenClaw: 直接运行 openclaw → 进入 Crestodian 交互
    miniclaw → 直接进入 TUI chat
    """
    # 只有程序名，或只有全局选项
    tokens = argv[1:]
    if not tokens:
        return True
    # 只有全局选项（如 --no-color）
    return all(t in ROOT_OPTIONS for t in tokens)


async def run_cli(argv=None):
    if argv is None: argv = sys.argv
    startup_trace = StartupTrace()

    # 1. Gateway run 快径
    if await try_run_gateway_run_fast_path(argv, startup_trace):
        return

    # 2. TUI chat 命令（对标 OpenClaw: openclaw chat）
    if is_tui_chat_argv(argv):
        params = parse_tui_chat_argv(argv)
        from tui.tui_app import run_tui
        await run_tui(**params)
        return

    # 3. 旧版 agent chat 命令（兼容）
    from cli.agent_chat import is_agent_chat_argv, parse_agent_chat_argv, run_agent_chat
    if is_agent_chat_argv(argv):
        params = parse_agent_chat_argv(argv)
        await run_agent_chat(**params)
        return

    # 4. 裸根命令 → 直接进入 TUI（对标 OpenClaw 的 Crestodian 行为）
    if is_bare_root_argv(argv):
        from tui.tui_app import run_tui
        await run_tui()
        return

    print("[run_main] 慢速路径暂未实现（第2章完成）", file=sys.stderr)
