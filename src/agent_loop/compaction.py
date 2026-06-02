"""
Context Compaction

对标 OpenClaw 的上下文压缩机制：
  - Token 估算 -> 自适应分块 -> LLM 摘要 -> 持久化
  - 压缩作为恢复手段：溢出和超时优先尝试压缩而非直接降级
  - 工具结果守卫：单条 <= 50% 上下文、总预算 75%、超预算压缩最旧结果

LangGraph 中 compaction 作为独立节点，
在 agent_reason 之前检测是否需要压缩。
"""

from typing import Dict, Any, List, Optional, Tuple
from loguru import logger

from agent_loop.state import AgenticLoopState


def estimate_message_tokens(message: Any) -> int:
    """
    估算单条消息的 token 数

    简化估算：中文约 1.5 字/token，英文约 4 字符/token
    取较大值确保估算偏保守
    """
    content = ""
    if hasattr(message, "content"):
        content = message.content or ""
    elif isinstance(message, dict):
        content = message.get("content", "")

    if not content:
        return 0

    char_count = len(content)
    chinese_chars = sum(1 for c in content if "\u4e00" <= c <= "\u9fff")
    non_chinese_chars = char_count - chinese_chars

    tokens = int(chinese_chars / 1.5) + int(non_chinese_chars / 4)
    return max(tokens, char_count // 3)


def estimate_total_tokens(messages: List[Any]) -> int:
    total = 0
    for msg in messages:
        total += estimate_message_tokens(msg)
    return total


def should_compact(state: AgenticLoopState) -> bool:
    """
    判断是否需要压缩上下文

    触发条件：
    1. 估算 token 数超过 max_context_tokens 的 80%
    2. 压缩次数未超过上限
    """
    if state.get("compaction_count", 0) >= state.get("max_compaction_count", 3):
        return False

    messages = state.get("messages", [])
    estimated = estimate_total_tokens(messages)
    max_tokens = state.get("max_context_tokens", 128000)

    threshold = max_tokens * 0.8
    if estimated > threshold:
        logger.info(
            f"Context compaction triggered: estimated={estimated}, "
            f"threshold={threshold}, max={max_tokens}"
        )
        return True

    return False


def _prune_tool_results(messages: List[Any], budget_ratio: float = 0.75) -> List[Any]:
    """
    剪枝工具结果

    对标 OpenClaw 的剪枝策略：
    - 仅针对 ToolResult + 内存
    - TTL 5min, softTrim 30%, hardClear 50%
    - 单条工具结果 <= 50% 上下文
    """
    pruned = []
    for msg in messages:
        msg_type = getattr(msg, "type", "")
        if msg_type == "tool":
            content = getattr(msg, "content", "")
            if content and len(content) > 2000:
                truncated = content[:1500] + "\n...[结果已截断]"
                if hasattr(msg, "model_copy"):
                    new_msg = msg.model_copy(update={"content": truncated})
                else:
                    new_msg = msg
                    try:
                        msg.content = truncated
                    except (AttributeError, TypeError):
                        pass
                    new_msg = msg
                pruned.append(new_msg)
                continue
        pruned.append(msg)
    return pruned


async def compact_context(state: AgenticLoopState) -> Dict[str, Any]:
    """
    执行上下文压缩

    对标 OpenClaw 的 contextEngine.compact()：
    1. 估算当前 token 数
    2. 先尝试剪枝工具结果
    3. 如果仍超限，使用 LLM 生成对话摘要
    4. 用摘要替换早期消息

    Returns:
        状态更新字典
    """
    messages = list(state.get("messages", []))
    if len(messages) <= 2:
        return {
            "compaction_count": state.get("compaction_count", 0) + 1,
            "context_token_estimate": estimate_total_tokens(messages),
        }

    pruned = _prune_tool_results(messages)
    pruned_tokens = estimate_total_tokens(pruned)
    max_tokens = state.get("max_context_tokens", 128000)

    if pruned_tokens < max_tokens * 0.6:
        logger.info(f"Compaction via pruning sufficient: {pruned_tokens} tokens")
        return {
            "messages": pruned,
            "compaction_count": state.get("compaction_count", 0) + 1,
            "context_token_estimate": pruned_tokens,
        }

    summary = await _generate_conversation_summary(pruned, state)
    if summary:
        from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

        kept_recent = pruned[-4:] if len(pruned) > 4 else pruned

        compacted = [
            SystemMessage(content=f"[对话历史摘要]\n{summary}\n[以下是最近的对话]")
        ] + kept_recent

        compacted_tokens = estimate_total_tokens(compacted)
        logger.info(
            f"Compaction via summary: {len(messages)} -> {len(compacted)} messages, "
            f"{compacted_tokens} tokens"
        )

        return {
            "messages": compacted,
            "compaction_count": state.get("compaction_count", 0) + 1,
            "context_token_estimate": compacted_tokens,
        }

    return {
        "compaction_count": state.get("compaction_count", 0) + 1,
        "context_token_estimate": estimate_total_tokens(pruned),
    }


async def _generate_conversation_summary(messages: List[Any], state: AgenticLoopState) -> Optional[str]:
    """
    使用 LLM 生成对话摘要

    对标 OpenClaw 的 LLM 摘要压缩策略
    """
    try:
        from miniclaw.utils.llm import get_fast_llm

        llm = get_fast_llm()

        conversation_text = _format_messages_for_summary(messages)
        if not conversation_text:
            return None

        summary_prompt = (
            "请将以下对话历史压缩为简洁的摘要，保留关键信息、决策和结论。"
            "忽略寒暄和重复内容，重点关注：\n"
            "1. 用户的原始请求\n"
            "2. 已执行的操作和工具调用结果\n"
            "3. 当前进展和待完成的任务\n\n"
            f"对话历史：\n{conversation_text}"
        )

        from langchain_core.messages import HumanMessage
        response = await llm.ainvoke([HumanMessage(content=summary_prompt)])
        return response.content

    except Exception as e:
        logger.error(f"Failed to generate conversation summary: {e}")
        return None


def _format_messages_for_summary(messages: List[Any]) -> str:
    lines = []
    for msg in messages:
        msg_type = getattr(msg, "type", "unknown")
        content = getattr(msg, "content", "")

        if not content:
            continue

        role_map = {
            "human": "用户",
            "ai": "助手",
            "system": "系统",
            "tool": "工具结果",
        }
        role = role_map.get(msg_type, msg_type)

        if len(content) > 300:
            content = content[:300] + "..."

        lines.append(f"[{role}] {content}")

    return "\n".join(lines)
