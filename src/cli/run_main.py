import sys
import os
from typing import Any

# from version import VERSION


class StartupTrace:
    def __init__(self):
        import time
        self._started = time.perf_counter()

    async def measure(self, name: str, fn) -> Any:
        import time
        before = time.perf_counter()
        try:
            result = await fn()
            return result
        finally:
            elapsed = (time.perf_counter() - before) * 1000
            if os.environ.get("OPENCLAW_GATEWAY_STARTUP_TRACE"):
                total = (time.perf_counter() - self._started) * 1000
                print(
                    f"[gateway] trace: {name} {elapsed:.1f}ms total={total:.1f}ms",
                    file=sys.stderr,
                )


def is_gateway_run_fast_path_argv(argv: list[str]) -> bool:
    return len(argv) >= 3 and argv[1] == "gateway" and argv[2] == "run"


async def try_run_gateway_run_fast_path(
        argv: list[str],
        startup_trace: StartupTrace | None = None,
) -> bool:
    if not is_gateway_run_fast_path_argv(argv):
        return False

    print("[openclaw] Gateway fast path detected...", file=sys.stderr)

    import click

    @click.group()
    def cli():
        pass

    @cli.group()
    def gateway():
        """Run, inspect, and query the WebSocket Gateway"""
        pass

    @gateway.command()
    @click.option("--port", default=18789, type=int, help="Gateway port")
    @click.option("--bind", default="loopback", help="Bind mode")
    def run(port: int, bind: str):
        """Run the WebSocket Gateway (foreground)"""
        import asyncio
        import nest_asyncio
        from gateway.server import start_gateway_server
        nest_asyncio.apply()
        asyncio.run(start_gateway_server(port=port))
        print(f"[run_main] Gateway 快速路径命中！port={port}")
        print(f"[run_main] 等待 server.py 接入...")

    cli(standalone_mode=False, args=argv[1:])
    return True


def should_use_root_help_fast_path(argv: list[str]) -> bool:
    return "--help" in argv or "-h" in argv


def should_load_dotenv() -> bool:
    return os.path.exists(".env")


async def run_cli(argv: list[str] | None = None) -> None:
    if argv is None:
        argv = sys.argv

    startup_trace = StartupTrace()

    if should_load_dotenv():
        try:
            from dotenv import load_dotenv
            load_dotenv(quiet=True)
        except ImportError:
            pass

    # if should_use_root_help_fast_path(argv):
    #     from miniclaw_bin import PRECOMPUTED_HELP
    #     sys.stdout.write(PRECOMPUTED_HELP)
    #     return

    if await try_run_gateway_run_fast_path(argv, startup_trace):
        return

    import click

    @click.group()
    # @click.version_option(version=VERSION)
    def cli():
        """OpenClaw - AI Assistant Gateway"""
        pass

    @cli.group()
    def gateway():
        """Gateway management"""
        pass

    @gateway.command()
    @click.option("--port", default=18789, type=int)
    @click.option("--bind", default="loopback")
    def run(port: int, bind: str):
        """Run the WebSocket Gateway"""
        # 🔗 连接点：下一阶段将接入 server.py
        print(f"[run_main] Gateway 命令 port={port}, bind={bind}")
        print(f"[run_main] 等待 server.py 接入...")

    @gateway.command()
    def status():
        """Check gateway status"""
        print("Gateway status: not implemented yet")

    @cli.command()
    def doctor():
        """Diagnose and fix issues"""
        print("Running diagnostics...")

    cli(args=argv[1:], standalone_mode=False)
