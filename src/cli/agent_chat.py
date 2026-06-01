"""
CLI Agent Chat Command

对标 OpenClaw 的 CLI agent 交互模式：
  - miniclaw agent chat: 启动交互式 Agentic Loop 会话
  - miniclaw agent chat --message "xxx": 单次消息模式
  - 支持流式输出和强制工具注入
"""

import sys
import asyncio
from typing import Optional

from loguru import logger


async def run_agent_chat(
    message: Optional[str] = None,
    user_id: str = "cli",
    session_id: str = "cli-session",
    force_think: bool = False,
    force_search: bool = False,
    interactive: bool = True,
) -> None:
    """
    执行 Agent Chat 命令

    对标 OpenClaw 的 CLI agent 交互：
    - 单次模式: miniclaw agent chat --message "今天天气怎么样"
    - 交互模式: miniclaw agent chat（进入 REPL）
    """
    try:
        from agent_loop.app import AgenticLoopApp

        app = AgenticLoopApp()
        print("[agent] Agentic Loop 已初始化", file=sys.stderr)

    except Exception as e:
        print(f"[agent] 初始化失败: {e}", file=sys.stderr)
        return

    if message:
        await _single_message_mode(app, message, user_id, session_id, force_think, force_search)
    elif interactive:
        await _interactive_mode(app, user_id, session_id, force_think, force_search)
    else:
        print("[agent] 请提供 --message 或使用交互模式", file=sys.stderr)


async def _single_message_mode(
    app,
    message: str,
    user_id: str,
    session_id: str,
    force_think: bool,
    force_search: bool,
) -> None:
    print(f"\n👤 你: {message}")
    print("🤖 助手: ", end="", flush=True)

    try:
        response = await app.chat(
            message=message,
            user_id=user_id,
            session_id=session_id,
            thread_id=f"cli-{user_id}-{session_id}",
            force_think=force_think,
            force_search=force_search,
        )
        print(response)
    except Exception as e:
        print(f"\n[错误] {e}", file=sys.stderr)


async def _interactive_mode(
    app,
    user_id: str,
    session_id: str,
    force_think: bool,
    force_search: bool,
) -> None:
    print("\n=== MiniClaw Agent Chat ===")
    print("输入消息开始对话，输入 /quit 退出，/help 查看帮助\n")

    turn_count = 0

    while True:
        try:
            user_input = input("👤 你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[agent] 再见！")
            break

        if not user_input:
            continue

        if user_input == "/quit":
            print("[agent] 再见！")
            break

        if user_input == "/help":
            _print_help()
            continue

        if user_input == "/think":
            force_think = not force_think
            print(f"[agent] 强制思考: {'开启' if force_think else '关闭'}")
            continue

        if user_input == "/search":
            force_search = not force_search
            print(f"[agent] 强制搜索: {'开启' if force_search else '关闭'}")
            continue

        if user_input.startswith("/session"):
            parts = user_input.split(maxsplit=1)
            if len(parts) > 1:
                session_id = parts[1].strip()
                print(f"[agent] 会话已切换: {session_id}")
            else:
                print(f"[agent] 当前会话: {session_id}")
            continue

        turn_count += 1
        print("🤖 助手: ", end="", flush=True)

        try:
            response = await app.chat(
                message=user_input,
                user_id=user_id,
                session_id=session_id,
                thread_id=f"cli-{user_id}-{session_id}",
                force_think=force_think,
                force_search=force_search,
            )
            print(response)
        except Exception as e:
            print(f"\n[错误] {e}", file=sys.stderr)

        print()

    print(f"\n[agent] 会话结束，共 {turn_count} 轮对话")


def _print_help():
    print("""
可用命令:
  /quit      退出交互模式
  /help      显示帮助
  /think     切换强制思考模式
  /search    切换强制搜索模式
  /session   查看/切换会话 ID

功能说明:
  - Supervisor 自动路由到最合适的 Worker Agent
  - 支持 ReAct 多步推理和工具调用
  - 自动上下文压缩和循环检测
  - 支持知识库检索 (RAG)
""")


def is_agent_chat_argv(argv: list[str]) -> bool:
    """判断是否是 agent chat 命令"""
    tokens = argv[1:]
    i = 0
    saw_agent = False
    saw_chat = False

    while i < len(tokens):
        token = tokens[i]
        if token == "--":
            break
        if token in ("--help", "-h", "--version", "-V"):
            return False
        if token == "agent" and not saw_agent:
            saw_agent = True
            i += 1
            continue
        if token == "chat" and saw_agent and not saw_chat:
            saw_chat = True
            i += 1
            continue
        if saw_chat and token in ("--message", "-m", "--user-id", "--session-id"):
            i += 2
            continue
        if saw_chat and token in ("--think", "--search"):
            i += 1
            continue
        if saw_chat and token.startswith("-"):
            return False
        if not saw_agent:
            return False
        i += 1

    return saw_agent and saw_chat


def parse_agent_chat_argv(argv: list[str]) -> dict:
    """解析 agent chat 命令参数"""
    result = {
        "message": None,
        "user_id": "cli",
        "session_id": "cli-session",
        "force_think": False,
        "force_search": False,
        "interactive": True,
    }

    tokens = argv[1:]
    i = 0

    while i < len(tokens):
        token = tokens[i]

        if token in ("agent", "chat"):
            i += 1
            continue

        if token in ("--message", "-m") and i + 1 < len(tokens):
            result["message"] = tokens[i + 1]
            result["interactive"] = False
            i += 2
            continue

        if token == "--user-id" and i + 1 < len(tokens):
            result["user_id"] = tokens[i + 1]
            i += 2
            continue

        if token == "--session-id" and i + 1 < len(tokens):
            result["session_id"] = tokens[i + 1]
            i += 2
            continue

        if token == "--think":
            result["force_think"] = True
            i += 1
            continue

        if token == "--search":
            result["force_search"] = True
            i += 1
            continue

        i += 1

    return result
