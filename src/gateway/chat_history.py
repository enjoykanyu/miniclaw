"""
Gateway Chat History — 会话历史查询

对标 OpenClaw 的 chat.history / chat.list 方法：
  - chat.history: 读取 LangGraph MemorySaver checkpointer 中的对话历史
  - chat.list: 列出所有会话及其元数据

映射关系：
  OpenClaw chat.history → handle_chat_history()
  OpenClaw chat.list   → handle_chat_list()

REST 端点：
  GET /api/v1/chat/history?thread_id=xxx&limit=50
  GET /api/v1/chat/list
"""

import time
from typing import Optional

from loguru import logger
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage

from agent_loop.app import AgenticLoopApp, get_loop_app
from session.store import SessionStore, resolve_default_store_path


def _format_message(msg) -> dict:
    """
    将 LangChain Message 转为 OpenClaw 兼容格式

    返回格式:
    {
        "role": "user" | "assistant" | "system" | "tool",
        "content": "...",
        "timestamp": 0.0,
        "tool_calls": [...] | None,
        "tool_call_id": "..." | None,
        "name": "..." | None,
    }
    """
    role_map = {
        HumanMessage: "user",
        AIMessage: "assistant",
        SystemMessage: "system",
        ToolMessage: "tool",
    }
    role = role_map.get(type(msg), "unknown")

    result: dict = {
        "role": role,
        "content": msg.content if hasattr(msg, "content") else "",
        "timestamp": 0.0,
        "tool_calls": None,
        "tool_call_id": None,
        "name": None,
    }

    # AIMessage 的 tool_calls
    if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls") and msg.tool_calls:
        result["tool_calls"] = [
            {
                "id": tc.get("id", ""),
                "type": "function",
                "function": {
                    "name": tc.get("name", ""),
                    "arguments": tc.get("args", {}),
                },
            }
            for tc in msg.tool_calls
        ]

    # ToolMessage 的 tool_call_id 和 name
    if isinstance(msg, ToolMessage):
        result["tool_call_id"] = getattr(msg, "tool_call_id", None)
        result["name"] = getattr(msg, "name", None)

    # HumanMessage 可能有 name
    if isinstance(msg, HumanMessage):
        result["name"] = getattr(msg, "name", None)

    return result


async def handle_chat_history(params: dict, auth: dict) -> dict:
    """
    chat.history 方法处理器

    从 LangGraph checkpointer 读取指定 thread_id 的对话历史。

    请求参数:
    {
        "thread_id": "xxx",     // 必填，会话线程 ID
        "limit": 50             // 可选，返回消息数量上限，默认 50
    }

    响应:
    {
        "thread_id": "xxx",
        "messages": [...],
        "total": 10
    }
    """
    thread_id = params.get("thread_id", "")
    if not thread_id:
        return {"error": "thread_id is required", "messages": [], "total": 0}

    limit = params.get("limit", 50)
    if not isinstance(limit, int) or limit <= 0:
        limit = 50

    try:
        app = get_loop_app()
        config = {"configurable": {"thread_id": thread_id}}

        # 从 checkpointer 读取历史状态
        checkpointer = app._checkpointer
        if checkpointer is None:
            logger.warning("chat.history: no checkpointer available")
            return {
                "thread_id": thread_id,
                "messages": [],
                "total": 0,
            }

        # 获取最新的 checkpoint
        checkpoint_tuple = await checkpointer.aget_tuple(config)
        if checkpoint_tuple is None:
            return {
                "thread_id": thread_id,
                "messages": [],
                "total": 0,
            }

        # 从 checkpoint 中提取消息
        checkpoint_data = checkpoint_tuple.checkpoint
        messages = []

        if isinstance(checkpoint_data, dict):
            channel_values = checkpoint_data.get("channel_values", {})
            raw_messages = channel_values.get("messages", [])
        elif hasattr(checkpoint_data, "channel_values"):
            raw_messages = checkpoint_data.channel_values.get("messages", [])
        else:
            raw_messages = []

        # 转换消息格式
        for msg in raw_messages:
            formatted = _format_message(msg)
            messages.append(formatted)

        # 应用 limit
        if len(messages) > limit:
            messages = messages[-limit:]

        return {
            "thread_id": thread_id,
            "messages": messages,
            "total": len(messages),
        }

    except Exception as e:
        logger.error(f"chat.history failed: {e}", exc_info=True)
        return {
            "thread_id": thread_id,
            "messages": [],
            "total": 0,
            "error": str(e),
        }


async def handle_chat_list(params: dict, auth: dict) -> dict:
    """
    chat.list 方法处理器

    列出所有会话及其元数据，使用 SessionStore 读取。

    请求参数:
    {
        "agent_id": "default"   // 可选，默认 "default"
    }

    响应:
    {
        "sessions": [...],
        "total": 5
    }
    """
    import os

    agent_id = params.get("agent_id", "default")

    try:
        # 确定 workspace 目录
        workspace_dir = os.getcwd()
        store_path = resolve_default_store_path(workspace_dir, agent_id)
        store = SessionStore(store_path)
        all_sessions = store.load(skip_cache=True)

        sessions = []
        for key, entry in all_sessions.items():
            sessions.append({
                "session_key": key,
                "session_id": entry.session_id,
                "updated_at": entry.updated_at,
                "session_started_at": entry.session_started_at,
                "last_interaction_at": entry.last_interaction_at,
                "last_channel": entry.last_channel,
                "last_thread_id": entry.last_thread_id,
                "compaction_count": entry.compaction_count,
                "model_override": entry.model_override,
                "route": entry.route,
            })

        # 按最后交互时间降序排列
        sessions.sort(key=lambda s: s.get("last_interaction_at", 0), reverse=True)

        return {
            "sessions": sessions,
            "total": len(sessions),
        }

    except Exception as e:
        logger.error(f"chat.list failed: {e}", exc_info=True)
        return {
            "sessions": [],
            "total": 0,
            "error": str(e),
        }


def register_chat_methods():
    """注册 chat.* 方法到 Gateway 方法注册表"""
    from gateway.server_impl import register_method

    register_method("chat.history", handle_chat_history, required_role="user")
    register_method("chat.list", handle_chat_list, required_role="user")

    logger.info("Chat methods registered: chat.history, chat.list")
