import os, sys, subprocess

VERSION = "0.1.0"

def init_process_env():
    """标记当前进程为 openclaw 执行实例"""
    os.environ.setdefault("OPENCLAW_EXEC", "1")
    os.environ.setdefault("NO_COLOR", "0")

def _build_cli_respawn_plan():
    """检测 .env 新增变量 →TODO  config-guard 实现 ↩"""
    return None

def ensure_cli_respawn_ready() -> bool:
    """触发 CLI Respawn，新进程退出后返回 True"""
    plan = _build_cli_respawn_plan()
    if not plan:
        return False
    child = subprocess.Popen(
        [plan["command"], *plan["argv"]],
        env={**os.environ, **plan["env"]}
    )
    child.wait()
    return True

def try_handle_root_version_fast_path(argv):
    """--version → 直接输出并退出，不加载 run_main"""
    if len(argv) == 2 and argv[1] in ("--version", "-V"):
        print(f"miniclaw v{VERSION}")
        return True
    return False

async def run_main_or_root_help(argv):
    if len(argv) <= 1:
        sys.stdout.write("Use 'miniclaw --help' for usage.\n")
        return
    from cli.run_main import run_cli
    await run_cli(argv)

async def run_entry(argv=None):
    if argv is None: argv = sys.argv
    init_process_env()
    if try_handle_root_version_fast_path(argv): return
    if ensure_cli_respawn_ready(): return
    await run_main_or_root_help(argv)