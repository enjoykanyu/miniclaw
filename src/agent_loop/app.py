"""
Agentic Loop App — agentCommand 入口

核心职责：
  1. 构建 LangGraph Agentic Loop 图
  2. 提供同步/流式/事件流三种调用接口
  3. 管理模型降级（Model Fallback）
  4. 会话生命周期管理

三层架构：
  - agentCommand (入口) → AgenticLoopApp
  - runWithModelFallback (降级) → _run_with_model_fallback
  - runEmbeddedPiAgent (循环) → LangGraph StateGraph
"""

from typing import Optional, List, AsyncGenerator, Any, Dict

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from loguru import logger

from agent_loop.state import AgenticLoopState, create_loop_state, AttemptStatus
from agent_loop.graph import build_agentic_loop_graph
from agent_loop.compaction import estimate_total_tokens
from agent_loop.skills_snapshot import build_skills_snapshot
from gateway.hooks import hook_runner


class AgenticLoopApp:
    """
    Agentic Loop 应用主类

    对标 OpenClaw 的 agentCommand + runWithModelFallback：
    - chat(): 同步聊天接口
    - stream(): 流式聊天接口
    - stream_events(): 事件流接口
    - 内置模型降级逻辑
    """

    def __init__(
        self,
        checkpointer: Optional[MemorySaver] = None,
        enable_rag: bool = True,
        max_loop_iterations: int = 25,
        max_tool_calls: int = 50,
        max_context_tokens: int = 128000,
    ):
        self._checkpointer = checkpointer
        self._enable_rag = enable_rag
        self._max_loop_iterations = max_loop_iterations
        self._max_tool_calls = max_tool_calls
        self._max_context_tokens = max_context_tokens

        try:
            self.graph = build_agentic_loop_graph(
                checkpointer=checkpointer,
                enable_rag=enable_rag,
            )
            logger.info("AgenticLoopApp initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize AgenticLoopApp: {e}")
            raise

    async def chat(
        self,
        message: str,
        user_id: str = "default",
        session_id: str = "default",
        thread_id: str = "default",
        force_think: bool = False,
        force_search: bool = False,
        selected_kbs: Optional[List[str]] = None,
        kb_retrieval_mode: Optional[str] = "intent",
    ) -> str:
        """
        同步聊天接口

        对标 OpenClaw 的 agentCommand 完整流程：
        1. 解析 Session
        2. 冻结 Skills Snapshot（新增！对标 agent-command.ts L810）
        3. runWithModelFallback（含降级）
        4. 投递结果
        5. 持久化对话记录
        """
        config = {"configurable": {"thread_id": thread_id}}

        # ── Hook: before_agent_run（对标 OpenClaw 生命周期）──
        session_key = f"{user_id}:{session_id}"
        await hook_runner.run_void_hook(
            "before_agent_run",
            {"message": message, "user_id": user_id, "session_id": session_id},
            session_key=session_key,
        )

        initial_state = create_loop_state(
            user_id=user_id,
            session_id=session_id,
            max_loop_iterations=self._max_loop_iterations,
            max_tool_calls=self._max_tool_calls,
            max_context_tokens=self._max_context_tokens,
        )
        initial_state["messages"] = [HumanMessage(content=message)]
        initial_state["metadata"] = {
            "force_think": force_think,
            "force_search": force_search,
            "selected_kbs": selected_kbs,
            "kb_retrieval_mode": kb_retrieval_mode,
        }

        # ── 冻结 Skills Snapshot（对标 OpenClaw agent-command.ts L810）──
        # 在 loop 开始前一次性构建，整个 loop 期间不变。
        # 即便中途有人注册了新工具，本次 loop 依然使用起跑时的版本。
        # 这是为了防止"中途换 skill 导致语义漂移"。
        snapshot = build_skills_snapshot()
        initial_state["skills_snapshot"] = snapshot.to_dict()
        logger.info(
            f"Skills snapshot frozen: version={snapshot.version}, "
            f"tools={snapshot.tool_names}, frozen_at={snapshot.frozen_at}"
        )

        if force_search:
            search_context = await self._execute_force_search(message)
            if search_context:
                initial_state["force_search_context"] = search_context

        try:
            result = await self._run_with_model_fallback(initial_state, config)

            if result.get("loop_breaker_tripped"):
                return result.get("agent_response", "推理循环被断路器终止，请简化请求后重试。")

            if result.get("attempt_status") == AttemptStatus.FAILED.value:
                return result.get("agent_response", "处理请求时出现问题，请重试。")

            agent_response = result.get("agent_response")
            if agent_response:
                return agent_response

            messages = result.get("messages", [])
            for msg in reversed(messages):
                if isinstance(msg, AIMessage) and msg.content:
                    return msg.content

            return "抱歉，我无法处理您的请求。"

        except Exception as e:
            logger.error(f"AgenticLoopApp.chat failed: {e}", exc_info=True)
            return f"抱歉，处理请求时出现错误：{str(e)[:100]}"
        finally:
            # ── Hook: agent_end（对标 OpenClaw 生命周期）──
            await hook_runner.run_void_hook(
                "agent_end",
                {"user_id": user_id, "session_id": session_id},
                session_key=session_key,
            )

    async def stream(
        self,
        message: str,
        user_id: str = "default",
        session_id: str = "default",
        thread_id: str = "default",
        force_think: bool = False,
        force_search: bool = False,
        selected_kbs: Optional[List[str]] = None,
        kb_retrieval_mode: Optional[str] = "intent",
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式聊天接口

        对标 OpenClaw 的 subscribeEmbeddedPiSession 事件流。
        """
        config = {"configurable": {"thread_id": thread_id}}

        initial_state = create_loop_state(
            user_id=user_id,
            session_id=session_id,
            max_loop_iterations=self._max_loop_iterations,
            max_tool_calls=self._max_tool_calls,
            max_context_tokens=self._max_context_tokens,
        )
        initial_state["messages"] = [HumanMessage(content=message)]
        initial_state["metadata"] = {
            "force_think": force_think,
            "force_search": force_search,
            "selected_kbs": selected_kbs,
            "kb_retrieval_mode": kb_retrieval_mode,
        }

        # ── 冻结 Skills Snapshot ──
        snapshot = build_skills_snapshot()
        initial_state["skills_snapshot"] = snapshot.to_dict()

        if force_search:
            search_context = await self._execute_force_search(message)
            if search_context:
                initial_state["force_search_context"] = search_context

        try:
            async for event in self.graph.astream_events(
                initial_state, config, version="v2"
            ):
                yield event
        except Exception as e:
            logger.error(f"AgenticLoopApp.stream failed: {e}", exc_info=True)
            yield {
                "error": True,
                "message": "流式处理出现错误",
                "details": str(e),
            }

    async def _run_with_model_fallback(
        self,
        initial_state: AgenticLoopState,
        config: Dict[str, Any],
    ) -> AgenticLoopState:
        """
        模型降级循环

        对标 OpenClaw 的 runWithModelFallback：
        1. 尝试主模型
        2. 如果失败（Rate Limit / Auth / Context Overflow），尝试降级模型
        3. 所有候选都失败则抛出 FallbackSummaryError

        集成 API Key 轮换：遇到速率限制自动切换 Key
        """
        import copy
        from utils.api_key_rotation import (
            execute_with_api_key_rotation,
            collect_provider_api_keys,
        )

        max_retries = 2
        last_error = None
        # 使用深拷贝，避免压缩操作污染原始状态
        current_state = copy.deepcopy(initial_state)

        # 工具循环检测器是模块级全局，跨请求累积会污染后续用户，每次请求重置
        from agent_loop.nodes.tools import _loop_detector
        _loop_detector.reset()

        # ── 收集 API Keys 用于轮换 ──
        api_keys = collect_provider_api_keys()

        async def _invoke_with_key(api_key: str) -> AgenticLoopState:
            """使用指定 API Key 执行推理"""
            # 如果有 Key 且当前使用 OpenAI 兼容 provider，临时替换 Key
            if api_key:
                import os
                from config.settings import settings
                original_key = os.environ.get("OPENAI_API_KEY", "")
                original_llm_key = os.environ.get("LLM_API_KEY", "")
                try:
                    os.environ["OPENAI_API_KEY"] = api_key
                    os.environ["LLM_API_KEY"] = api_key
                    # 重置 LLM 缓存，使新 Key 生效
                    from utils.llm import reset_llm_cache
                    reset_llm_cache()
                    return await self.graph.ainvoke(current_state, config)
                finally:
                    os.environ["OPENAI_API_KEY"] = original_key
                    os.environ["LLM_API_KEY"] = original_llm_key
                    from utils.llm import reset_llm_cache
                    reset_llm_cache()
            else:
                return await self.graph.ainvoke(current_state, config)

        for attempt in range(max_retries):
            try:
                # ── 使用 API Key 轮换执行推理 ──
                result = await execute_with_api_key_rotation(
                    _invoke_with_key,
                    api_keys,
                )

                if result.get("attempt_status") == AttemptStatus.FAILED.value:
                    error_code = result.get("last_error_code", "")
                    if error_code in ("RATE_LIMITED", "CONTEXT_OVERFLOW"):
                        last_error = result.get("last_error")
                        logger.warning(
                            f"Attempt {attempt + 1} failed with {error_code}: {last_error}"
                        )

                        if error_code == "CONTEXT_OVERFLOW":
                            from agent_loop.compaction import compact_context
                            compact_result = await compact_context(current_state)
                            current_state.update(compact_result)

                        continue

                return result

            except Exception as e:
                last_error = str(e)
                logger.warning(f"Attempt {attempt + 1} exception: {e}")

                if "rate_limit" in last_error.lower() or "429" in last_error:
                    continue
                if "context" in last_error.lower():
                    continue
                raise

        logger.error(f"All model fallback attempts exhausted: {last_error}")
        return {
            **current_state,
            "attempt_status": AttemptStatus.FAILED.value,
            "last_error": last_error,
            "last_error_code": "FALLBACK_EXHAUSTED",
            "agent_response": "所有模型尝试均失败，请稍后重试。",
        }

    async def _execute_force_search(self, query: str) -> str:
        """
        程序化执行联网搜索

        对标 OpenClaw 的 preflight search：
        在 LLM 调用之前程序化执行搜索，将结果注入上下文。
        """
        import asyncio

        try:
            from config.settings import settings

            tavily_key = settings.TAVILY_API_KEY

            if tavily_key:
                from tools.tavily import _search_tavily
                result = await _search_tavily(query, 5)
                logger.info(f"Force search (Tavily) for: {query}, result length: {len(result)}")
                return result

            try:
                from tools.tavily import _search_duckduckgo
                result = await asyncio.to_thread(_search_duckduckgo, query, 5)
                logger.info(f"Force search (DuckDuckGo) for: {query}, result length: {len(result)}")
                return result
            except ImportError:
                logger.warning("DuckDuckGo not installed, force search unavailable")
                return ""

        except Exception as e:
            logger.error(f"Force search failed: {e}", exc_info=True)
            return ""
