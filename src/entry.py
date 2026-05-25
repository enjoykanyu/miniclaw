import os
import sys
import subprocess
import importlib

def init_process_env() -> None:
    """对应 entry.ts L91-98: 进程环境初始化"""
    try:
        import setproctitle
        setproctitle.setproctitle("openclaw")
    except ImportError:
        pass
    os.environ.setdefault("OPENCLAW_EXEC", "1")
    import warnings
    warnings.filterwarnings("ignore", category=DeprecationWarning)

def ensure_cli_respawn_ready() -> bool:
    """对应 entry.ts L109-140: CLI Respawn"""
    plan = _build_cli_respawn_plan()
    if not plan:
        return False
    child = subprocess.Popen(
        [plan["command"], *plan["argv"]],
        env={**os.environ, **plan["env"]},
    )
    child.wait()
    return True

def _build_cli_respawn_plan() -> dict | None:
    """检查是否需要 respawn（如 .env 文件变更）"""
    if os.environ.get("OPENCLAW_CLI_RESPAWNED"):
        return None
    dotenv_path = os.path.join(os.getcwd(), ".env")
    if not os.path.exists(dotenv_path):
        return None
    return {
        "command": sys.executable,
        "argv": sys.argv,
        "env": {"OPENCLAW_CLI_RESPAWNED": "1"},
    }

async def run_main_or_root_help(argv: list[str]) -> None:
    """对应 entry.ts L220-237: 核心分发"""
    if _try_handle_root_help_fast_path(argv):
        return
    mod = importlib.import_module(".cli.run_main", __package__)
    await mod.run_cli(argv)

def _try_handle_root_help_fast_path(argv: list[str]) -> bool:
    if len(argv) <= 1 or argv[1] in ("--help", "-h"):
        if len(argv) == 1:
            sys.stdout.write("Use 'openclaw --help' for usage.\n")
            return True
    return False

async def run_entry(argv: list[str] | None = None) -> None:
    """入口函数，由 openclaw_bin.py 调用"""
    if argv is None:
        argv = sys.argv
    init_process_env()
    if ensure_cli_respawn_ready():
        return
    await run_main_or_root_help(argv)