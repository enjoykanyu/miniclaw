"""
MiniClaw TUI 主应用

对标 OpenClaw 的 tui.ts + tui-event-handlers.ts：
  - 主事件循环
  - 输入处理（prompt_toolkit 高级 REPL）
  - 流式响应渲染
  - Slash 命令分发
  - 活动状态机
  - 快捷键绑定
"""

from __future__ import annotations

import asyncio
import sys
import time
from enum import Enum
from typing import Optional, List, Dict, Any

from rich.console import Console
from rich.markdown import Markdown
from rich.text import Text
from rich.panel import Panel
from rich.live import Live
from rich.spinner import Spinner

from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory, FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter, Completer, Completion
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style as PtStyle
from prompt_toolkit.formatted_text import FormattedText

from tui.banner import print_banner, print_banner_line
from tui.chat_log import ChatLog
from tui.stream_assembler import StreamAssembler, StreamChunk
from tui.commands import SlashCommandRegistry, create_default_registry


class ActivityState(Enum):
    """对标 OpenClaw 的活动状态机"""
    IDLE = "idle"
    SENDING = "sending"
    STREAMING = "streaming"
    FINISHING = "finishing"
    ERROR = "error"
    ABORTED = "aborted"


class SlashCommandCompleter(Completer):
    """Slash 命令自动补全"""

    def __init__(self, registry: SlashCommandRegistry):
        self.registry = registry

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        if not text.startswith("/"):
            return

        parts = text.split(maxsplit=1)
        cmd_part = parts[0]

        # 命令名补全
        if len(parts) == 1:
            for item in self.registry.completion_items():
                if item.startswith(cmd_part):
                    cmd = self.registry.resolve(item[1:])
                    desc = cmd.description if cmd else ""
                    yield Completion(
                        item,
                        start_position=-len(cmd_part),
                        display_meta=desc,
                    )
        # 参数补全
        elif len(parts) == 2:
            cmd_name = cmd_part[1:]  # 去掉 /
            arg_completions = self.registry.arg_completions_for(cmd_name)
            arg_part = parts[1]
            for ac in arg_completions:
                if ac.startswith(arg_part):
                    yield Completion(
                        ac,
                        start_position=-len(arg_part),
                    )


class MiniClawTUI:
    """
    对标 OpenClaw 的 TUI 类

    核心职责：
    1. 管理主事件循环
    2. 处理用户输入（prompt_toolkit）
    3. 调用 AgenticLoopApp 进行对话
    4. 流式渲染响应
    5. Slash 命令分发
    6. 状态管理
    """

    def __init__(
        self,
        user_id: str = "cli",
        session_id: Optional[str] = None,
        force_think: bool = False,
        force_search: bool = False,
        verbose: bool = False,
        show_usage: bool = False,
        initial_message: Optional[str] = None,
    ):
        self.user_id = user_id
        self.session_id = session_id or f"cli-{int(time.time())}"
        self.force_think = force_think
        self.force_search = force_search
        self.verbose = verbose
        self.show_usage = show_usage
        self.initial_message = initial_message
        self.model_name = "default"
        self.think_level = "high" if force_think else "off"

        # 状态
        self._activity = ActivityState.IDLE
        self._abort_requested = False
        self._turn_count = 0
        self._app = None  # AgenticLoopApp，延迟初始化

        # Rich console
        self.console = Console()

        # ChatLog
        self.chat_log = ChatLog(self.console, verbose=verbose)

        # StreamAssembler
        self.stream_assembler = StreamAssembler()

        # 命令系统
        self.command_registry = create_default_registry(self)

        # prompt_toolkit
        self._prompt_session: Optional[PromptSession] = None

    @property
    def activity(self) -> ActivityState:
        return self._activity

    @activity.setter
    def activity(self, value: ActivityState):
        self._activity = value

    def _create_prompt_session(self) -> PromptSession:
        """创建 prompt_toolkit 会话，对标 OpenClaw 的 CustomEditor"""
        # 历史记录
        try:
            import os
            history_dir = os.path.expanduser("~/.miniclaw")
            os.makedirs(history_dir, exist_ok=True)
            history = FileHistory(os.path.join(history_dir, "chat_history"))
        except Exception:
            history = InMemoryHistory()

        # 自动补全
        completer = SlashCommandCompleter(self.command_registry)

        # 快捷键绑定
        kb = KeyBindings()

        # Ctrl+C: 清空输入 / 退出（双击）
        last_ctrl_c_time = [0.0]

        @kb.add("c-c")
        def handle_ctrl_c(event):
            buffer = event.current_buffer
            if buffer.text:
                buffer.reset()
            else:
                now = time.time()
                if now - last_ctrl_c_time[0] < 1.0:
                    # 双击 Ctrl+C 退出
                    event.app.exit(exception=EOFError())
                else:
                    last_ctrl_c_time[0] = now
                    self.console.print(
                        "[dim]再按一次 Ctrl+C 退出，或输入 /quit[/dim]"
                    )

        # 样式
        style = PtStyle.from_dict({
            "prompt": "bold cyan",
            "completion-menu.completion": "bg:#1a1a2e #e0e0e0",
            "completion-menu.completion.current": "bg:#0f3460 #ffffff",
            "completion-menu.meta": "bg:#1a1a2e #888888",
        })

        return PromptSession(
            history=history,
            auto_suggest=AutoSuggestFromHistory(),
            completer=completer,
            key_bindings=kb,
            style=style,
            multiline=False,
            mouse_support=False,
        )

    def _get_prompt_text(self) -> FormattedText:
        """对标 OpenClaw 的 prompt 显示"""
        if self._activity == ActivityState.STREAMING:
            return FormattedText([("class:prompt", "  ... ")])
        return FormattedText([("class:prompt", "  You > ")])

    async def _init_agent(self) -> None:
        """延迟初始化 AgenticLoopApp"""
        if self._app is not None:
            return
        try:
            from agent_loop.app import AgenticLoopApp
            self._app = AgenticLoopApp()
            self.console.print("[dim]Agent Loop 已初始化[/dim]")
        except Exception as e:
            self.console.print(f"[bold red]Agent 初始化失败: {e}[/bold red]")
            raise

    async def run(self) -> None:
        """
        主入口：对标 OpenClaw 的 runTui()

        1. 显示 Banner
        2. 初始化 Agent
        3. 进入主事件循环
        """
        # Banner
        try:
            terminal_width = self.console.width
            if terminal_width >= 60:
                print_banner(self.console)
            else:
                print_banner_line(self.console)
        except Exception:
            print_banner_line(self.console)

        # 初始化 Agent
        with self.console.status("[cyan]正在初始化 Agent...[/cyan]"):
            await self._init_agent()

        # 创建 prompt session
        self._prompt_session = self._create_prompt_session()

        # 如果有初始消息，先发送
        if self.initial_message:
            await self._handle_message(self.initial_message)

        # 主事件循环
        await self._main_loop()

    async def _main_loop(self) -> None:
        """对标 OpenClaw 的主事件循环"""
        while True:
            try:
                # 获取用户输入
                user_input = await self._prompt_session.prompt_async(
                    self._get_prompt_text(),
                )
                user_input = user_input.strip()

                if not user_input:
                    continue

                # 处理输入
                if user_input.startswith("/"):
                    should_exit = await self._handle_command(user_input)
                    if should_exit:
                        break
                else:
                    await self._handle_message(user_input)

            except KeyboardInterrupt:
                self.console.print("[dim]使用 /quit 或双击 Ctrl+C 退出[/dim]")
                continue
            except EOFError:
                break

        # 退出
        self._print_farewell()

    async def _handle_command(self, input_text: str) -> bool:
        """
        对标 OpenClaw 的 handleCommand

        解析 slash 命令并分发。
        返回 True 表示应该退出。
        """
        parts = input_text[1:].split(maxsplit=1)  # 去掉 /
        cmd_name = parts[0]
        cmd_args = parts[1] if len(parts) > 1 else ""

        cmd = self.command_registry.resolve(cmd_name)

        if cmd is None:
            self.console.print(f"[dim]未知命令: /{cmd_name}，输入 /help 查看帮助[/dim]")
            return False

        # /quit 和 /exit 直接退出
        if cmd.name in ("quit", "exit"):
            return True

        if cmd.handler:
            await cmd.handler(cmd_args)

        return False

    async def _handle_message(self, message: str) -> None:
        """
        对标 OpenClaw 的消息处理流程

        状态机: idle -> sending -> streaming -> finishing -> idle
        """
        if self._activity != ActivityState.IDLE:
            self.console.print("[dim]请等待当前响应完成，或使用 /abort 中止[/dim]")
            return

        self._abort_requested = False
        self._turn_count += 1

        # 渲染用户消息
        self.chat_log.add_user_message(message)

        # 状态: sending
        self._activity = ActivityState.SENDING

        try:
            # 尝试流式调用
            await self._stream_response(message)
        except Exception as e:
            self._activity = ActivityState.ERROR
            self.chat_log.add_error(f"处理请求时出现错误: {e}")
        finally:
            self._activity = ActivityState.IDLE

    async def _stream_response(self, message: str) -> None:
        """
        对标 OpenClaw 的流式响应处理

        使用 AgenticLoopApp.stream() 获取事件流，
        通过 StreamAssembler 组装内容，
        实时渲染到终端。
        """
        self._activity = ActivityState.STREAMING
        self.stream_assembler.reset()

        # 开始流式渲染
        self.chat_log.start_stream()

        # 使用 Rich Live 进行实时渲染
        live_content = Text("")
        with Live(live_content, console=self.console, refresh_per_second=8, transient=True) as live:
            try:
                async for event in self._app.stream(
                    message=message,
                    user_id=self.user_id,
                    session_id=self.session_id,
                    thread_id=f"cli-{self.user_id}-{self.session_id}",
                    force_think=self.force_think,
                    force_search=self.force_search,
                ):
                    # 检查中止
                    if self._abort_requested:
                        self._activity = ActivityState.ABORTED
                        break

                    # 处理错误事件
                    if isinstance(event, dict) and event.get("error"):
                        self.chat_log.add_error(event.get("message", "流式处理出现错误"))
                        return

                    # 组装流式内容
                    chunk = self.stream_assembler.ingest_delta(event)
                    if chunk and chunk.content:
                        live_content.append(chunk.content)

                        # 实时更新 Live 显示
                        try:
                            md = Markdown(self.stream_assembler.current_content)
                            live.update(md)
                        except Exception:
                            live.update(Text(self.stream_assembler.current_content))

                    # 工具调用事件（verbose 模式）
                    if self.verbose:
                        event_name = event.get("event", "")
                        if event_name == "on_tool_start":
                            tool_name = event.get("name", "unknown")
                            self.chat_log.add_tool_call(tool_name)
                        elif event_name == "on_tool_end":
                            tool_name = event.get("name", "unknown")
                            output = event.get("data", {}).get("output", "")
                            self.chat_log.add_tool_call(
                                tool_name, result=str(output)[:200]
                            )

            except Exception as e:
                # 流式失败，回退到同步模式
                self.console.print("[dim]流式响应失败，回退到同步模式...[/dim]")
                live.stop()
                await self._sync_response(message)
                return

        # 最终渲染
        final_chunk = self.stream_assembler.finalize()
        self.chat_log.finalize_stream(final_chunk.content)

    async def _sync_response(self, message: str) -> None:
        """同步模式回退"""
        with self.console.status("[cyan]MiniClaw 正在思考...[/cyan]"):
            response = await self._app.chat(
                message=message,
                user_id=self.user_id,
                session_id=self.session_id,
                thread_id=f"cli-{self.user_id}-{self.session_id}",
                force_think=self.force_think,
                force_search=self.force_search,
            )

        self.chat_log.add_assistant_message(response)

    def request_abort(self) -> None:
        """对标 OpenClaw 的 /abort"""
        if self._activity in (ActivityState.STREAMING, ActivityState.SENDING):
            self._abort_requested = True
            self.console.print("[dim]正在中止...[/dim]")
        else:
            self.console.print("[dim]当前没有正在运行的任务[/dim]")

    def print_help(self) -> None:
        """对标 OpenClaw 的 /help"""
        from rich.table import Table

        table = Table(title="MiniClaw TUI 命令", show_header=True, header_style="bold cyan")
        table.add_column("命令", style="cyan")
        table.add_column("别名", style="dim")
        table.add_column("说明")

        for cmd in self.command_registry.all_commands():
            aliases = ", ".join(f"/{a}" for a in cmd.aliases) if cmd.aliases else ""
            table.add_row(f"/{cmd.name}", aliases, cmd.description)

        self.console.print(table)

        # 快捷键
        self.console.print("\n[bold]快捷键:[/bold]")
        shortcuts = [
            ("Enter", "发送消息"),
            ("Ctrl+C", "清空输入 / 退出（双击）"),
            ("Ctrl+D", "退出 TUI"),
            ("Up/Down", "浏览历史"),
            ("Tab", "自动补全"),
        ]
        for key, desc in shortcuts:
            self.console.print(f"  [cyan]{key:15}[/cyan] {desc}")

        self.console.print("\n[bold]功能说明:[/bold]")
        features = [
            "Supervisor 自动路由到最合适的 Worker Agent",
            "ReAct 多步推理和工具调用",
            "自动上下文压缩和循环检测",
            "知识库检索 (RAG)",
            "Markdown 渲染和语法高亮",
            "流式响应实时显示",
        ]
        for f in features:
            self.console.print(f"  • {f}")
        self.console.print()

    def print_status(self) -> None:
        """对标 OpenClaw 的 /status"""
        from rich.table import Table

        table = Table(show_header=False, box=None)
        table.add_column(style="cyan", width=15)
        table.add_column()

        table.add_row("会话 ID", self.session_id)
        table.add_row("用户 ID", self.user_id)
        table.add_row("模型", self.model_name)
        table.add_row("思考级别", self.think_level)
        table.add_row("强制搜索", "开启" if self.force_search else "关闭")
        table.add_row("详细模式", "开启" if self.verbose else "关闭")
        table.add_row("对话轮数", str(self._turn_count))
        table.add_row("消息数", str(self.chat_log.message_count))
        table.add_row("状态", self._activity.value)

        self.console.print(Panel(table, title="MiniClaw 状态", border_style="cyan"))
        self.console.print()

    def _print_farewell(self) -> None:
        """退出告别"""
        self.console.print()
        self.console.print(
            Panel(
                Text(f"再见！共 {self._turn_count} 轮对话", style="cyan", justify="center"),
                border_style="dim",
            )
        )
        self.console.print()


async def run_tui(
    user_id: str = "cli",
    session_id: Optional[str] = None,
    force_think: bool = False,
    force_search: bool = False,
    verbose: bool = False,
    message: Optional[str] = None,
) -> None:
    """
    对标 OpenClaw 的 runTui() 入口函数

    启动 MiniClaw TUI 交互界面。
    """
    tui = MiniClawTUI(
        user_id=user_id,
        session_id=session_id,
        force_think=force_think,
        force_search=force_search,
        verbose=verbose,
        initial_message=message,
    )
    await tui.run()
