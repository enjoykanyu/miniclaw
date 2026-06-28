"""
Agent Reasoning Node

对标 OpenClaw 的 runEmbeddedAttempt：
  - 组装上下文、加载工具、注入系统提示
  - 调用 LLM 进行推理
  - 判断是否需要工具调用

这是 Agentic Loop 的核心节点，实现 ReAct 模式的 Reason 步骤。
LangGraph 中通过条件边决定下一步：tool_execute / supervisor / finish

改造要点（Skills Snapshot 冻结）：
  - 旧方式：每次 agent_reason_node 调用时实时扫描工具 → 可能中途变
  - 新方式：从 state.skills_snapshot 读取冻结的工具列表 → 整个 loop 不变
  - 对标 OpenClaw: agent-command.ts L810 构建 snapshot → L1373 传入 runAgentAttempt
"""

from typing import Dict, Any, List, Optional

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from loguru import logger

from agent_loop.state import AgenticLoopState
from agent_loop.loop_detection import LoopDetector, LoopSeverity


def _get_agent_system_prompt(agent_name: str, state: AgenticLoopState) -> str:
    base_prompts = {
        "learning": "你是学习规划助手，帮助制定学习计划、追踪进度、安排复习。你可以使用工具来完成具体操作。",
        "task": "你是任务管理助手，管理TODO清单、创建任务、生成每日报告。你可以使用工具来完成具体操作。",
        "info": "你是信息获取助手，查询天气、推送新闻、知识问答。你可以使用工具来完成具体操作。",
        "health": "你是健康提醒助手，定时提醒休息、管理作息、提供健康建议。你可以使用工具来完成具体操作。",
        "data": "你是数据处理助手，操作Excel表格、数据分析。你可以使用工具来完成具体操作。",
        "chat": "你是日常聊天助手，处理一般对话和引导用户使用功能。",
        "supervisor": "你是协调者，负责分析用户请求并决定由哪个专业助手处理。",
    }
    prompt = base_prompts.get(agent_name, f"你是 {agent_name} 助手。")

    rag_context = state.get("rag_context")
    if rag_context:
        prompt += f"\n\n【知识库检索结果】\n{rag_context}\n你可以参考以上知识库内容回答用户问题。"

    force_search_context = state.get("force_search_context")
    if force_search_context:
        prompt += f"\n\n【联网搜索结果】\n{force_search_context}\n请基于以上搜索结果回答用户问题。"

    metadata = state.get("metadata") or {}
    if metadata.get("force_think"):
        prompt += "\n\n【强制要求】请先使用 think 工具进行深度思考，然后再给出回答。"
    if metadata.get("force_search") and not force_search_context:
        prompt += "\n\n【强制要求】请使用 tavily 工具进行联网搜索，然后基于搜索结果回答。"

    loop_iteration = state.get("loop_iteration", 0)
    if loop_iteration > 10:
        prompt += "\n\n【注意】当前推理已进行多轮，请尽快总结并给出最终回答。"
    if loop_iteration > 20:
        prompt += "\n\n【紧急】推理轮次已接近上限，请立即给出当前最佳答案。"

    return prompt


# 缓存已反序列化的 SkillsSnapshot，避免每轮循环重复 from_dict 开销
_snapshot_cache: dict[str, Any] = {}


def _get_tools_from_snapshot(state: AgenticLoopState) -> List:
    """
    从冻结的 Skills Snapshot 中加载工具

    对标 OpenClaw: agent-command.ts L1373 skillsSnapshot 传入 runAgentAttempt

    苏格拉底式提问：为什么从 snapshot 加载而非实时扫描？
    → 因为 snapshot 是在 loop 开始前冻结的，保证整个 loop 期间工具不变。
      如果实时扫描，中途注册的新工具会"悄悄"出现在 LLM 的工具列表中，
      但 LLM 之前的决策是基于旧工具列表做的 → 语义漂移。

    流程：
    1. 从 state 中读取 skills_snapshot（dict）
    2. 反序列化为 SkillsSnapshot 对象（带缓存，避免每轮重复反序列化）
    3. 只加载 snapshot 中声明的工具（tool_names）
    4. 如果 snapshot 不存在，fallback 到实时扫描（兼容旧逻辑）
    """
    from agent_loop.skills_snapshot import SkillsSnapshot

    snapshot_dict = state.get("skills_snapshot")
    if not snapshot_dict:
        # Fallback：没有 snapshot 时实时扫描（兼容旧逻辑）
        logger.warning("No skills_snapshot in state, falling back to real-time scan")
        current_agent = state.get("current_agent", "chat")
        tools, _ = _get_tools_for_agent_legacy(current_agent)
        return tools

    # 使用 (version, tool_names) 作为缓存键：仅 version 在不同 agent 间会冲突，
    # 加上 tool_names 才能区分不同 agent 的 snapshot，避免加载到错误工具集
    cache_key = (
        str(snapshot_dict.get("version", "")),
        tuple(snapshot_dict.get("tool_names", []) or []),
    )
    cached = _snapshot_cache.get(cache_key)
    if cached is not None:
        snapshot = cached
    else:
        snapshot = SkillsSnapshot.from_dict(snapshot_dict)
        _snapshot_cache.clear()  # 只保留最新版本
        _snapshot_cache[cache_key] = snapshot

    tools = []
    for tool_name in snapshot.tool_names:
        tool = _try_load_tool(tool_name)
        if tool:
            tools.append(tool)

    logger.debug(
        f"Loaded {len(tools)} tools from snapshot "
        f"(version={snapshot.version}, frozen_at={snapshot.frozen_at})"
    )
    return tools


def _get_tools_for_agent_legacy(agent_name: str) -> List:
    tool_map = {
        "learning": ["think"],
        "task": ["think"],
        "info": ["get_weather", "get_news", "think"],
        "health": ["think"],
        "data": ["think"],
        "chat": ["think"],
    }
    tool_names = tool_map.get(agent_name, [])

    tools = []
    for name in tool_names:
        tool = _try_load_tool(name)
        if tool:
            tools.append(tool)

    metadata_overrides = {}
    return tools, metadata_overrides


def _try_load_tool(tool_name: str) -> Optional[Any]:
    try:
        from tools.registry import registry
        tool = registry.get(tool_name)
        if tool and hasattr(tool, "to_langchain_tool"):
            return tool.to_langchain_tool()
        if tool and hasattr(tool, "name"):
            return tool
    except Exception:
        pass

    builtin_modules = {
        "tavily": "tools.tavily",
        "think": "tools.think",
        "get_weather": "tools.weather",
        "get_news": "tools.news",
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


async def agent_reason_node(state: AgenticLoopState) -> Dict[str, Any]:
    """
    Agent 推理节点

    对标 OpenClaw 的 runEmbeddedAttempt：
    1. 组装上下文（系统提示 + 对话历史 + 工具）
    2. 调用 LLM 进行推理
    3. 返回推理结果（含可能的工具调用）

    这是 ReAct 循环的 Reason 步骤。
    如果 LLM 返回 tool_calls，条件边会路由到 tool_execute。
    如果 LLM 返回最终回答，条件边会路由到 finish 或 supervisor。
    """
    from utils.llm import get_smart_llm

    current_agent = state.get("current_agent", "chat")
    loop_iteration = state.get("loop_iteration", 0) + 1

    logger.info(f"AgentReason[{current_agent}] iteration={loop_iteration}")

    system_prompt = _get_agent_system_prompt(current_agent, state)

    # ── 从冻结的 Snapshot 加载工具（改造核心！）──
    # 旧方式: tools, _ = _get_tools_for_agent(current_agent)
    #   → 每次 ReAct 循环都重新扫描，可能中途变
    # 新方式: tools = _get_tools_from_snapshot(state)
    #   → 从 state 中的 snapshot 读取，整个 loop 不变
    tools = _get_tools_from_snapshot(state)

    # 注入 snapshot 的 prompt 到系统提示（对标 OpenClaw skillsSnapshot.prompt）
    # 复用 _get_tools_from_snapshot 中的缓存，避免重复反序列化
    snapshot_dict = state.get("skills_snapshot")
    if snapshot_dict:
        cache_key = str(snapshot_dict.get("version", ""))
        cached_snapshot = _snapshot_cache.get(cache_key)
        if cached_snapshot and cached_snapshot.prompt:
            system_prompt += f"\n\n{cached_snapshot.prompt}"

    metadata = state.get("metadata") or {}
    if metadata.get("force_think"):
        think_tool = _try_load_tool("think")
        if think_tool and not any(t.name == "think" if hasattr(t, "name") else False for t in tools):
            tools.append(think_tool)
    if metadata.get("force_search") and not state.get("force_search_context"):
        tavily_tool = _try_load_tool("tavily")
        if tavily_tool and not any(t.name == "tavily" if hasattr(t, "name") else False for t in tools):
            tools.append(tavily_tool)

    try:
        from mcp.tools import mcp_tool_registry
        from langchain_core.tools import BaseTool
        mcp_tools = mcp_tool_registry.get_all_tools()
        valid_mcp = [t for t in mcp_tools if isinstance(t, BaseTool)]
        if len(valid_mcp) < len(mcp_tools):
            logger.warning(
                f"Skipped {len(mcp_tools) - len(valid_mcp)} non-LangChain MCP tools "
                f"(MCPToolProxy is a stub, not bindable)"
            )
        tools.extend(valid_mcp)
    except Exception as e:
        logger.warning(f"MCP tools load failed: {e}")

    messages = list(state.get("messages", []))
    full_messages = [SystemMessage(content=system_prompt)] + messages

    try:
        llm = get_smart_llm()

        if tools:
            llm_with_tools = llm.bind_tools(tools)
            response = await llm_with_tools.ainvoke(full_messages)
        else:
            response = await llm.ainvoke(full_messages)

        has_tool_calls = (
            hasattr(response, "tool_calls") and
            response.tool_calls and
            len(response.tool_calls) > 0
        )

        if has_tool_calls:
            logger.info(
                f"AgentReason[{current_agent}] LLM requests {len(response.tool_calls)} tool calls: "
                f"{[tc.get('name', tc.get('function', {}).get('name', '?')) for tc in response.tool_calls]}"
            )

        updates: Dict[str, Any] = {
            "loop_iteration": loop_iteration,
            "attempt_status": "running",
            "messages": [response],
        }

        if not has_tool_calls:
            response_content = getattr(response, "content", "") or ""
            updates["agent_response"] = response_content

        return updates

    except Exception as e:
        logger.error(f"AgentReason[{current_agent}] LLM call failed: {e}")

        error_msg = str(e)
        error_code = "LLM_ERROR"

        if "rate_limit" in error_msg.lower() or "429" in error_msg:
            error_code = "RATE_LIMITED"
        elif "context" in error_msg.lower() and "overflow" in error_msg.lower():
            error_code = "CONTEXT_OVERFLOW"
        elif "timeout" in error_msg.lower():
            error_code = "TIMEOUT"

        from langchain_core.messages import AIMessage
        fallback_content = "抱歉，处理请求时遇到了问题，请稍后重试。"

        return {
            "loop_iteration": loop_iteration,
            "attempt_status": "failed",
            "last_error": error_msg,
            "last_error_code": error_code,
            "messages": [AIMessage(content=fallback_content)],
            "agent_response": fallback_content,
        }
