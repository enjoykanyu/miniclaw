"""
MiniClaw LangGraph Workflow - Supervisor Multi-Agent Pattern
"""

import logging
from typing import Dict, Any, Literal, Optional
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from miniclaw.core.state import MiniClawState, create_initial_state
from miniclaw.core.exceptions import MiniClawException, MiniClawErrorCode, AgentException
from miniclaw.core.error_handler import error_handler, retry_with_fallback, safe_execute
from miniclaw.agents.supervisor import SupervisorAgent, WorkerAgent as WorkerType

logger = logging.getLogger(__name__)


# Worker Agent 工厂函数
def create_worker_agent(agent_type: str):
    """根据类型创建 Worker Agent"""
    try:
        if agent_type == WorkerType.LEARNING.value:
            from miniclaw.agents.learning import LearningAgent
            return LearningAgent()
        elif agent_type == WorkerType.TASK.value:
            from miniclaw.agents.task import TaskAgent
            return TaskAgent()
        elif agent_type == WorkerType.INFO.value:
            from miniclaw.agents.info import InfoAgent
            return InfoAgent()
        elif agent_type == WorkerType.HEALTH.value:
            from miniclaw.agents.health import HealthAgent
            return HealthAgent()
        elif agent_type == WorkerType.DATA.value:
            from miniclaw.agents.data import DataAgent
            return DataAgent()
        elif agent_type == WorkerType.CHAT.value:
            from miniclaw.agents.chat import ChatAgent
            return ChatAgent()
        else:
            logger.warning(f"Unknown agent type: {agent_type}, falling back to chat")
            from miniclaw.agents.chat import ChatAgent
            return ChatAgent()
    except Exception as e:
        logger.error(f"Failed to create agent {agent_type}: {e}")
        raise AgentException(
            message=f"Failed to create agent: {agent_type}",
            agent_name=agent_type,
            original_error=e,
        )


@retry_with_fallback(max_attempts=3, fallback_value=None)
async def supervisor_node(state: MiniClawState) -> Command[Literal[
    WorkerType.LEARNING.value,
    WorkerType.TASK.value,
    WorkerType.INFO.value,
    WorkerType.HEALTH.value,
    WorkerType.DATA.value,
    WorkerType.CHAT.value,
    "finish"
]]:
    """
    Supervisor 节点 - 路由决策

    这是 LangGraph Supervisor 模式的核心：
    1. 接收当前状态
    2. 决定下一个 Worker Agent
    3. 返回 Command 进行路由
    """
    try:
        supervisor = SupervisorAgent()
        command = await supervisor.route(state)

        # 更新 state 中的 next_agent 用于条件边判断
        return Command(
            goto=command.goto,
            update={"next_agent": command.goto}
        )
    except Exception as e:
        logger.error(f"Supervisor routing error: {e}")
        # 降级到 chat agent
        return Command(
            goto=WorkerType.CHAT.value,
            update={"next_agent": WorkerType.CHAT.value}
        )


async def learning_agent_node(state: MiniClawState) -> Dict[str, Any]:
    """Learning Worker 节点"""
    return await _execute_worker_node(WorkerType.LEARNING.value, state)


async def task_agent_node(state: MiniClawState) -> Dict[str, Any]:
    """Task Worker 节点"""
    return await _execute_worker_node(WorkerType.TASK.value, state)


async def info_agent_node(state: MiniClawState) -> Dict[str, Any]:
    """Info Worker 节点"""
    return await _execute_worker_node(WorkerType.INFO.value, state)


async def health_agent_node(state: MiniClawState) -> Dict[str, Any]:
    """Health Worker 节点"""
    return await _execute_worker_node(WorkerType.HEALTH.value, state)


async def data_agent_node(state: MiniClawState) -> Dict[str, Any]:
    """Data Worker 节点"""
    return await _execute_worker_node(WorkerType.DATA.value, state)


async def chat_agent_node(state: MiniClawState) -> Dict[str, Any]:
    """Chat Worker 节点 (Fallback)"""
    return await _execute_worker_node(WorkerType.CHAT.value, state)


@retry_with_fallback(max_attempts=2, fallback_value={"error": "Worker execution failed"})
async def _execute_worker_node(agent_type: str, state: MiniClawState) -> Dict[str, Any]:
    """
    执行 Worker 节点，带重试和错误处理
    """
    try:
        agent = create_worker_agent(agent_type)
        result = await agent.execute(state)
        return result
    except Exception as e:
        logger.error(f"Worker {agent_type} execution error: {e}")

        # 包装错误
        if not isinstance(e, MiniClawException):
            e = AgentException(
                message=f"Agent execution failed: {str(e)}",
                agent_name=agent_type,
                original_error=e,
            )

        # 处理错误
        error_handler.handle_error(e, {"state": state})

        # 返回降级响应
        fallback_response = error_handler.get_fallback_response(e)
        return {
            "current_agent": agent_type,
            "agent_response": fallback_response,
            "error": True,
            "error_code": e.code.value if hasattr(e, 'code') else "UNKNOWN",
        }


def build_supervisor_graph(checkpointer: Optional[MemorySaver] = None):
    """
    构建 Supervisor 多 Agent 工作流
    """
    graph = StateGraph(MiniClawState)

    # 添加节点
    graph.add_node("supervisor", supervisor_node)
    graph.add_node(WorkerType.LEARNING.value, learning_agent_node)
    graph.add_node(WorkerType.TASK.value, task_agent_node)
    graph.add_node(WorkerType.INFO.value, info_agent_node)
    graph.add_node(WorkerType.HEALTH.value, health_agent_node)
    graph.add_node(WorkerType.DATA.value, data_agent_node)
    graph.add_node(WorkerType.CHAT.value, chat_agent_node)
    graph.add_node("finish", lambda state: {"agent_response": state.get("agent_response", "对话结束")})

    # 设置入口点
    graph.set_entry_point("supervisor")

    # 添加边：所有 Worker 执行完后回到 Supervisor
    workers = [
        WorkerType.LEARNING.value,
        WorkerType.TASK.value,
        WorkerType.INFO.value,
        WorkerType.HEALTH.value,
        WorkerType.DATA.value,
        WorkerType.CHAT.value,
    ]

    for worker in workers:
        graph.add_edge(worker, "supervisor")

    # 添加条件边：Supervisor 决定下一个节点
    graph.add_conditional_edges(
        "supervisor",
        lambda state: state.get("next_agent", "finish"),
        {
            WorkerType.LEARNING.value: WorkerType.LEARNING.value,
            WorkerType.TASK.value: WorkerType.TASK.value,
            WorkerType.INFO.value: WorkerType.INFO.value,
            WorkerType.HEALTH.value: WorkerType.HEALTH.value,
            WorkerType.DATA.value: WorkerType.DATA.value,
            WorkerType.CHAT.value: WorkerType.CHAT.value,
            "finish": END,
        }
    )

    if checkpointer is None:
        checkpointer = MemorySaver()

    return graph.compile(checkpointer=checkpointer)


class MiniClawApp:
    """
    MiniClaw 应用主类 - Supervisor 多 Agent 模式
    """

    def __init__(self, checkpointer: Optional[MemorySaver] = None):
        try:
            self.graph = build_supervisor_graph(checkpointer)
            logger.info("MiniClawApp initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize MiniClawApp: {e}")
            raise MiniClawException(
                message="Failed to initialize application",
                code=MiniClawErrorCode.INITIALIZATION_ERROR,
                original_error=e,
            )

    @safe_execute(
        fallback_value="抱歉，系统暂时无法处理您的请求，请稍后重试。",
        error_message="Chat processing failed",
        error_code=MiniClawErrorCode.INTERNAL_ERROR,
    )
    async def chat(
        self,
        message: str,
        user_id: str = "default",
        session_id: str = "default",
        thread_id: str = "default",
    ) -> str:
        """
        同步聊天接口（带完整异常处理）
        """
        from langchain_core.messages import HumanMessage

        config = {"configurable": {"thread_id": thread_id}}

        initial_state = create_initial_state(user_id, session_id)
        initial_state["messages"] = [HumanMessage(content=message)]

        try:
            result = await self.graph.ainvoke(initial_state, config)

            # 检查是否有错误
            if result.get("error"):
                error_code = result.get("error_code", "UNKNOWN")
                logger.warning(f"Agent returned error: {error_code}")
                return result.get("agent_response", "处理请求时出现问题，请重试。")

            # 获取 Worker 的回复
            agent_response = result.get("agent_response")
            if agent_response:
                return agent_response

            # 获取最后一条 AI 消息
            messages = result.get("messages", [])
            for msg in reversed(messages):
                if hasattr(msg, "type") and msg.type == "ai":
                    return msg.content

            return "抱歉，我无法处理您的请求。"

        except Exception as e:
            logger.error(f"Graph execution error: {e}")
            raise MiniClawException(
                message="Request processing failed",
                code=MiniClawErrorCode.INTERNAL_ERROR,
                details={"user_id": user_id, "session_id": session_id},
                original_error=e,
            )

    async def stream(
        self,
        message: str,
        user_id: str = "default",
        session_id: str = "default",
        thread_id: str = "default",
        force_think: bool = False,
        force_search: bool = False,
    ):
        """
        流式聊天接口（带异常处理）
        """
        from langchain_core.messages import HumanMessage

        config = {"configurable": {"thread_id": thread_id}}

        initial_state = create_initial_state(user_id, session_id)
        initial_state["messages"] = [HumanMessage(content=message)]

        try:
            async for event in self.graph.astream(initial_state, config):
                yield event
        except Exception as e:
            logger.error(f"Stream processing error: {e}")
            # 返回错误事件
            yield {
                "error": True,
                "message": "流式处理出现错误",
                "details": str(e),
            }
