"""
ChatLog — 聊天消息渲染区

对标 OpenClaw 的 ChatLog 组件 (chat-log.ts)：
  - 用户/助手消息区分渲染
  - Markdown 渲染（代码块语法高亮）
  - 流式更新（增量渲染）
  - 工具调用显示（verbose 模式）
  - 思考过程折叠显示
"""

from __future__ import annotations

from typing import Optional, List, Dict, Any
from datetime import datetime

from rich.console import Console, Group
from rich.markdown import Markdown
from rich.text import Text
from rich.panel import Panel
from rich.rule import Rule
from rich.syntax import Syntax
from rich.live import Live
from rich.spinner import Spinner
from rich.columns import Columns


class ChatLog:
    """
    对标 OpenClaw 的 ChatLog

    职责：
    1. 渲染用户消息（简洁格式）
    2. 渲染助手消息（Markdown + 语法高亮）
    3. 流式更新助手消息（增量渲染）
    4. 工具调用显示
    5. 思考过程显示
    """

    def __init__(self, console: Console, verbose: bool = False):
        self.console = console
        self.verbose = verbose
        self._messages: List[Dict[str, Any]] = []
        self._current_stream_text: str = ""
        self._stream_live: Optional[Live] = None

    def clear(self) -> None:
        self._messages.clear()

    def add_user_message(self, content: str) -> None:
        """渲染用户消息"""
        self._messages.append({"role": "user", "content": content, "time": datetime.now()})

        # 对标 OpenClaw 的用户消息渲染：右侧对齐，accent 色
        user_text = Text()
        user_text.append("You", style="bold bright_blue")
        user_text.append(f"  {datetime.now().strftime('%H:%M')}", style="dim")
        self.console.print(user_text)
        self.console.print(content)
        self.console.print()

    def add_assistant_message(self, content: str) -> None:
        """渲染助手消息（完整，非流式）"""
        self._messages.append({"role": "assistant", "content": content, "time": datetime.now()})
        self._render_assistant_full(content)

    def _render_assistant_full(self, content: str) -> None:
        """完整渲染助手消息"""
        # 对标 OpenClaw 的助手消息渲染：左侧，Markdown 渲染
        label = Text()
        label.append("MiniClaw", style="bold bright_cyan")
        label.append(f"  {datetime.now().strftime('%H:%M')}", style="dim")
        self.console.print(label)

        # Markdown 渲染
        md = Markdown(content)
        self.console.print(md)
        self.console.print()

    def start_stream(self) -> None:
        """开始流式渲染"""
        self._current_stream_text = ""
        label = Text()
        label.append("MiniClaw", style="bold bright_cyan")
        label.append(f"  {datetime.now().strftime('%H:%M')}", style="dim")
        self.console.print(label)

    def update_stream(self, delta: str) -> None:
        """流式增量更新"""
        self._current_stream_text += delta

    def finalize_stream(self, final_text: Optional[str] = None) -> None:
        """结束流式渲染，显示最终结果"""
        text = final_text or self._current_stream_text
        self._current_stream_text = ""

        if text:
            md = Markdown(text)
            self.console.print(md)
            self._messages.append({
                "role": "assistant", "content": text, "time": datetime.now()
            })
        self.console.print()

    def add_tool_call(self, tool_name: str, args: str = "", result: str = "") -> None:
        """渲染工具调用（verbose 模式）"""
        if not self.verbose:
            return

        # 对标 OpenClaw 的工具调用渲染：折叠面板
        tool_text = Text()
        tool_text.append("  Tool: ", style="dim")
        tool_text.append(tool_name, style="bold yellow")

        if args:
            tool_text.append(f"  args: {args[:100]}", style="dim")

        self.console.print(tool_text)

        if result:
            self.console.print(Panel(
                result[:500],
                style="dim",
                padding=(0, 1),
            ))

    def add_thinking(self, content: str) -> None:
        """渲染思考过程"""
        # 对标 OpenClaw 的 thinking 渲染：折叠显示
        think_panel = Panel(
            Markdown(content) if len(content) > 100 else Text(content),
            title="[dim]Thinking[/dim]",
            border_style="dim",
            padding=(0, 1),
        )
        self.console.print(think_panel)

    def add_error(self, message: str) -> None:
        """渲染错误消息"""
        self.console.print(Panel(
            Text(message, style="bold red"),
            title="[red]Error[/red]",
            border_style="red",
            padding=(0, 1),
        ))
        self.console.print()

    def add_system(self, message: str) -> None:
        """渲染系统消息"""
        self.console.print(Text(f"  {message}", style="dim italic"))
        self.console.print()

    def show_spinner(self, message: str = "Thinking") -> None:
        """显示加载动画"""
        spinner = Spinner("dots", text=f"  {message}...", style="cyan")
        self.console.print(spinner)

    @property
    def message_count(self) -> int:
        return len(self._messages)
