"""
Agentic Loop Graph — LangGraph StateGraph 编排

对标 OpenClaw 三层嵌套循环架构，用 LangGraph 的 StateGraph + 条件边实现：

  主循环层 (runEmbeddedPiAgent):
    while(true) 重试/恢复 → LangGraph 的 agent_reason ↔ tool_execute 循环

  尝试层 (runEmbeddedAttempt):
    单次推理生命周期 → agent_reason 节点 + 条件路由

  事件层 (subscribeEmbeddedPiSession):
    流式响应 → LangGraph astream_events

图结构：

  rag_detect → [需要RAG] → rag_retrieve → supervisor
             → [不需要RAG] → supervisor

  supervisor → 条件边读取 next_agent → agent_reason / finish

  agent_reason → [有tool_calls] → tool_execute → agent_reason (ReAct 循环)
              → [无tool_calls + 需要继续] → supervisor (多步协作)
              → [无tool_calls + 完成] → finish → END

  compaction 作为条件节点，在 tool_execute 之后检测是否需要压缩上下文
"""

from typing import Literal, Optional, Dict, Any

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from loguru import logger

from agent_loop.state import AgenticLoopState, create_loop_state, AttemptStatus
from agent_loop.compaction import should_compact, compact_context, estimate_total_tokens
from agent_loop.nodes.supervisor import supervisor_node
from agent_loop.nodes.agent import agent_reason_node
from agent_loop.nodes.tools import tool_execute_node
from agent_loop.nodes.rag import rag_detect_node, rag_retrieve_node, should_retrieve


def _should_continue_after_reason(state: AgenticLoopState) -> Literal["tool_execute", "supervisor", "finish"]:
    if state.get("loop_breaker_tripped"):
        logger.warning("Loop breaker tripped, routing to finish")
        return "finish"

    max_iterations = state.get("max_loop_iterations", 25)
    if state.get("loop_iteration", 0) >= max_iterations:
        logger.warning(f"Max loop iterations ({max_iterations}) reached, routing to finish")
        return "finish"

    max_tool_calls = state.get("max_tool_calls", 50)
    if state.get("tool_call_count", 0) >= max_tool_calls:
        logger.warning(f"Max tool calls ({max_tool_calls}) reached, routing to finish")
        return "finish"

    messages = state.get("messages", [])
    from langchain_core.messages import AIMessage
    last_ai_msg = None
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            last_ai_msg = msg
            break

    if last_ai_msg and hasattr(last_ai_msg, "tool_calls") and last_ai_msg.tool_calls:
        return "tool_execute"

    attempt_status = state.get("attempt_status")
    if attempt_status == AttemptStatus.FAILED.value:
        retry_count = state.get("attempt_retry_count", 0)
        max_retries = state.get("max_attempt_retries", 3)
        if retry_count < max_retries:
            return "supervisor"
        return "finish"

    return "finish"


def _should_continue_after_tool(state: AgenticLoopState) -> Literal["agent_reason", "compaction", "finish"]:
    if state.get("loop_breaker_tripped"):
        return "finish"

    max_tool_calls = state.get("max_tool_calls", 50)
    if state.get("tool_call_count", 0) >= max_tool_calls:
        return "finish"

    if should_compact(state):
        return "compaction"

    return "agent_reason"


async def compaction_node(state: AgenticLoopState) -> Dict[str, Any]:
    logger.info("Compaction node triggered")
    result = await compact_context(state)
    return result


def _after_compaction(state: AgenticLoopState) -> Literal["agent_reason", "finish"]:
    if state.get("loop_breaker_tripped"):
        return "finish"

    compaction_count = state.get("compaction_count", 0)
    max_compaction = state.get("max_compaction_count", 3)
    if compaction_count >= max_compaction:
        logger.warning(f"Max compaction count ({max_compaction}) reached")
        return "finish"

    return "agent_reason"


def _route_from_supervisor(state: AgenticLoopState) -> Literal["agent_reason", "finish"]:
    """
    Supervisor 之后的路由

    supervisor_node 通过 state.next_agent 字段传递路由决策，
    条件边读取该字段决定下一步：agent_reason（执行推理）或 finish（结束）。
    不使用 Command(goto=...)，避免与条件边机制冲突。
    """
    next_agent = state.get("next_agent", "finish")
    if next_agent == "finish":
        return "finish"
    return "agent_reason"


def build_agentic_loop_graph(
    checkpointer: Optional[MemorySaver] = None,
    enable_rag: bool = True,
) -> Any:
    """
    构建 Agentic Loop 的 LangGraph StateGraph

    对标 OpenClaw 的完整 Agent Loop 架构：
    - 三层嵌套循环 → LangGraph 条件边 + 循环节点
    - 多步协作 → Worker 完成后回到 Supervisor
    - 上下文压缩 → compaction 节点
    - 循环检测 → loop_breaker 状态字段

    Args:
        checkpointer: LangGraph 检查点器，用于状态持久化
        enable_rag: 是否启用 RAG 检测节点

    Returns:
        编译后的 CompiledGraph
    """
    graph = StateGraph(AgenticLoopState)

    graph.add_node("supervisor", supervisor_node)
    graph.add_node("agent_reason", agent_reason_node)
    graph.add_node("tool_execute", tool_execute_node)
    graph.add_node("compaction", compaction_node)
    graph.add_node("finish", _finish_node)

    if enable_rag:
        graph.add_node("rag_detect", rag_detect_node)
        graph.add_node("rag_retrieve", rag_retrieve_node)

        graph.set_entry_point("rag_detect")

        graph.add_conditional_edges(
            "rag_detect",
            should_retrieve,
            {
                "rag_retrieve": "rag_retrieve",
                "skip_rag": "supervisor",
            },
        )
        graph.add_edge("rag_retrieve", "supervisor")
    else:
        graph.set_entry_point("supervisor")

    graph.add_conditional_edges(
        "supervisor",
        _route_from_supervisor,
        {
            "agent_reason": "agent_reason",
            "finish": "finish",
        },
    )

    graph.add_conditional_edges(
        "agent_reason",
        _should_continue_after_reason,
        {
            "tool_execute": "tool_execute",
            "supervisor": "supervisor",
            "finish": "finish",
        },
    )

    graph.add_conditional_edges(
        "tool_execute",
        _should_continue_after_tool,
        {
            "agent_reason": "agent_reason",
            "compaction": "compaction",
            "finish": "finish",
        },
    )

    graph.add_conditional_edges(
        "compaction",
        _after_compaction,
        {
            "agent_reason": "agent_reason",
            "finish": "finish",
        },
    )

    graph.add_edge("finish", END)

    if checkpointer is None:
        checkpointer = MemorySaver()

    compiled = graph.compile(checkpointer=checkpointer)

    logger.info("Agentic Loop graph built successfully")
    return compiled


async def _finish_node(state: AgenticLoopState) -> Dict[str, Any]:
    agent_response = state.get("agent_response", "")

    if not agent_response:
        messages = state.get("messages", [])
        from langchain_core.messages import AIMessage
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and msg.content:
                agent_response = msg.content
                break

    if not agent_response:
        agent_response = "抱歉，我无法处理您的请求。"

    return {
        "agent_response": agent_response,
        "attempt_status": AttemptStatus.COMPLETED.value,
    }
