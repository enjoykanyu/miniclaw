# =============================
# miniclaw_bin.py — Python 版 "openclaw.mjs"
# 职责：版本守卫 + 帮助快径 + 导入入口
# =============================
import sys
import os

MIN_PYTHON = (3, 11)

def _ensure_src_on_path():
    src_dir = os.path.dirname(os.path.abspath(__file__))
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

def ensure_supported_python_version():
    if sys.version_info[:2] < MIN_PYTHON:
        print(f"需要 Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+", file=sys.stderr)
        sys.exit(1)

def is_bare_root_help_invocation(argv):
    return len(argv) == 2 and argv[1] in ("--help", "-h")

def should_defer_root_help_to_runtime_entry():
    """有插件时延迟帮助输出 → 第2章 Phase3 实现 ↩"""
    return False

def try_output_help_fast_path(argv):
    """帮助快径：满足条件则输出预计算帮助并返回 True"""
    if not is_bare_root_help_invocation(argv):
        return False
    if should_defer_root_help_to_runtime_entry():
        return False
    print("Usage: miniclaw [command] [options]")
    print("  gateway run    Start the WebSocket Gateway")
    return True

def try_output_version_fast_path(argv):
    """版本快径：对应 entry.ts 的 tryHandleRootVersionFastPath"""
    if len(argv) == 2 and argv[1] in ("--version", "-V"):
        print("miniclaw v0.1.0")
        return True
    return False

def main():
    ensure_supported_python_version()
    _ensure_src_on_path()
    argv = sys.argv
    if try_output_help_fast_path(argv): return
    if try_output_version_fast_path(argv): return
    import asyncio
    from entry import run_entry
    asyncio.run(run_entry(argv))

if __name__ == "__main__":
    main()