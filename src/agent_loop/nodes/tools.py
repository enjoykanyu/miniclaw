"""
Tool Execution Node

对标 OpenClaw 的工具执行层：
  - 策略管道 7 级过滤
  - before_tool_call Hook
  - 工具实际执行
  - after_tool_call Hook
  - tool_result 添加到对话历史

LangGraph 中 tool_execute 是 agent_reason 的后继节点，
执行完工具后回到 agent_reason 继续推理（ReAct 循环的 Act+Observe 步骤）。
"""

from typing import Dict, Any, List, Optional
from datetime import datetime

from langchain_core.messages import AIMessage, ToolMessage
from loguru import logger

from agent_loop.state import AgenticLoopState, ToolCallRecord
from agent_loop.loop_detection import LoopDetector, LoopSeverity


_loop_detector = LoopDetector()


def _extract_tool_name(tool_call: Dict[str, Any]) -> str:
    if "name" in tool_call:
        return tool_call["name"]
    if "function" in tool_call and "name" in tool_call["function"]:
        return tool_call["function"]["name"]
    return ""


def _extract_tool_args(tool_call: Dict[str, Any]) -> Dict[str, Any]:
    args = tool_call.get("args") or tool_call.get("function", {}).get("arguments", {})
    if isinstance(args, str):
        import json
        try:
            return json.loads(args)
        except (json.JSONDecodeError, TypeError):
            return {}
    return args if isinstance(args, dict) else {}


def _find_tool(tool_name: str) -> Optional[Any]:
    try:
        from tools.registry import registry
        tool = registry.get(tool_name)
        if tool:
            if hasattr(tool, "to_langchain_tool"):
                return tool.to_langchain_tool()
            if hasattr(tool, "name"):
                return tool
    except Exception:
        pass

    builtin_modules = {
        "tavily": "tools.tavily",
        "think": "tools.think",
        "get_weather": "tools.weather",
        "fetch_weather": "tools.weather",
        "get_news": "tools.news",
        "fetch_news": "tools.news",
    }

    module_path = builtin_modules.get(tool_name)
    if module_path:
        try:
            import importlib
            module = importlib.import_module(module_path)
            if hasattr(module, tool_name):
                tool = getattr(module, tool_name)
                if hasattr(tool, "name"):
                    return tool
        except Exception as e:
            logger.debug(f"Failed to load tool '{tool_name}': {e}")

    return None


async def _execute_single_tool(tool_name: str, tool_args: Dict[str, Any]) -> str:
    tool = _find_tool(tool_name)
    if not tool:
        return f"Error: Tool '{tool_name}' not found"

    try:
        if hasattr(tool, "ainvoke"):
            result = await tool.ainvoke(tool_args)
        elif hasattr(tool, "func"):
            import asyncio
            import inspect
            if inspect.iscoroutinefunction(tool.func):
                result = await tool.func(**tool_args)
            else:
                result = await asyncio.to_thread(tool.invoke, tool_args)
        else:
            result = tool.invoke(tool_args)

        if isinstance(result, str):
            return result
        if isinstance(result, dict):
            if "error" in result:
                return f"Error: {result.get('message', result.get('error', 'Unknown error'))}"
            import json
            return json.dumps(result, ensure_ascii=False, default=str)
        return str(result)

    except Exception as e:
        logger.error(f"Tool '{tool_name}' execution failed: {e}")
        return f"Error: Tool '{tool_name}' failed: {str(e)}"


async def tool_execute_node(state: AgenticLoopState) -> Dict[str, Any]:
    """
    工具执行节点

    对标 OpenClaw 的工具执行流程：
    1. 从最后一条 AI 消息中提取 tool_calls
    2. 对每个工具调用进行循环检测
    3. 执行工具
    4. 将 ToolMessage 添加到消息流
    5. 更新 tool_call_history 和计数

    执行完后回到 agent_reason 继续推理（ReAct 的 Observe 步骤）。
    """
    messages = state.get("messages", [])
    tool_call_count = state.get("tool_call_count", 0)
    loop_iteration = state.get("loop_iteration", 0)
    tool_call_history = list(state.get("tool_call_history", []))

    last_ai_message = None
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls") and msg.tool_calls:
            last_ai_message = msg
            break

    if not last_ai_message:
        logger.warning("tool_execute_node: No AI message with tool_calls found")
        return {"tool_call_count": tool_call_count}

    tool_calls = last_ai_message.tool_calls
    tool_messages: List[ToolMessage] = []
    loop_breaker_tripped = False
    loop_breaker_reason = None

    for tool_call in tool_calls:
        tool_name = _extract_tool_name(tool_call)
        tool_args = _extract_tool_args(tool_call)
        tool_call_id = tool_call.get("id", f"{tool_name}_{tool_call_count}")

        detection_result = _loop_detector.observe(tool_name, tool_args, loop_iteration)
        if detection_result.detected:
            if detection_result.severity in (LoopSeverity.CRITICAL, LoopSeverity.BREAKER):
                logger.warning(
                    f"Loop detection triggered: {detection_result.detector.value} - "
                    f"{detection_result.message}"
                )
                if detection_result.severity == LoopSeverity.BREAKER:
                    loop_breaker_tripped = True
                    loop_breaker_reason = detection_result.message
                    tool_messages.append(ToolMessage(
                        content=f"[循环检测] {detection_result.message}. {detection_result.suggestion}",
                        tool_call_id=tool_call_id,
                    ))
                    continue
                else:
                    warning_content = (
                        f"[警告] {detection_result.message}. {detection_result.suggestion}\n"
                        f"请基于已有信息给出回答。"
                    )
                    tool_messages.append(ToolMessage(
                        content=warning_content,
                        tool_call_id=tool_call_id,
                    ))
                    continue

        logger.info(f"Executing tool: {tool_name} with args: {list(tool_args.keys())}")
        result = await _execute_single_tool(tool_name, tool_args)

        max_result_len = 5000
        if len(result) > max_result_len:
            result = result[:max_result_len] + "\n...[结果已截断]"

        tool_messages.append(ToolMessage(
            content=result,
            tool_call_id=tool_call_id,
        ))

        tool_call_count += 1
        result_summary = result[:200] + "..." if len(result) > 200 else result
        tool_call_history.append(ToolCallRecord(
            tool_name=tool_name,
            args=tool_args,
            result_summary=result_summary,
            timestamp=datetime.now().isoformat(),
            iteration=loop_iteration,
        ))

    updates: Dict[str, Any] = {
        "messages": tool_messages,
        "tool_call_count": tool_call_count,
        "tool_call_history": tool_call_history,
    }

    if loop_breaker_tripped:
        updates["loop_breaker_tripped"] = True
        updates["loop_breaker_reason"] = loop_breaker_reason

    return updates
