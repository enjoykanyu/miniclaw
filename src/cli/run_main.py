import sys
import click
import asyncio

def is_gateway_run_fast_path_argv(argv: list[str]) -> bool:
    """检测是否为 gateway run 快速路径"""
    return (len(argv) >= 3 and
            argv[1] == "gateway" and
            argv[2] == "run")

async def run_cli(argv: list[str] | None = None) -> None:
    """对应 runCli(): CLI 核心调度器"""
    if argv is None:
        argv = sys.argv

    # 1. 加载 .env 文件
    if _should_load_cli_dotenv():
        from dotenv import load_dotenv
        load_dotenv(quiet=True)

    # 2. 帮助快速路径
    if _should_use_root_help_fast_path(argv):
        _output_precomputed_help()
        return

    # 3. ★ Gateway 快速启动路径 ★
    if await try_run_gateway_run_fast_path(argv):
        return

    # 4. 完整程序构建
    program = _build_program()
    program(args=argv[1:])

async def try_run_gateway_run_fast_path(argv) -> bool:
    """对应 tryRunGatewayRunFastPath(): 快速启动"""
    if not is_gateway_run_fast_path_argv(argv):
        return False

    # 仅加载 gateway run 所需的最小依赖
    @click.group()
    def cli():
        """OpenClaw - AI Assistant Gateway"""
        pass

    @cli.group()
    def gateway():
        """Gateway management"""
        pass

    @gateway.command()
    @click.option("--port", default=18789, type=int)
    def run(port: int):
        """Run the WebSocket Gateway"""
        # 🔗 连接点：下一阶段将接入 server.py
        # from ..gateway.server import start_gateway_server
        # asyncio.run(start_gateway_server(port=port))
        print(f"[run_main] Gateway 快速路径命中！port={port}")
        print(f"[run_main] 等待 server.py 接入...")

    cli(args=argv[1:])
    return True

def _should_load_cli_dotenv() -> bool:
    import os
    return os.path.exists(".env")

def _should_use_root_help_fast_path(argv: list[str]) -> bool:
    return "--help" in argv or "-h" in argv

def _output_precomputed_help() -> None:
    sys.stdout.write("Usage: openclaw [command] [options]\n\n"
                     "Commands:\n  gateway  Gateway management\n")

def _build_program():
    """构建完整 CLI 程序（所有子命令）"""
    @click.group()
    def program():
        """OpenClaw - AI Assistant Gateway"""
        pass

    @program.group()
    def gateway():
        """Gateway management"""
        pass

    @gateway.command()
    def status():
        """Check gateway status"""
        print("Gateway status: not implemented yet")

    @program.command()
    def doctor():
        """Diagnose and fix issues"""
        print("Running diagnostics...")

    return program