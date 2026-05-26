from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Any, Callable
import importlib
import sys

def create_lazy_import_loader(module_path: str) -> Callable:
    """对应 createLazyImportLoader: 惰性模块加载"""
    _cached: Any = None
    def load():
        nonlocal _cached
        if _cached is None:
            _cached = importlib.import_module(module_path)
        return _cached
    return load

@dataclass
class CliCommandBootstrapParams:
    """对应 TypeScript 的 params 类型"""
    runtime: Any = None
    command_path: list[str] = field(default_factory=list)
    suppress_doctor_stdout: bool = False
    skip_config_guard: bool = False
    allow_invalid: bool = False
    load_plugins: bool = True
    plugin_registry: Optional[str] = None

async def ensure_cli_command_bootstrap(
        params: CliCommandBootstrapParams,
) -> None:
    """对应 ensureCliCommandBootstrap(): 命令引导"""

    # Step 1: Config Guard（配置守卫）
    if not params.skip_config_guard:
        print("[bootstrap] 检查配置就绪...", file=sys.stderr)
        # 🔗 连接点：后续实现 config_guard 后接入
        # mod = _config_guard_loader()
        # await mod.ensure_config_ready(...)
        print("[bootstrap] 配置检查通过（占位）", file=sys.stderr)

    # Step 2: 插件加载开关
    if not params.load_plugins:
        return

    # Step 3: 插件注册表加载
    # 🔗 连接点：后续实现 plugin_registry_loader 后接入
    # from .command_path_policy import resolve_cli_command_path_policy
    # from .plugin_registry_loader import ensure_cli_plugin_registry_loaded
    scope = params.plugin_registry or "full"
    print(f"[bootstrap] 加载插件注册表 scope={scope}（占位）", file=sys.stderr)