"""
MiniClaw LangGraph Workflow - Supervisor Multi-Agent Pattern
"""

from typing import Dict, Any, Literal, Optional
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from miniclaw.core.state import MiniClawState, create_initial_state
from miniclaw.agents.supervisor import SupervisorAgent, WorkerAgent as WorkerType


# Worker Agent 工厂函数
def create_worker_agent(agent_type: str):
    """根据类型创建 Worker Agent"""
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
        from miniclaw.agents.chat import ChatAgent
        return ChatAgent()


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
    supervisor = SupervisorAgent()
    command = await supervisor.route(state)
    
    # 更新 state 中的 next_agent 用于条件边判断
    return Command(
        goto=command.goto,
        update={"next_agent": command.goto}
    )


async def learning_agent_node(state: MiniClawState) -> Dict[str, Any]:
    """Learning Worker 节点"""
    agent = create_worker_agent(WorkerType.LEARNING.value)
    result = await agent.execute(state)
    return result


async def task_agent_node(state: MiniClawState) -> Dict[str, Any]:
    """Task Worker 节点"""
    agent = create_worker_agent(WorkerType.TASK.value)
    result = await agent.execute(state)
    return result


async def info_agent_node(state: MiniClawState) -> Dict[str, Any]:
    """Info Worker 节点"""
    agent = create_worker_agent(WorkerType.INFO.value)
    result = await agent.execute(state)
    return result


async def health_agent_node(state: MiniClawState) -> Dict[str, Any]:
    """Health Worker 节点"""
    agent = create_worker_agent(WorkerType.HEALTH.value)
    result = await agent.execute(state)
    return result


async def data_agent_node(state: MiniClawState) -> Dict[str, Any]:
    """Data Worker 节点"""
    agent = create_worker_agent(WorkerType.DATA.value)
    result = await agent.execute(state)
    return result


async def chat_agent_node(state: MiniClawState) -> Dict[str, Any]:
    """Chat Worker 节点 (Fallback)"""
    agent = create_worker_agent(WorkerType.CHAT.value)
    result = await agent.execute(state)
    return result


def build_supervisor_graph(checkpointer: Optional[MemorySaver] = None):
    """
    构建 Supervisor 多 Agent 工作流

    架构：
    ```
    ┌─────────────┐
    │ Supervisor  │
    │  (Router)   │
    └──────┬──────┘
           │
    ┌──────┴──────┬──────────┬──────────┬──────────┬──────────┬──────────┐
    │             │          │          │          │          │          │
    ▼             ▼          ▼          ▼          ▼          ▼          ▼
┌────────┐  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
│Learning│  │  Task  │ │  Info  │ │ Health │ │  Data  │ │  Chat  │ │ FINISH │
└────┬───┘  └────┬───┘ └────┬───┘ └────┬───┘ └────┬───┘ └────┬───┘ └────┬───┘
     │           │          │          │          │          │          │
     └───────────┴──────────┴──────────┴──────────┴──────────┴──────────┘
                                       │
                                       ▼
                                 ┌──────────┐
                                 │   END    │
                                 └──────────┘
    ```
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
        self.graph = build_supervisor_graph(checkpointer)

    async def chat(
        self,
        message: str,
        user_id: str = "default",
        session_id: str = "default",
        thread_id: str = "default",
    ) -> str:
        """
        同步聊天接口

        流程：
        1. 创建初始状态
        2. 调用 Graph 执行
        3. 返回最终回复
        """
        from langchain_core.messages import HumanMessage

        config = {"configurable": {"thread_id": thread_id}}

        initial_state = create_initial_state(user_id, session_id)
        initial_state["messages"] = [HumanMessage(content=message)]

        result = await self.graph.ainvoke(initial_state, config)

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

    async def stream(
        self,
        message: str,
        user_id: str = "default",
        session_id: str = "default",
        thread_id: str = "default",
    ):
        """
        流式聊天接口

        实时返回执行过程中的事件
        """
        from langchain_core.messages import HumanMessage

        config = {"configurable": {"thread_id": thread_id}}

        initial_state = create_initial_state(user_id, session_id)
        initial_state["messages"] = [HumanMessage(content=message)]

        async for event in self.graph.astream(initial_state, config):
            yield event
