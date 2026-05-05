"""
MiniClaw Worker Agent Base Class
基于 LangGraph 官方 Worker Agent 模式实现

Worker Agent 是被 Supervisor 调用的专业智能体
"""
from loguru import logger

from abc import ABC
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
    5. 支持强制注入 think 和 TAVILY 工具
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
        """构建工具映射表，包含基础工具、MCP 工具和强制注入工具"""
        all_tools = list(self._base_tools)
        all_tools.extend(self._get_mcp_tools())
        all_tools.extend(self._force_tools)
        return {tool.name: tool for tool in all_tools}

    def _load_tool_by_name(self, tool_name: str) -> Optional[BaseTool]:
        """
        根据工具名称动态加载工具实例

        这是 Skill 系统的核心工具加载器。Skill 只声明工具名称，
        实际的工具实例由此方法动态查找并返回。

        查找优先级：
        1. 已加载的基础工具 (_base_tools)
        2. MCP 远程工具 (_get_mcp_tools)
        3. 内置工具模块动态导入 (miniclaw.tools.*)

        Args:
            tool_name: 工具名称，如 "tavily", "think", "get_news"

        Returns:
            BaseTool 实例，如果找不到则返回 None
        """
        # 1. 检查已加载的基础工具
        for tool in self._base_tools:
            if tool.name == tool_name:
                return tool

        # 2. 检查 MCP 工具
        mcp_tools = self._get_mcp_tools()
        for tool in mcp_tools:
            if tool.name == tool_name:
                return tool

        # 3. 动态导入内置工具模块
        # 支持的工具模块映射
        builtin_modules = {
            "tavily": "miniclaw.tools.tavily",
            "think": "miniclaw.tools.think",
            "trail": "miniclaw.tools.trail",
        }

        module_path = builtin_modules.get(tool_name)
        if module_path:
            try:
                import importlib
                module = importlib.import_module(module_path)
                # 工具在模块中通常以函数名或变量名暴露
                if hasattr(module, tool_name):
                    tool = getattr(module, tool_name)
                    # 确保是有效的工具（有 name 属性，且是 BaseTool 或 callable）
                    if hasattr(tool, "name"):
                        return tool
            except Exception as e:
                logger.warning(f"动态加载工具 '{tool_name}' 失败: {e}")

        logger.warning(f"找不到工具 '{tool_name}'，请检查 Skill 配置或工具模块")
        return None

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

    def _build_skills_prompt(self, state: MiniClawState) -> str:
        """
        构建技能目录提示词（渐进式披露 Level 1）


        将当前 Agent 绑定的技能目录注入 system prompt
        让 LLM 自主判断是否需要某个 skill
        """
        from miniclaw.skills.registry import skill_registry
        
        summary = skill_registry.build_skills_summary(self.name)
        if not summary:
            return ""
        
        return (
            f"\n\n{summary}\n"
            f"\n当你需要使用某个技能时，请回复：[SKILL: skill-name]\n"
            f"系统会自动加载该技能的详细指令。\n"
        )

    def _build_kb_prompt(self, state: MiniClawState) -> str:
        """构建知识库选择提示词，让 LLM 知道用户选择了哪些知识库"""
        metadata = state.get("metadata") or {}
        selected_kbs = metadata.get("selected_kbs")
        if not selected_kbs:
            return ""
        kb_list = ", ".join(selected_kbs)
        return (
            f"\n\n【知识库选择】\n"
            f"用户已选择以下知识库作为参考来源：{kb_list}\n"
            f"当你调用 rag_search 工具时，系统会自动使用这些知识库进行搜索。\n"
        )

    def _init_react_agent_with_state(self, state: MiniClawState, extra_tools: Optional[List[BaseTool]] = None) -> None:
        """初始化 ReAct Agent，支持动态工具注入 + 强制搜索上下文注入"""
        system_prompt = self._get_system_prompt()

        # 追加 RAG 上下文
        rag_prompt = self._build_rag_prompt(state)
        if rag_prompt:
            system_prompt += rag_prompt

        # 追加知识库选择提示
        kb_prompt = self._build_kb_prompt(state)
        if kb_prompt:
            system_prompt += kb_prompt

        # 追加技能目录提示（渐进式披露）
        skills_prompt = self._build_skills_prompt(state)
        if skills_prompt:
            system_prompt += skills_prompt

        all_tools = list(self._base_tools)
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

    def _get_tools_from_skills(self, state: MiniClawState) -> List[BaseTool]:
        """
        从 Skill 注册表获取当前 Agent 需要的工具
        并根据 Skill 中定义的条件决定是否注入
        
        Cherry Studio 设计模式：
        - Skill 声明式定义工具（名称 + 条件）
        - 运行时根据 state.metadata 中的条件动态加载工具实例
        """
        from miniclaw.skills.registry import skill_registry
        
        skills = skill_registry.get_for_agent(self.name)
        tools = []
        
        metadata = state.get("metadata") or {}
        
        for skill in skills:
            for tool_def in skill.tools:
                # 检查条件：condition 为 None 表示无条件注入
                condition = tool_def.condition
                if condition == "force_search" and not metadata.get("force_search"):
                    continue  # 不满足条件，跳过注入
                if condition == "force_think" and not metadata.get("force_think"):
                    continue
                
                # 加载工具实例
                tool = self._load_tool_by_name(tool_def.name)
                if tool:
                    tools.append(tool)
        
        return tools

    def _get_force_tools(self, state: MiniClawState) -> List[BaseTool]:
        """
        根据 State 中的 metadata 获取需要强制注入的工具

        这是强制工具注入的核心逻辑：
        1. 从 state.metadata 中读取 force_think 和 force_search
        2. 根据标记动态导入并返回对应的工具
        """
        """
        强制工具 = Skill 条件工具 + 用户显式强制标记
        """
        # 1. 从 Skill 获取条件触发的工具
        skill_tools = self._get_tools_from_skills(state)
        
        # 2. 用户显式强制（保留作为兜底）
        metadata = state.get("metadata") or {}
        force_tools = list(skill_tools)
        
        # 如果 force_search=true 但 Skill 没有覆盖，兜底注入
        if metadata.get("force_search") and not any(t.name == "tavily" for t in force_tools):
            from miniclaw.tools.tavily import tavily
            force_tools.append(tavily)
        
        return force_tools

    def _build_force_prompt(self, state: MiniClawState) -> str:
        """
        构建强制工具使用的提示词追加

        1. 如果搜索已在预处理阶段程序化执行 → 直接注入结果，禁止再调用搜索工具
        2. 如果搜索未执行但 force_search=True → 强制要求调用 TAVILY 工具
        3. 如果 force_think=True → 强制要求调用 think 工具
        """
        """
        强制提示词 = Skill 内容 + 动态条件
        """
        from miniclaw.skills.registry import skill_registry
        
        prompts = []
        metadata = state.get("metadata") or {}
        
        # 从 Skill 获取能力描述
        skill_prompt = skill_registry.build_prompt_for_agent(self.name)
        
        # 如果 force_search=true，在 Skill 描述基础上追加强制要求
        if metadata.get("force_search"):
            # 找到 web_search skill 的内容
            web_search_skill = skill_registry.get("web_search")
            if web_search_skill:
                prompts.append(f"【强制模式 - {web_search_skill.name}】\n{web_search_skill.content}")
            else:
                # fallback
                prompts.append("【强制要求】用户已启用联网搜索...")
        
        return "\n".join(prompts)

    async def execute(self, state: MiniClawState) -> Dict[str, Any]:
        """
        执行 Worker 任务

        这是 Worker 的核心方法，被 Supervisor 调用。
        在调用前会根据 state.metadata 中的 force 标记注入工具。
        """
        # 动态获取需要强制注入的工具
        self._force_tools = self._get_force_tools(state)

        # 关键日志：帮助调试工具注入
        metadata = state.get("metadata") or {}
        search_context = state.get("force_search_context")
        logger.info(
            f"Worker[{self.name}] execute: "
            f"force_think={metadata.get('force_think')}, "
            f"force_search={metadata.get('force_search')}, "
            f"search_context={'YES' if search_context else 'NO'}, "
            f"base_tools={[t.name for t in self._base_tools]}, "
            f"force_tools={[t.name for t in self._force_tools]}"
        )

        # 设置 RAG 工具上下文，让 rag_search 知道用户选择了哪些知识库
        selected_kbs = metadata.get("selected_kbs")
        kb_retrieval_mode = metadata.get("kb_retrieval_mode")
        if selected_kbs:
            from miniclaw.rag.rag_tools import set_rag_tool_context
            set_rag_tool_context(selected_kbs=selected_kbs, kb_retrieval_mode=kb_retrieval_mode)
            logger.info(f"Worker[{self.name}] RAG tool context set: selected_kbs={selected_kbs}, mode={kb_retrieval_mode}")

        try:
            if self._use_react and (self._base_tools or self._force_tools):
                return await self._execute_react(state)
            else:
                return await self._execute_single_call(state)
        finally:
            # 清除 RAG 工具上下文，避免污染后续请求
            from miniclaw.rag.rag_tools import clear_rag_tool_context
            clear_rag_tool_context()

    async def _execute_react(self, state: MiniClawState) -> Dict[str, Any]:
        """
        ReAct 模式执行

        关键修复：将搜索结果作为消息传入，而不是通过 state_modifier 注入系统提示词。
        create_react_agent 的 state_modifier 不接受动态拼接的长文本。
        """
        messages = list(state.get("messages", []))

        # 将强制搜索上下文作为消息注入（而不是通过 state_modifier）
        force_prompt = self._build_force_prompt(state)
        if force_prompt:
            messages.insert(0, SystemMessage(content=force_prompt))

        # 使用包含强制工具的 ReAct Agent 执行
        self._init_react_agent_with_state(state, self._force_tools)

        result = await self._agent_executor.ainvoke(
            {"messages": messages},
            config={"recursion_limit": self._max_iterations}
        )

        # 提取最终回复
        final_message = result["messages"][-1]
        response_content = final_message.content if hasattr(final_message, "content") else str(final_message)

        if not response_content:
            response_content = str(final_message)

        return {
            "current_agent": self.name,
            "agent_response": response_content,
            "messages": [AIMessage(content=response_content)],
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

    def _get_required_tools(self, state: MiniClawState) -> List[str]:
        """
        获取当前状态下必须调用的工具列表

        根据 metadata 中的 force 标记确定哪些工具是强制必须调用的。
        如果工具已经在预处理阶段执行过（如 force_search_context 已有值），
        则不再强制要求调用。
        """
        required_tools: List[str] = []
        metadata = state.get("metadata") or {}

        if metadata.get("force_think"):
            required_tools.append("think")

        if metadata.get("force_search") and not state.get("force_search_context"):
            required_tools.append("tavily")

        return required_tools

    async def _execute_single_call(self, state: MiniClawState) -> Dict[str, Any]:
        """
        单次调用模式执行（支持强制工具注入和强制工具重试）

        如果设置了 force_think 或 force_search，但模型没有调用对应工具，
        会拦截回答并要求模型重新调用工具。
        """
        user_message = self.get_last_user_message(state)
        system_prompt = self._get_system_prompt()

        # 追加 RAG 上下文
        rag_prompt = self._build_rag_prompt(state)
        if rag_prompt:
            system_prompt += rag_prompt

        # 追加知识库选择提示
        kb_prompt = self._build_kb_prompt(state)
        if kb_prompt:
            system_prompt += kb_prompt

        # 追加技能目录提示（渐进式披露）
        skills_prompt = self._build_skills_prompt(state)
        if skills_prompt:
            system_prompt += skills_prompt

        # 构建消息列表
        messages: List[Any] = [SystemMessage(content=system_prompt)]

        # 将强制搜索上下文作为独立消息注入（避免超长 system prompt）
        force_prompt = self._build_force_prompt(state)
        if force_prompt:
            messages.append(SystemMessage(content=force_prompt))

        messages.append(HumanMessage(content=user_message))

        # 绑定工具并调用 LLM（包含强制注入的工具）
        llm_with_tools = self.bind_tools(self._force_tools)
        response = await llm_with_tools.ainvoke(messages)

        # 校验 LLM 是否请求加载某个 Skill（渐进式披露 ）
        skill_content = self._check_and_load_skill(response)
        if skill_content:
            # LLM 请求了某个 skill，加载其内容并重新调用
            logger.info(f"Worker[{self.name}] LLM 请求加载 skill，重新调用")
            messages.append(response)
            messages.append(SystemMessage(content=f"【Skill 详细指令】\n{skill_content}"))
            response = await llm_with_tools.ainvoke(messages)

        # 检查是否有强制要求但未调用的工具
        required_tools = self._get_required_tools(state)
        called_tools = []
        if hasattr(response, "tool_calls") and response.tool_calls:
            called_tools = [self._extract_tool_name(tc) for tc in response.tool_calls]

        missing_tools = [t for t in required_tools if t not in called_tools]

        # 如果强制工具未调用，拦截并重新要求调用
        if missing_tools and hasattr(response, "content"):
            retry_prompt = (
                f"你还没有调用必要的工具：{', '.join(missing_tools)}。"
                f"请先调用这些工具，然后再给出最终回答。"
            )
            messages = messages + [
                response,
                HumanMessage(content=retry_prompt),
            ]
            response = await llm_with_tools.ainvoke(messages)

        # 处理工具调用
        if hasattr(response, "tool_calls") and response.tool_calls:
            final_content = await self._handle_tool_calls(response.tool_calls, messages, response)
        else:
            final_content = response.content

        return {
            "current_agent": self.name,
            "agent_response": final_content,
            "messages": [AIMessage(content=final_content)],
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

    def _check_and_load_skill(self, response: Any) -> Optional[str]:
        """
        检查 LLM 回复是否包含 [SKILL: name] 标记，如果是则加载该 skill 内容
        
        渐进式披露 ：LLM 自主判断需要某个 skill 后，系统按需加载
        
        Args:
            response: LLM 的回复消息
            
        Returns:
            Skill 的完整内容（包括 frontmatter），如果没有请求则返回 None
        """
        import re
        
        content = ""
        if hasattr(response, "content"):
            content = response.content or ""
        
        # 匹配 [SKILL: skill-name] 标记
        match = re.search(r'\[SKILL:\s*([^\]]+)\]', content)
        if not match:
            return None
        
        skill_name = match.group(1).strip()
        logger.info(f"Worker[{self.name}] LLM 请求加载 skill: {skill_name}")
        
        # 从 SkillLoader 加载完整内容
        from miniclaw.skills.loader import SkillLoader
        loader = SkillLoader()
        # 先加载所有 skill 建立文件映射
        loader.load_all()
        full_content = loader.load_skill_content(skill_name)
        
        if full_content:
            logger.info(f"Worker[{self.name}] 成功加载 skill '{skill_name}' 内容")
            return full_content
        else:
            logger.warning(f"Worker[{self.name}] 找不到 skill '{skill_name}'")
            return None

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
