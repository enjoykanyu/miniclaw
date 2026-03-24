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


class WorkerAgent(ABC):
    """
    Worker Agent 基类

    特性：
    1. 被 Supervisor 调用执行特定任务
    2. 可以访问共享的 State
    3. 返回 Command 以便 Supervisor 继续决策
    4. 支持工具调用和 ReAct 模式
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
        self._tools = tools or []
        self._use_react = use_react
        self._max_iterations = max_iterations

        # 构建工具映射表
        self._tool_map: Dict[str, Callable] = {
            tool.name: tool for tool in self._tools
        }

        # 初始化 ReAct Agent（如果需要）
        self._agent_executor = None
        if self._use_react and self._tools:
            self._init_react_agent()

    def _init_react_agent(self) -> None:
        """初始化 ReAct Agent"""
        system_prompt = self._get_system_prompt()
        self._agent_executor = create_react_agent(
            model=self.llm,
            tools=self._tools,
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
        """获取工具列表，包括本地工具和 MCP 工具"""
        tools = list(self._tools)
        
        # 添加 MCP 工具
        try:
            mcp_tools = mcp_tool_registry.get_all_tools()
            tools.extend(mcp_tools)
        except Exception:
            pass
        
        return tools

    def bind_tools(self) -> Any:
        if self._tools:
            return self.llm.bind_tools(self._tools)
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

    async def execute(self, state: MiniClawState) -> Dict[str, Any]:
        """
        执行 Worker 任务

        这是 Worker 的核心方法，被 Supervisor 调用

        Returns:
            Dict 包含更新后的 state 字段
        """
        if self._use_react and self._agent_executor:
            return await self._execute_react(state)
        else:
            return await self._execute_single_call(state)

    async def _execute_react(self, state: MiniClawState) -> Dict[str, Any]:
        """
        ReAct 模式执行
        """
        messages = state.get("messages", [])

        # 使用 ReAct Agent 执行
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

    async def _execute_single_call(self, state: MiniClawState) -> Dict[str, Any]:
        """
        单次调用模式执行
        """
        user_message = self.get_last_user_message(state)
        system_prompt = self._get_system_prompt()

        # 构建消息
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ]

        # 绑定工具并调用 LLM
        llm_with_tools = self.bind_tools()
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

        for tool_call in tool_calls:
            tool_name = self._extract_tool_name(tool_call)
            tool_args = self._extract_tool_args(tool_call)

            result = await self._execute_single_tool(tool_name, tool_args)
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

    async def _execute_single_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> str:
        """执行单个工具"""
        if tool_name not in self._tool_map:
            return f"❌ 工具 '{tool_name}' 未找到"

        try:
            tool = self._tool_map[tool_name]

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
