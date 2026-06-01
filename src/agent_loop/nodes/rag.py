"""
RAG Detection & Retrieval Nodes

对标 OpenClaw 的上下文管理策略：
  - RAG 检测：判断用户请求是否需要知识库检索
  - RAG 检索：执行向量检索并注入上下文

LangGraph 中 rag_detect 是入口条件判断节点，
rag_retrieve 执行实际检索后将结果注入 state。
"""

from typing import Dict, Any, Literal

from langchain_core.messages import SystemMessage, HumanMessage
from loguru import logger

from agent_loop.state import AgenticLoopState


_RAG_DETECT_SYSTEM_PROMPT = """你是一个意图分析器，判断用户消息是否需要从知识库中检索信息。

需要检索的情况：
- 用户询问特定知识点或概念
- 用户需要参考资料或文档
- 用户的问题涉及专业领域知识
- 用户明确要求搜索知识库

不需要检索的情况：
- 日常闲聊
- 简单的天气/新闻查询
- 任务管理操作
- 已有足够上下文可以回答的问题

请只回答 "yes" 或 "no"。"""


async def rag_detect_node(state: AgenticLoopState) -> Dict[str, Any]:
    """
    RAG 检测节点

    判断用户请求是否需要知识库检索。
    对标 OpenClaw 的 5 级窗口解析策略中的意图检测层。
    """
    messages = state.get("messages", [])
    user_message = ""
    for msg in reversed(messages):
        if hasattr(msg, "type") and msg.type == "human":
            user_message = msg.content
            break

    if not user_message:
        return {"needs_rag": False}

    metadata = state.get("metadata") or {}
    selected_kbs = metadata.get("selected_kbs")
    if selected_kbs:
        logger.info(f"RAG detect: user selected KBs, forcing rag retrieval")
        return {"needs_rag": True}

    try:
        from miniclaw.utils.llm import get_fast_llm

        llm = get_fast_llm()
        detect_messages = [
            SystemMessage(content=_RAG_DETECT_SYSTEM_PROMPT),
            HumanMessage(content=user_message),
        ]
        response = await llm.ainvoke(detect_messages)
        answer = response.content.strip().lower()

        needs_rag = "yes" in answer
        logger.info(f"RAG detect: needs_rag={needs_rag} for: {user_message[:50]}")
        return {"needs_rag": needs_rag}

    except Exception as e:
        logger.error(f"RAG detection failed: {e}")
        return {"needs_rag": False}


def should_retrieve(state: AgenticLoopState) -> Literal["rag_retrieve", "skip_rag"]:
    if state.get("needs_rag"):
        return "rag_retrieve"
    return "skip_rag"


async def rag_retrieve_node(state: AgenticLoopState) -> Dict[str, Any]:
    """
    RAG 检索节点

    执行向量检索并将结果注入 state。
    对标 OpenClaw 的上下文注入策略。
    """
    messages = state.get("messages", [])
    user_message = ""
    for msg in reversed(messages):
        if hasattr(msg, "type") and msg.type == "human":
            user_message = msg.content
            break

    if not user_message:
        return {}

    try:
        from miniclaw.rag.rag_tools import rag_search
        metadata = state.get("metadata") or {}
        selected_kbs = metadata.get("selected_kbs")
        kb_retrieval_mode = metadata.get("kb_retrieval_mode", "intent")

        if selected_kbs:
            from miniclaw.rag.rag_tools import set_rag_tool_context
            set_rag_tool_context(selected_kbs=selected_kbs, kb_retrieval_mode=kb_retrieval_mode)

        try:
            result = await rag_search.ainvoke({"query": user_message, "top_k": 5})
        except Exception:
            result = rag_search.invoke({"query": user_message, "top_k": 5})

        rag_context = ""
        rag_sources = []

        if isinstance(result, str):
            rag_context = result
        elif isinstance(result, dict):
            rag_context = result.get("content", result.get("result", ""))
            rag_sources = result.get("sources", [])

        logger.info(f"RAG retrieve: got {len(rag_context)} chars context")

        return {
            "rag_context": rag_context,
            "rag_sources": rag_sources,
        }

    except Exception as e:
        logger.error(f"RAG retrieval failed: {e}")
        return {
            "rag_context": "",
            "rag_sources": [],
        }

    finally:
        try:
            from miniclaw.rag.rag_tools import clear_rag_tool_context
            clear_rag_tool_context()
        except Exception:
            pass
