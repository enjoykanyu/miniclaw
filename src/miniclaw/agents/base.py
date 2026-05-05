"""
MiniClaw Base Agent Class
使用 AgentExecutor 模式实现自动化工具调用
"""

from abc import ABC
from typing import Any, Dict, List, Optional, Callable

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.tools import BaseTool
from langgraph.prebuilt import create_react_agent

from miniclaw.core.state import MiniClawState
from miniclaw.utils.llm import get_smart_llm
from miniclaw.skills.registry import skill_registry


class BaseAgent(ABC):
    """
    BaseAgent - 使用 AgentExecutor 模式的基础智能体类

    特性：
    1. 使用 LangGraph 的 create_react_agent 实现自动化工具调用
    2. 支持单次调用模式（默认）和 ReAct 多步推理模式
    3. 自动化的工具调用处理和结果格式化
    """

    name: str = "base_agent"
    description: str = "Base agent class"

    def __init__(
        self,
        llm: Optional[BaseChatModel] = None,
        tools: Optional[List[BaseTool]] = None,
        use_react: bool = False,
        max_iterations: int = 5,
    ):
        """
        初始化 BaseAgent

        Args:
            llm: 语言模型实例
            tools: 工具列表
            use_react: 是否使用 ReAct 多步推理模式
            max_iterations: ReAct 模式最大迭代次数
        """
        self._llm = llm
        self._tools = tools or []
        self._use_react = use_react
        self._max_iterations = max_iterations

        # 构建工具映射表，O(1) 查找
        self._tool_map: Dict[str, Callable] = {
            tool.name: tool for tool in self._tools
        }

        # 初始化 AgentExecutor
        self._agent_executor = None
        if self._use_react and self._tools:
            self._init_agent_executor()

    def _init_agent_executor(self) -> None:
        """初始化 ReAct Agent Executor"""
        system_prompt = self._get_system_prompt()
        self._agent_executor = create_react_agent(
            model=self.llm,
            tools=self._tools,
            state_modifier=system_prompt,
        )

    
    def _get_system_prompt(self) -> str:
        """
        获取系统提示词 - 自动追加匹配的 skills
        """
        base_prompt = f"你是 {self.name}，{self.description}"
        
        # 从注册表获取当前 Agent 的技能目录摘要（仅 name + description）
        skills_summary = skill_registry.build_skills_summary(self.name)
        
        if skills_summary:
            return (
                f"{base_prompt}\n\n{skills_summary}\n\n"
                f"当你需要使用某个技能时，请回复：[SKILL: skill-name]\n"
                f"系统会自动加载该技能的详细指令。"
            )
        
        return base_prompt


    @property
    def llm(self) -> BaseChatModel:
        if self._llm is None:
            self._llm = get_smart_llm()
        return self._llm

    def get_tools(self) -> List[BaseTool]:
        return self._tools

    def bind_tools(self) -> Any:
        if self._tools:
            return self.llm.bind_tools(self._tools)
        return self.llm

    def get_last_user_message(self, state: MiniClawState) -> str:
        messages = state.get("messages", [])
        for msg in reversed(messages):
            if hasattr(msg, "type") and msg.type == "human":
                return msg.content
            if hasattr(msg, "content"):
                return msg.content
        return ""

    def update_state(self, state: MiniClawState, updates: Dict[str, Any]) -> MiniClawState:
        new_state = dict(state)
        new_state.update(updates)
        return new_state

    async def process(self, state: MiniClawState) -> str:
        """
        主处理流程

        根据配置选择执行模式：
        1. ReAct 模式：使用 AgentExecutor 进行多步推理
        2. 单次调用模式：单次 LLM 调用 + 自动化工具执行
        """
        if self._use_react and self._agent_executor:
            return await self._process_react(state)
        else:
            return await self._process_single_call(state)

    async def _process_react(self, state: MiniClawState) -> str:
        """
        ReAct 模式处理 - 使用 AgentExecutor 进行多步推理

        适用场景：
        - 需要多步推理的复杂任务
        - 工具结果需要进一步分析和决策
        """
        user_message = self.get_last_user_message(state)

        # 构建输入消息
        messages = state.get("messages", [])
        if not messages:
            messages = [HumanMessage(content=user_message)]

        # 使用 AgentExecutor 执行
        result = await self._agent_executor.ainvoke(
            {"messages": messages},
            config={"recursion_limit": self._max_iterations}
        )

        # 提取最终回复
        final_message = result["messages"][-1]
        return final_message.content if hasattr(final_message, "content") else str(final_message)

    async def _process_single_call(self, state: MiniClawState) -> str:
        """
        单次调用模式处理 - 单次 LLM 调用 + 自动化工具执行

        适用场景：
        - 简单直接的任务
        - 对延迟敏感的场景
        - 工具调用是"一次性"的
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
            return await self._handle_tool_calls(response.tool_calls, messages, response)

        return response.content

    async def _handle_tool_calls(
        self,
        tool_calls: List[Dict[str, Any]],
        messages: List[Any],
        ai_response: AIMessage,
    ) -> str:
        """
        处理工具调用并生成最终回复

        流程：
        1. 执行所有工具调用
        2. 将工具结果整合到对话上下文
        3. 让 LLM 生成最终的自然语言回复
        """
        tool_results = []

        for tool_call in tool_calls:
            tool_name = self._extract_tool_name(tool_call)
            tool_args = self._extract_tool_args(tool_call)

            result = await self._execute_single_tool(tool_name, tool_args)
            tool_results.append({"name": tool_name, "result": result})

        # 构建包含工具结果的上下文
        tool_context = self._build_tool_context(tool_results)

        # 让 LLM 基于工具结果生成最终回复
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
        """
        执行单个工具

        支持：
        - 异步工具（ainvoke）
        - 同步工具（invoke）
        - 装饰器工具（func）
        """
        if tool_name not in self._tool_map:
            return f"❌ 工具 '{tool_name}' 未找到"

        try:
            tool = self._tool_map[tool_name]

            # 优先使用异步调用
            if hasattr(tool, 'ainvoke'):
                result = await tool.ainvoke(tool_args)
            # 检查是否是异步函数
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
        """
        格式化工具执行结果

        子类可以覆盖此方法实现自定义格式化
        """
        # 调用子类的自定义格式化（如果存在）
        custom_formatted = self.format_tool_result(tool_name, result)
        if custom_formatted is not None:
            return custom_formatted

        # 默认格式化逻辑
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
