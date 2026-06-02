"""
Supervisor Node

对标 OpenClaw 的 agentCommand 入口调度：
  - 分析用户请求，决定由哪个 Worker Agent 处理
  - 支持多步协作（Worker 完成后可回到 Supervisor 重新评估）
  - 使用结构化输出获取路由决策

LangGraph 中 supervisor 是路由中枢，
通过 state.next_agent 字段决定路由目标。
条件边 _route_from_supervisor 读取 next_agent 决定下一步。
"""

from typing import Dict, Any, List, Optional

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from loguru import logger

from agent_loop.state import AgenticLoopState


_WORKER_TYPES = ["learning", "task", "info", "health", "data", "chat", "finish"]

_WORKER_DESCRIPTIONS = {
    "learning": "学习规划助手，帮助制定学习计划、追踪进度、安排复习",
    "task": "任务管理助手，管理TODO清单、创建任务、生成每日报告",
    "info": "信息获取助手，查询天气、推送新闻、知识问答",
    "health": "健康提醒助手，定时提醒休息、管理作息、提供健康建议",
    "data": "数据处理助手，操作Excel表格、数据分析",
    "chat": "日常聊天助手，处理一般对话和引导用户使用功能",
}

_SUPERVISOR_SYSTEM_PROMPT = """你是 MiniClaw 的 Supervisor（监督者），负责协调多个专业智能体完成用户请求。

## 你的职责
1. 分析用户请求，决定由哪个 Worker Agent 处理
2. 如果需要，可以依次调用多个 Worker Agent 协作完成任务
3. 当任务完成时，选择 finish

## 可用的 Worker Agents

{worker_descriptions}

## 决策规则

1. **单次任务**：如果用户请求可以由一个 Worker 完成，直接路由到该 Worker
2. **多步任务**：如果任务需要多个步骤，按顺序路由到不同的 Workers
3. **finish**：当任务完成或用户只是闲聊时，选择 finish

## 重要：多步协作
Worker 完成后会回到你这里，你需要决定：
- 是否需要路由到另一个 Worker 继续处理
- 还是任务已经完成，可以 finish

请分析用户请求，选择最合适的 Worker Agent 或 finish。"""


def _build_worker_descriptions() -> str:
    lines = []
    for name, desc in _WORKER_DESCRIPTIONS.items():
        lines.append(f"- **{name}**: {desc}")
    return "\n".join(lines)


def _get_last_user_message(state: AgenticLoopState) -> str:
    messages = state.get("messages", [])
    for msg in reversed(messages):
        if hasattr(msg, "type") and msg.type == "human":
            return msg.content
    return ""


def _build_routing_context(state: AgenticLoopState) -> str:
    parts = []

    current_agent = state.get("current_agent")
    if current_agent:
        parts.append(f"当前正在执行: {current_agent}")

    agent_response = state.get("agent_response")
    if agent_response:
        parts.append(f"当前 Worker 的回复: {agent_response[:500]}")

    messages = state.get("messages", [])
    if len(messages) > 1:
        parts.append("\n最近对话:")
        for msg in messages[-6:]:
            if hasattr(msg, "type"):
                role = "用户" if msg.type == "human" else "助手"
                content = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
                parts.append(f"{role}: {content}")

    loop_iteration = state.get("loop_iteration", 0)
    if loop_iteration > 0:
        parts.append(f"\n当前循环轮次: {loop_iteration}")

    return "\n".join(parts)


async def supervisor_node(state: AgenticLoopState) -> Dict[str, Any]:
    """
    Supervisor 路由节点

    对标 OpenClaw 的 agentCommand 调度逻辑：
    1. 解析用户请求
    2. 决定路由目标
    3. 通过 state.next_agent 字段传递路由决策

    条件边 _route_from_supervisor 读取 next_agent 决定下一步：
    - next_agent == "finish" → finish 节点
    - 其他 → agent_reason 节点（同时设置 current_agent）
    """
    from miniclaw.utils.llm import get_smart_llm

    user_message = _get_last_user_message(state)
    routing_context = _build_routing_context(state)

    system_prompt = _SUPERVISOR_SYSTEM_PROMPT.format(
        worker_descriptions=_build_worker_descriptions()
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=(
            f"用户请求: {user_message}\n\n{routing_context}\n\n"
            f"请决定下一个 Worker Agent（只返回名称: {', '.join(_WORKER_TYPES)}）:"
        )),
    ]

    decision_reason = ""
    next_agent = "chat"

    try:
        from pydantic import BaseModel, Field

        class RoutingDecision(BaseModel):
            next_agent: str = Field(
                description=f"下一个 Worker Agent 名称，可选: {_WORKER_TYPES}",
            )
            reason: str = Field(description="选择该 Agent 的原因")

        llm = get_smart_llm()
        structured_llm = llm.with_structured_output(RoutingDecision)
        decision = await structured_llm.ainvoke(messages)
        next_agent = decision.next_agent.lower().strip()
        decision_reason = decision.reason

    except Exception as e:
        logger.debug(f"Structured output failed, falling back to text parsing: {e}")
        try:
            llm = get_smart_llm()
            response = await llm.ainvoke(messages)
            content = response.content.lower().strip()
            decision_reason = response.content
            next_agent = _parse_agent_from_response(content)
        except Exception as e2:
            logger.error(f"Supervisor LLM call failed: {e2}")
            next_agent = "chat"

    if next_agent not in _WORKER_TYPES:
        next_agent = "chat"

    logger.info(f"Supervisor decision: {next_agent} (reason: {decision_reason[:100]})")

    updates: Dict[str, Any] = {
        "next_agent": next_agent,
        "supervisor_reason": decision_reason,
    }

    if next_agent != "finish":
        updates["current_agent"] = next_agent

    return updates


def _parse_agent_from_response(content: str) -> str:
    content = content.lower().strip()

    if "finish" in content or "完成" in content or "结束" in content:
        return "finish"

    for worker_name in _WORKER_DESCRIPTIONS:
        if worker_name in content:
            return worker_name

    return "chat"
