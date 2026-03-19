"""
MiniClaw Router Module
Routes user requests to appropriate agents based on intent
"""

from typing import Literal
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from miniclaw.core.state import MiniClawState
from miniclaw.utils.llm import get_fast_llm
from miniclaw.utils.helpers import load_prompt_template


class IntentResult(BaseModel):
    intent: Literal["learning", "task", "info", "health", "data", "chat"] = Field(
        description="The detected intent category"
    )
    confidence: float = Field(
        description="Confidence score between 0 and 1",
        ge=0.0,
        le=1.0,
    )


INTENT_KEYWORDS = {
    "learning": [
        "学习计划", "学习", "复习", "课程", "教程", "学习进度",
        "艾宾浩斯", "记忆曲线", "学习目标", "制定计划",
    ],
    "task": [
        "任务", "todo", "待办", "清单", "完成", "进度",
        "截止", "优先级", "提醒任务", "创建任务",
    ],
    "info": [
        "天气", "新闻", "资讯", "查询", "搜索",
        "今天天气", "天气预报", "最新新闻",
    ],
    "health": [
        "休息", "喝水", "站起来", "眼保健操", "健康",
        "早安", "午安", "晚安", "久坐", "运动",
    ],
    "data": [
        "excel", "表格", "数据", "分析", "统计",
        "新建表格", "数据处理", "导出",
    ],
}


def detect_intent_by_keywords(message: str) -> str:
    message_lower = message.lower()
    
    scores = {}
    for intent, keywords in INTENT_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in message_lower)
        scores[intent] = score
    
    max_score = max(scores.values())
    if max_score == 0:
        return "chat"
    
    for intent, score in scores.items():
        if score == max_score:
            return intent
    
    return "chat"


async def detect_intent_with_llm(message: str) -> IntentResult:
    try:
        prompts = load_prompt_template("router")
        system_prompt = prompts.get("system", "")
        examples = prompts.get("routing_examples", "")
        
        llm = get_fast_llm()
        structured_llm = llm.with_structured_output(IntentResult)
        
        messages = [
            SystemMessage(content=system_prompt),
            SystemMessage(content=f"示例：\n{examples}"),
            HumanMessage(content=f"用户输入：{message}\n\n请判断意图："),
        ]
        
        result = await structured_llm.ainvoke(messages)
        return result
    except Exception:
        keyword_intent = detect_intent_by_keywords(message)
        return IntentResult(intent=keyword_intent, confidence=0.6)


async def intent_router_node(state: MiniClawState) -> dict:
    last_message = state["messages"][-1] if state["messages"] else None
    
    if not last_message:
        return {"intent": "chat"}
    
    message_content = last_message.content if hasattr(last_message, "content") else str(last_message)
    
    intent_result = await detect_intent_with_llm(message_content)
    
    return {
        "intent": intent_result.intent,
        "updated_at": state.get("updated_at"),
    }


def route_by_intent(state: MiniClawState) -> str:
    intent = state.get("intent", "chat")
    
    routing_map = {
        "learning": "learning_agent",
        "task": "task_agent",
        "info": "info_agent",
        "health": "health_agent",
        "data": "data_agent",
        "chat": "chat_agent",
    }
    
    return routing_map.get(intent, "chat_agent")
