"""
Banner 系统

对标 OpenClaw 的 banner.ts：
  - ASCII Art 模式（Unicode 块字符）
  - 单行模式
  - 主题着色
  - TTY 检测
"""

from __future__ import annotations

import os
import sys

from rich.text import Text
from rich.console import Console
from rich.panel import Panel
from rich.align import Align


VERSION = "0.1.0"


def _is_tty() -> bool:
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def _should_show_banner() -> bool:
    if not _is_tty():
        return False
    if os.environ.get("NO_COLOR") == "1":
        return False
    return True


def _get_short_commit() -> str:
    try:
        import subprocess
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=2,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return "dev"


def print_banner(console: Console) -> None:
    """
    对标 OpenClaw 的 formatCliBannerArt

    使用 Unicode 块字符绘制 ASCII Art，配合 rich 主题着色。
    """
    if not _should_show_banner():
        return

    commit = _get_short_commit()

    # 紧凑型 ASCII Art banner，适配窄终端
    art_lines = [
        r" __  __ ___ _   _ ___ ____ _        ___        __",
        r"|  \/  |_ _| \ | |_ _/ ___| |      / \ \      / /",
        r"| |\/| || ||  \| || | |   | |     / _ \ \ /\ / / ",
        r"| |  | || || |\  || | |___| |___ / ___ \ V  V /  ",
        r"|_|  |_|___|_| \_|___\____|_____/_/   \_\_/\_/   ",
    ]

    # 着色：对标 OpenClaw 的 accentBright/accentDim/accent 主题
    styled_art = Text()
    for i, line in enumerate(art_lines):
        if i > 0:
            styled_art.append("\n")
        for ch in line:
            if ch in "_|/\\":
                styled_art.append(ch, style="bold bright_cyan")
            elif ch.isalpha() or ch.isdigit():
                styled_art.append(ch, style="bold white")
            else:
                styled_art.append(ch, style="dim")

    # 组合 banner
    banner_text = Text()
    banner_text.append(styled_art)
    banner_text.append("\n\n")
    banner_text.append("  Mini Claw", style="bold bright_cyan")
    banner_text.append(f" v{VERSION}", style="dim")
    banner_text.append(f" ({commit})", style="dim bright_black")
    banner_text.append("\n")
    banner_text.append("  Personal AI Assistant — powered by LangGraph", style="dim italic")

    console.print()
    console.print(Align.center(banner_text))
    console.print()


def print_banner_line(console: Console) -> None:
    """
    对标 OpenClaw 的 formatCliBannerLine

    单行紧凑模式，适合窄终端。
    """
    if not _should_show_banner():
        return

    commit = _get_short_commit()
    line = Text()
    line.append("Mini Claw", style="bold bright_cyan")
    line.append(f" {VERSION}", style="dim")
    line.append(f" ({commit})", style="bright_black")
    line.append(" — ", style="dim")
    line.append("Personal AI Assistant", style="italic dim")

    console.print(line)
    console.print()
