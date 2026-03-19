"""
MiniClaw LangGraph Workflow Definition
"""

from typing import Optional
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from miniclaw.core.state import MiniClawState, create_initial_state
from miniclaw.core.router import intent_router_node, route_by_intent


async def learning_agent_node(state: MiniClawState) -> dict:
    from miniclaw.agents.learning import LearningAgent
    agent = LearningAgent()
    response = await agent.process(state)
    return {
        "current_agent": "learning",
        "agent_response": response,
    }


async def task_agent_node(state: MiniClawState) -> dict:
    from miniclaw.agents.task import TaskAgent
    agent = TaskAgent()
    response = await agent.process(state)
    return {
        "current_agent": "task",
        "agent_response": response,
    }


async def info_agent_node(state: MiniClawState) -> dict:
    from miniclaw.agents.info import InfoAgent
    agent = InfoAgent()
    response = await agent.process(state)
    return {
        "current_agent": "info",
        "agent_response": response,
    }


async def health_agent_node(state: MiniClawState) -> dict:
    from miniclaw.agents.health import HealthAgent
    agent = HealthAgent()
    response = await agent.process(state)
    return {
        "current_agent": "health",
        "agent_response": response,
    }


async def data_agent_node(state: MiniClawState) -> dict:
    from miniclaw.agents.data import DataAgent
    agent = DataAgent()
    response = await agent.process(state)
    return {
        "current_agent": "data",
        "agent_response": response,
    }


async def chat_agent_node(state: MiniClawState) -> dict:
    from miniclaw.agents.chat import ChatAgent
    agent = ChatAgent()
    response = await agent.process(state)
    return {
        "current_agent": "chat",
        "agent_response": response,
    }


async def response_node(state: MiniClawState) -> dict:
    from langchain_core.messages import AIMessage
    from datetime import datetime
    
    response_content = state.get("agent_response", "抱歉，我无法处理您的请求。")
    
    return {
        "messages": [AIMessage(content=response_content)],
        "updated_at": datetime.now().isoformat(),
    }


def build_graph(checkpointer: Optional[MemorySaver] = None):
    graph = StateGraph(MiniClawState)
    
    graph.add_node("intent_router", intent_router_node)
    graph.add_node("learning_agent", learning_agent_node)
    graph.add_node("task_agent", task_agent_node)
    graph.add_node("info_agent", info_agent_node)
    graph.add_node("health_agent", health_agent_node)
    graph.add_node("data_agent", data_agent_node)
    graph.add_node("chat_agent", chat_agent_node)
    graph.add_node("response", response_node)
    
    graph.set_entry_point("intent_router")
    
    graph.add_conditional_edges(
        "intent_router",
        route_by_intent,
        {
            "learning_agent": "learning_agent",
            "task_agent": "task_agent",
            "info_agent": "info_agent",
            "health_agent": "health_agent",
            "data_agent": "data_agent",
            "chat_agent": "chat_agent",
        }
    )
    
    for agent in ["learning_agent", "task_agent", "info_agent", "health_agent", "data_agent", "chat_agent"]:
        graph.add_edge(agent, "response")
    
    graph.add_edge("response", END)
    
    if checkpointer is None:
        checkpointer = MemorySaver()
    
    return graph.compile(checkpointer=checkpointer)


class MiniClawApp:
    def __init__(self, checkpointer: Optional[MemorySaver] = None):
        self.graph = build_graph(checkpointer)
    
    async def chat(
        self,
        message: str,
        user_id: str = "default",
        session_id: str = "default",
        thread_id: str = "default",
    ) -> str:
        from langchain_core.messages import HumanMessage
        
        config = {"configurable": {"thread_id": thread_id}}
        
        initial_state = create_initial_state(user_id, session_id)
        initial_state["messages"] = [HumanMessage(content=message)]
        
        result = await self.graph.ainvoke(initial_state, config)
        
        last_message = result["messages"][-1] if result.get("messages") else None
        return last_message.content if last_message else "抱歉，我无法处理您的请求。"
    
    async def stream(
        self,
        message: str,
        user_id: str = "default",
        session_id: str = "default",
        thread_id: str = "default",
    ):
        from langchain_core.messages import HumanMessage
        
        config = {"configurable": {"thread_id": thread_id}}
        
        initial_state = create_initial_state(user_id, session_id)
        initial_state["messages"] = [HumanMessage(content=message)]
        
        async for event in self.graph.astream(initial_state, config):
            yield event
