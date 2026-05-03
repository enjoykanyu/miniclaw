"""
MiniClaw Supervisor Agent
基于 LangGraph 官方 Supervisor 模式实现的多 Agent 协调器

参考: https://langchain-ai.github.io/langgraph/concepts/multi_agent/#supervisor
"""

from typing import Dict, List, Literal, Optional, Any
from enum import Enum

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.types import Command

from miniclaw.core.state import MiniClawState
from miniclaw.utils.llm import get_smart_llm


class WorkerType(str, Enum):
    """Worker Agent 类型枚举"""
    LEARNING = "learning"
    TASK = "task"
    INFO = "info"
    HEALTH = "health"
    DATA = "data"
    CHAT = "chat"
    FINISH = "finish"


# Worker Agent 定义
WORKER_DEFINITIONS = {
    WorkerType.LEARNING: {
        "name": "learning_agent",
        "description": "学习规划助手，帮助制定学习计划、追踪进度、安排复习",
        "tools": ["create_study_plan", "generate_excel_plan", "schedule_review"],
    },
    WorkerType.TASK: {
        "name": "task_agent",
        "description": "任务管理助手，管理TODO清单、创建任务、生成每日报告",
        "tools": ["create_task", "list_tasks", "complete_task", "generate_daily_summary"],
    },
    WorkerType.INFO: {
        "name": "info_agent",
        "description": "信息获取助手，查询天气、推送新闻、知识问答",
        "tools": ["get_weather", "get_news", "search_knowledge"],
    },
    WorkerType.HEALTH: {
        "name": "health_agent",
        "description": "健康提醒助手，定时提醒休息、管理作息、提供健康建议",
        "tools": ["set_reminder", "get_greeting", "get_health_tips"],
    },
    WorkerType.DATA: {
        "name": "data_agent",
        "description": "数据处理助手，操作Excel表格、数据分析",
        "tools": ["create_excel_file", "read_excel_file", "analyze_data", "update_excel_cell"],
    },
    WorkerType.CHAT: {
        "name": "chat_agent",
        "description": "日常聊天助手，处理一般对话和引导用户使用功能",
        "tools": [],
    },
}


SUPERVISOR_SYSTEM_PROMPT = """你是 MiniClaw 的 Supervisor（监督者），负责协调多个专业智能体（Worker Agents）完成用户请求。

## 你的职责
1. 分析用户请求，决定由哪个 Worker Agent 处理
2. 如果需要，可以依次调用多个 Worker Agent 协作完成任务
3. 当任务完成时，调用 FINISH

## 可用的 Worker Agents

{worker_descriptions}

## 决策规则

1. **单次任务**：如果用户请求可以由一个 Worker 完成，直接路由到该 Worker
2. **多步任务**：如果任务需要多个步骤，按顺序路由到不同的 Workers
3. **FINISH**：当任务完成或用户只是闲聊时，调用 FINISH

## 示例

用户: "帮我制定一个Python学习计划"
→ 路由到: learning

用户: "今天天气怎么样"
→ 路由到: info

用户: "创建一个任务：明天开会，然后查一下北京天气"
→ 先路由到: task，完成后路由到: info，最后 FINISH

用户: "你好"
→ 路由到: chat 或直接 FINISH

请分析用户请求，选择最合适的 Worker Agent 或 FINISH。
"""


def build_worker_descriptions() -> str:
    """构建 Worker Agent 描述文本"""
    descriptions = []
    for worker, info in WORKER_DEFINITIONS.items():
        descriptions.append(
            f"- **{worker.value}**: {info['description']}"
        )
    return "\n".join(descriptions)


class SupervisorAgent:
    """
    Supervisor Agent - 多 Agent 协调器

    基于 LangGraph 官方 Supervisor 模式实现：
    1. 使用结构化输出决定下一个 Worker
    2. 支持多轮协作
    3. 维护对话上下文
    """

    name = "supervisor"
    description = "Supervisor Agent，协调多个 Worker Agents 完成任务"

    def __init__(
        self,
        llm: Optional[BaseChatModel] = None,
        workers: Optional[List[WorkerType]] = None,
    ):
        self._llm = llm or get_smart_llm()
        self._workers = workers or list(WorkerType)
        if WorkerType.FINISH not in self._workers:
            self._workers.append(WorkerType.FINISH)

        # 构建系统提示词
        self._system_prompt = SUPERVISOR_SYSTEM_PROMPT.format(
            worker_descriptions=build_worker_descriptions()
        )

    def _get_last_user_message(self, state: MiniClawState) -> str:
        """获取最后一条用户消息"""
        messages = state.get("messages", [])
        for msg in reversed(messages):
            if hasattr(msg, "type") and msg.type == "human":
                return msg.content
            if hasattr(msg, "content"):
                content = msg.content
                # 简单判断是否是用户消息（不包含工具结果标记）
                if not content.startswith("【") and not content.startswith("工具执行结果"):
                    return content
        return ""

    def _build_routing_context(self, state: MiniClawState) -> str:
        """构建路由决策的上下文"""
        context_parts = []

        # 当前 Agent
        current_agent = state.get("current_agent")
        if current_agent:
            context_parts.append(f"当前正在执行: {current_agent}")

        # 历史消息摘要（最近3轮）
        messages = state.get("messages", [])
        if len(messages) > 1:
            context_parts.append("\n对话历史:")
            for msg in messages[-6:]:  # 最近6条消息
                if hasattr(msg, "type"):
                    role = "用户" if msg.type == "human" else "助手"
                    content = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
                    context_parts.append(f"{role}: {content}")

        return "\n".join(context_parts)

    async def route(self, state: MiniClawState) -> Command[Literal[tuple([w.value for w in WorkerType])]]:
        """
        Supervisor 路由决策

        基于 LangGraph Command 模式，决定下一个执行的 Worker Agent

        Returns:
            Command: 包含 goto 目标（Worker Agent 名称或 "finish"）
        """
        user_message = self._get_last_user_message(state)
        routing_context = self._build_routing_context(state)

        # 构建决策消息
        messages = [
            SystemMessage(content=self._system_prompt),
            HumanMessage(content=f"用户请求: {user_message}\n\n{routing_context}\n\n请决定下一个 Worker Agent（只返回名称）:"),
        ]

        # 使用结构化输出获取决策
        try:
            # 尝试使用 with_structured_output
            from pydantic import BaseModel, Field

            class RoutingDecision(BaseModel):
                next_agent: str = Field(
                    description=f"下一个 Worker Agent 名称，可选: {[w.value for w in self._workers]}",
                )
                reason: str = Field(
                    description="选择该 Agent 的原因",
                )

            structured_llm = self._llm.with_structured_output(RoutingDecision)
            decision = await structured_llm.ainvoke(messages)
            next_agent = decision.next_agent.lower()

        except Exception:
            # 降级：直接调用 LLM 并解析结果
            response = await self._llm.ainvoke(messages)
            content = response.content.lower()

            # 解析响应，找出匹配的 Worker
            next_agent = self._parse_agent_from_response(content)

        # 验证并返回 Command
        if next_agent == WorkerType.FINISH.value:
            return Command(goto=WorkerType.FINISH.value)

        # 检查是否是有效的 Worker
        valid_workers = [w.value for w in self._workers if w != WorkerType.FINISH]
        if next_agent in valid_workers:
            return Command(goto=next_agent)

        # 默认路由到 chat
        return Command(goto=WorkerType.CHAT.value)

    def _parse_agent_from_response(self, content: str) -> str:
        """从 LLM 响应中解析 Agent 名称"""
        content = content.lower().strip()

        # 检查是否包含 FINISH
        if "finish" in content or "完成" in content or "结束" in content:
            return WorkerType.FINISH.value

        # 检查各个 Worker
        for worker in WorkerType:
            if worker == WorkerType.FINISH:
                continue
            if worker.value in content:
                return worker.value

        # 默认返回 chat
        return WorkerType.CHAT.value

    def get_worker_info(self, worker_name: str) -> Optional[Dict[str, Any]]:
        """获取 Worker Agent 信息"""
        try:
            worker = WorkerType(worker_name)
            return WORKER_DEFINITIONS.get(worker)
        except ValueError:
            return None
