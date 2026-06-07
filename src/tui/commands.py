"""
Slash 命令系统

对标 OpenClaw 的 commands.ts + tui-command-handlers.ts：
  - 命令注册与分发
  - 参数自动补全
  - 别名支持
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Callable, Awaitable, List, Dict, Any


@dataclass
class SlashCommand:
    """对标 OpenClaw 的 command 定义"""
    name: str
    description: str
    aliases: List[str] = field(default_factory=list)
    usage: str = ""
    arg_completions: Optional[Callable[[], List[str]]] = None
    handler: Optional[Callable[[str], Awaitable[None]]] = None


class SlashCommandRegistry:
    """
    对标 OpenClaw 的命令注册系统

    支持命令注册、别名映射、自动补全、命令分发。
    """

    def __init__(self):
        self._commands: Dict[str, SlashCommand] = {}
        self._aliases: Dict[str, str] = {}

    def register(self, cmd: SlashCommand) -> None:
        self._commands[cmd.name] = cmd
        for alias in cmd.aliases:
            self._aliases[alias] = cmd.name

    def resolve(self, name: str) -> Optional[SlashCommand]:
        resolved = self._aliases.get(name, name)
        return self._commands.get(resolved)

    def all_commands(self) -> List[SlashCommand]:
        return list(self._commands.values())

    def completion_items(self) -> List[str]:
        items = []
        for cmd in self._commands.values():
            items.append(f"/{cmd.name}")
            for alias in cmd.aliases:
                items.append(f"/{alias}")
        return sorted(items)

    def arg_completions_for(self, name: str) -> List[str]:
        cmd = self.resolve(name)
        if cmd and cmd.arg_completions:
            return cmd.arg_completions()
        return []


def create_default_registry(tui: "MiniClawTUI") -> SlashCommandRegistry:
    """
    创建默认命令注册表

    对标 OpenClaw 的命令体系：
    - 会话管理: /new, /reset, /session, /sessions
    - 模型与 Agent: /think, /search, /model
    - 调试: /verbose, /trace, /usage
    - 系统: /help, /quit, /exit, /abort, /status
    """
    registry = SlashCommandRegistry()

    # ── 会话管理 ──
    async def handle_new(args: str):
        tui.session_id = f"cli-{id(tui)}"
        tui.chat_log.clear()
        tui.console.print("[dim]新会话已创建[/dim]")

    async def handle_reset(args: str):
        tui.session_id = f"cli-{id(tui)}"
        tui.chat_log.clear()
        tui.console.print("[dim]会话已重置[/dim]")

    async def handle_session(args: str):
        if args.strip():
            tui.session_id = args.strip()
            tui.console.print(f"[dim]会话已切换: {tui.session_id}[/dim]")
        else:
            tui.console.print(f"[dim]当前会话: {tui.session_id}[/dim]")

    registry.register(SlashCommand(
        name="new", description="创建新会话", handler=handle_new,
    ))
    registry.register(SlashCommand(
        name="reset", description="重置当前会话", aliases=["clear"], handler=handle_reset,
    ))
    registry.register(SlashCommand(
        name="session", description="查看/切换会话", usage="[session_id]",
        handler=handle_session,
    ))

    # ── 模型与 Agent ──
    async def handle_think(args: str):
        level = args.strip().lower()
        valid_levels = ["off", "minimal", "low", "medium", "high"]
        if level in valid_levels:
            tui.think_level = level
            tui.force_think = level != "off"
            tui.console.print(f"[dim]思考级别: {level}[/dim]")
        else:
            tui.force_think = not tui.force_think
            tui.think_level = "high" if tui.force_think else "off"
            tui.console.print(f"[dim]强制思考: {'开启' if tui.force_think else '关闭'}[/dim]")

    async def handle_search(args: str):
        tui.force_search = not tui.force_search
        tui.console.print(f"[dim]强制搜索: {'开启' if tui.force_search else '关闭'}[/dim]")

    async def handle_model(args: str):
        if args.strip():
            tui.model_name = args.strip()
            tui.console.print(f"[dim]模型已切换: {tui.model_name}[/dim]")
        else:
            tui.console.print(f"[dim]当前模型: {tui.model_name}[/dim]")

    registry.register(SlashCommand(
        name="think", description="设置思考级别",
        usage="[off|minimal|low|medium|high]",
        arg_completions=lambda: ["off", "minimal", "low", "medium", "high"],
        handler=handle_think,
    ))
    registry.register(SlashCommand(
        name="search", description="切换强制搜索模式", handler=handle_search,
    ))
    registry.register(SlashCommand(
        name="model", description="查看/切换模型", usage="[model_name]",
        handler=handle_model,
    ))

    # ── 调试 ──
    async def handle_verbose(args: str):
        tui.verbose = not tui.verbose
        tui.console.print(f"[dim]详细输出: {'开启' if tui.verbose else '关闭'}[/dim]")

    async def handle_usage(args: str):
        tui.show_usage = not tui.show_usage
        tui.console.print(f"[dim]使用量显示: {'开启' if tui.show_usage else '关闭'}[/dim]")

    registry.register(SlashCommand(
        name="verbose", description="切换详细输出", aliases=["v"], handler=handle_verbose,
    ))
    registry.register(SlashCommand(
        name="usage", description="切换使用量显示", handler=handle_usage,
    ))

    # ── 系统 ──
    async def handle_help(args: str):
        tui.print_help()

    async def handle_status(args: str):
        tui.print_status()

    async def handle_abort(args: str):
        tui.request_abort()

    registry.register(SlashCommand(
        name="help", description="显示帮助", aliases=["h", "?"], handler=handle_help,
    ))
    registry.register(SlashCommand(
        name="quit", description="退出 TUI", aliases=["exit", "q"], handler=None,
    ))
    registry.register(SlashCommand(
        name="status", description="显示当前状态", handler=handle_status,
    ))
    registry.register(SlashCommand(
        name="abort", description="中止当前运行", handler=handle_abort,
    ))

    return registry
