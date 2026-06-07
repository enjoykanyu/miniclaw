"""
MiniClaw TUI — 富终端聊天界面

对标 OpenClaw 的 TUI 系统（基于 pi-tui），使用 Python 生态对等方案：
  - rich: Markdown 渲染、语法高亮、主题、进度指示
  - prompt_toolkit: 高级输入（历史、补全、多行编辑、快捷键）

架构对标：
  - OpenClaw TUI (tui.ts) → MiniClawTUI
  - OpenClaw ChatLog (chat-log.ts) → ChatLog
  - OpenClaw CustomEditor (custom-editor.ts) → PromptSession
  - OpenClaw Commands (commands.ts) → SlashCommands
  - OpenClaw StreamAssembler (tui-stream-assembler.ts) → StreamAssembler
  - OpenClaw Banner (banner.ts) → Banner
"""

from .tui_app import MiniClawTUI, run_tui

__all__ = ["MiniClawTUI", "run_tui"]
