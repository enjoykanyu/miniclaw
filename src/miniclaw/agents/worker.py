"""
MiniClaw Worker Agent Base Class
基于 LangGraph 官方 Worker Agent 模式实现

Worker Agent 是被 Supervisor 调用的专业智能体
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Callable

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.prebuilt import create_react_agent
from langgraph.types import Command

from miniclaw.core.state import MiniClawState
from miniclaw.utils.llm import get_llm, get_smart_llm
from miniclaw.mcp.tools import mcp_tool_registry


class BaseWorker(ABC):
    """
    Worker Agent 基类

    特性：
    1. 被 Supervisor 调用执行特定任务
    2. 可以访问共享的 State
    3. 返回 Command 以便 Supervisor 继续决策
    4. 支持工具调用和 ReAct 模式
    5. 支持强制注入 think 和 trail 工具
    """

    name: str = "worker_agent"
    description: str = "Worker agent base class"

    def __init__(
        self,
        llm: Optional[BaseChatModel] = None,
        tools: Optional[List[BaseTool]] = None,
        use_react: bool = False,
        max_iterations: int = 5,
    ):
        self._llm = llm
        self._base_tools = tools or []
        self._use_react = use_react
        self._max_iterations = max_iterations

        # 强制注入的工具会在 execute 时动态添加
        self._force_tools: List[BaseTool] = []

    def _build_tool_map(self) -> Dict[str, Callable]:
        """构建工具映射表，包含基础工具和强制注入工具"""
        all_tools = list(self._base_tools) + list(self._force_tools)
        return {tool.name: tool for tool in all_tools}

    def _init_react_agent(self, extra_tools: Optional[List[BaseTool]] = None) -> None:
        """初始化 ReAct Agent，支持动态工具注入（含 MCP 工具）"""
        system_prompt = self._get_system_prompt()
        all_tools = list(self._base_tools)
        # 注入 MCP 工具
        all_tools.extend(self._get_mcp_tools())
        if extra_tools:
            all_tools.extend(extra_tools)

        self._agent_executor = create_react_agent(
            model=self.llm,
            tools=all_tools,
            state_modifier=system_prompt,
        )

    def _get_system_prompt(self) -> str:
        """获取系统提示词 - 子类可覆盖"""
        return f"你是 {self.name}，{self.description}"

    @property
    def llm(self) -> BaseChatModel:
        if self._llm is None:
            self._llm = get_smart_llm()
        return self._llm

    def get_tools(self) -> List[BaseTool]:
        """获取工具列表，包括本地工具、MCP 工具和强制注入工具"""
        tools = list(self._base_tools)
        tools.extend(self._get_mcp_tools())
        tools.extend(self._force_tools)
        return tools

    def _get_mcp_tools(self) -> List[BaseTool]:
        """获取 MCP 远程工具列表"""
        try:
            return mcp_tool_registry.get_all_tools()
        except Exception:
            return []

    def bind_tools(self, extra_tools: Optional[List[BaseTool]] = None) -> Any:
        all_tools = list(self._base_tools)
        # 注入 MCP 工具
        all_tools.extend(self._get_mcp_tools())
        if extra_tools:
            all_tools.extend(extra_tools)
        if all_tools:
            return self.llm.bind_tools(all_tools)
        return self.llm

    def get_last_user_message(self, state: MiniClawState) -> str:
        """获取最后一条用户消息"""
        messages = state.get("messages", [])
        for msg in reversed(messages):
            if hasattr(msg, "type") and msg.type == "human":
                return msg.content
            if hasattr(msg, "content"):
                return msg.content
        return ""

    def update_state(self, state: MiniClawState, updates: Dict[str, Any]) -> MiniClawState:
        """更新 State"""
        new_state = dict(state)
        new_state.update(updates)
        return new_state

    def _get_force_tools(self, state: MiniClawState) -> List[BaseTool]:
        """
        根据 State 中的 metadata 获取需要强制注入的工具

        这是强制工具注入的核心逻辑：
        1. 从 state.metadata 中读取 force_think 和 force_search
        2. 根据标记动态导入并返回对应的工具
        """
        force_tools: List[BaseTool] = []
        metadata = state.get("metadata") or {}

        if metadata.get("force_think"):
            from miniclaw.tools.think import think
            if think not in force_tools:
                force_tools.append(think)

        if metadata.get("force_search"):
            from miniclaw.tools.trail import trail
            if trail not in force_tools:
                force_tools.append(trail)

        return force_tools

    def _build_force_prompt(self, state: MiniClawState) -> str:
        """
        构建强制工具使用的提示词追加

        当用户强制启用某些功能时，在系统提示词中追加明确要求，
        增加模型调用对应工具的概率。
        """
        prompts = []
        metadata = state.get("metadata") or {}

        if metadata.get("force_think"):
            prompts.append(
                "\n\n【强制要求】用户已启用深度思考模式。"
                "在回答任何问题前，你必须先调用 `think` 工具进行结构化思考，"
                "分析问题的各个方面，然后再给出最终回答。"
            )

        if metadata.get("force_search"):
            prompts.append(
                "\n\n【强制要求】用户已启用联网搜索模式。"
                "在回答前，你必须先调用 `trail` 工具搜索最新的网络信息，"
                "基于搜索结果给出准确、及时的回复。"
            )

        return "\n".join(prompts)

    async def execute(self, state: MiniClawState) -> Dict[str, Any]:
        """
        执行 Worker 任务

        这是 Worker 的核心方法，被 Supervisor 调用。
        在调用前会根据 state.metadata 中的 force 标记注入工具。
        """
        # 动态获取需要强制注入的工具
        self._force_tools = self._get_force_tools(state)

        if self._use_react and (self._base_tools or self._force_tools):
            return await self._execute_react(state)
        else:
            return await self._execute_single_call(state)

    async def _execute_react(self, state: MiniClawState) -> Dict[str, Any]:
        """
        ReAct 模式执行
        """
        messages = state.get("messages", [])

        # 使用包含强制工具的 ReAct Agent 执行
        self._init_react_agent(self._force_tools)

        result = await self._agent_executor.ainvoke(
            {"messages": messages},
            config={"recursion_limit": self._max_iterations}
        )

        # 提取最终回复
        final_message = result["messages"][-1]
        response_content = final_message.content if hasattr(final_message, "content") else str(final_message)

        return {
            "current_agent": self.name,
            "agent_response": response_content,
            "messages": result["messages"],
        }

    def _build_rag_prompt(self, state: MiniClawState) -> str:
        """构建 RAG 上下文提示词"""
        rag_context = state.get("rag_context", "")
        if not rag_context:
            return ""
        return (
            "\n\n【知识库检索结果】\n"
            f"{rag_context}\n"
            "\n你可以参考以上知识库内容回答用户问题。"
        )

    async def _execute_single_call(self, state: MiniClawState) -> Dict[str, Any]:
        """
        单次调用模式执行（支持强制工具注入）
        """
        user_message = self.get_last_user_message(state)
        system_prompt = self._get_system_prompt()

        # 追加强制使用工具的提示词
        force_prompt = self._build_force_prompt(state)
        if force_prompt:
            system_prompt += force_prompt

        # 追加 RAG 上下文
        rag_prompt = self._build_rag_prompt(state)
        if rag_prompt:
            system_prompt += rag_prompt

        # 构建消息
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ]

        # 绑定工具并调用 LLM（包含强制注入的工具）
        llm_with_tools = self.bind_tools(self._force_tools)
        response = await llm_with_tools.ainvoke(messages)

        # 处理工具调用
        if hasattr(response, "tool_calls") and response.tool_calls:
            final_content = await self._handle_tool_calls(response.tool_calls, messages, response)
        else:
            final_content = response.content

        return {
            "current_agent": self.name,
            "agent_response": final_content,
            "messages": [response],
        }

    async def _handle_tool_calls(
        self,
        tool_calls: List[Dict[str, Any]],
        messages: List[Any],
        ai_response: AIMessage,
    ) -> str:
        """处理工具调用"""
        tool_results = []
        tool_map = self._build_tool_map()

        for tool_call in tool_calls:
            tool_name = self._extract_tool_name(tool_call)
            tool_args = self._extract_tool_args(tool_call)

            result = await self._execute_single_tool(tool_name, tool_args, tool_map)
            tool_results.append({"name": tool_name, "result": result})

        # 构建上下文并让 LLM 生成回复
        tool_context = self._build_tool_context(tool_results)
        final_messages = messages + [ai_response] + [
            HumanMessage(content=f"工具执行结果：\n{tool_context}\n\n请基于以上结果，给用户一个完整、友好的回复。")
        ]

        final_response = await self.llm.ainvoke(final_messages)
        return final_response.content

    def _extract_tool_name(self, tool_call: Dict[str, Any]) -> str:
        """提取工具名称"""
        if "name" in tool_call:
            return tool_call["name"]
        if "function" in tool_call and "name" in tool_call["function"]:
            return tool_call["function"]["name"]
        return ""

    def _extract_tool_args(self, tool_call: Dict[str, Any]) -> Dict[str, Any]:
        """提取工具参数"""
        args = tool_call.get("args") or tool_call.get("function", {}).get("arguments", {})
        if isinstance(args, str):
            import json
            try:
                return json.loads(args)
            except json.JSONDecodeError:
                return {}
        return args if isinstance(args, dict) else {}

    async def _execute_single_tool(self, tool_name: str, tool_args: Dict[str, Any], tool_map: Optional[Dict[str, Callable]] = None) -> str:
        """执行单个工具"""
        if tool_map is None:
            tool_map = self._build_tool_map()

        if tool_name not in tool_map:
            return f"❌ 工具 '{tool_name}' 未找到"

        try:
            tool = tool_map[tool_name]

            # 支持异步工具
            if hasattr(tool, 'ainvoke'):
                result = await tool.ainvoke(tool_args)
            elif hasattr(tool, 'func') and hasattr(tool.func, '__call__'):
                import asyncio
                import inspect
                if inspect.iscoroutinefunction(tool.func):
                    result = await tool.func(**tool_args)
                else:
                    result = tool.invoke(tool_args)
            else:
                result = tool.invoke(tool_args)

            return self._format_tool_result(tool_name, result)

        except Exception as e:
            return f"❌ 工具 '{tool_name}' 执行失败: {str(e)}"

    def _format_tool_result(self, tool_name: str, result: Any) -> str:
        """格式化工具结果"""
        custom_formatted = self.format_tool_result(tool_name, result)
        if custom_formatted is not None:
            return custom_formatted

        if isinstance(result, dict):
            if "error" in result:
                return f"❌ {result.get('message', '操作失败')}"
            return "\n".join(f"{k}: {v}" for k, v in result.items())
        elif isinstance(result, list):
            if len(result) == 0:
                return "暂无数据"
            return "\n".join(f"- {item}" for item in result[:10])
        return str(result)

    def _build_tool_context(self, tool_results: List[Dict[str, str]]) -> str:
        """构建工具结果上下文"""
        contexts = []
        for item in tool_results:
            name = item["name"]
            result = item["result"]
            contexts.append(f"【{name}】\n{result}")
        return "\n\n".join(contexts)

    def format_tool_result(self, tool_name: str, result: Any) -> Optional[str]:
        """
        子类可覆盖的自定义格式化方法

        Returns:
            格式化后的字符串，或 None 使用默认格式化
        """
        return None
