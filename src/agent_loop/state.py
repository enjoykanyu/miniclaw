"""
Agentic Loop State Definition

对标 OpenClaw 三层嵌套循环的状态管理：
  - 主循环层: while(true) 重试/恢复
  - 尝试层: 单次推理生命周期
  - 事件层: 流式响应处理

LangGraph 中通过 StateGraph 条件边实现循环控制，
状态字段承载循环计数、断路器、压缩等运行时信息。
"""

from typing import TypedDict, List, Optional, Annotated, Any, Dict
from datetime import datetime
from enum import Enum

from langgraph.graph import add_messages


class LoopPhase(str, Enum):
    RAG_DETECT = "rag_detect"
    SUPERVISOR = "supervisor"
    AGENT_REASON = "agent_reason"
    TOOL_EXECUTE = "tool_execute"
    COMPACTION = "compaction"
    FINISH = "finish"


class AttemptStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CONTEXT_OVERFLOW = "context_overflow"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"


class ToolCallRecord(TypedDict):
    tool_name: str
    args: Dict[str, Any]
    result_summary: str
    timestamp: str
    iteration: int


class AgenticLoopState(TypedDict):
    messages: Annotated[list, add_messages]
    user_id: str
    session_id: str

    next_agent: Optional[str]
    supervisor_reason: Optional[str]
    current_agent: Optional[str]
    agent_response: Optional[str]
    intent: Optional[str]

    loop_iteration: int
    max_loop_iterations: int
    tool_call_count: int
    max_tool_calls: int
    tool_call_history: List[ToolCallRecord]

    attempt_status: Optional[str]
    attempt_retry_count: int
    max_attempt_retries: int

    compaction_count: int
    max_compaction_count: int
    context_token_estimate: int
    max_context_tokens: int

    loop_breaker_tripped: bool
    loop_breaker_reason: Optional[str]

    last_error: Optional[str]
    last_error_code: Optional[str]

    task_context: Optional[dict]
    current_tasks: Optional[List[dict]]
    learning_progress: Optional[dict]
    study_plans: Optional[List[dict]]
    reminders: Optional[List[dict]]
    weather_info: Optional[dict]
    news_items: Optional[List[dict]]
    excel_files: Optional[List[str]]
    current_excel: Optional[str]

    rag_context: Optional[str]
    rag_sources: Optional[List[dict]]
    needs_rag: Optional[bool]
    force_search_context: Optional[str]

    metadata: Optional[dict]
    created_at: Optional[str]
    updated_at: Optional[str]


_DEFAULT_MAX_LOOP_ITERATIONS = 25
_DEFAULT_MAX_TOOL_CALLS = 50
_DEFAULT_MAX_ATTEMPT_RETRIES = 3
_DEFAULT_MAX_COMPACTION_COUNT = 3
_DEFAULT_MAX_CONTEXT_TOKENS = 128000


def create_loop_state(
    user_id: str = "default",
    session_id: str = "default",
    max_loop_iterations: int = _DEFAULT_MAX_LOOP_ITERATIONS,
    max_tool_calls: int = _DEFAULT_MAX_TOOL_CALLS,
    max_context_tokens: int = _DEFAULT_MAX_CONTEXT_TOKENS,
) -> AgenticLoopState:
    now = datetime.now().isoformat()
    return AgenticLoopState(
        messages=[],
        user_id=user_id,
        session_id=session_id,
        next_agent=None,
        supervisor_reason=None,
        current_agent=None,
        agent_response=None,
        intent=None,
        loop_iteration=0,
        max_loop_iterations=max_loop_iterations,
        tool_call_count=0,
        max_tool_calls=max_tool_calls,
        tool_call_history=[],
        attempt_status=AttemptStatus.PENDING.value,
        attempt_retry_count=0,
        max_attempt_retries=_DEFAULT_MAX_ATTEMPT_RETRIES,
        compaction_count=0,
        max_compaction_count=_DEFAULT_MAX_COMPACTION_COUNT,
        context_token_estimate=0,
        max_context_tokens=max_context_tokens,
        loop_breaker_tripped=False,
        loop_breaker_reason=None,
        last_error=None,
        last_error_code=None,
        task_context=None,
        current_tasks=[],
        learning_progress=None,
        study_plans=[],
        reminders=[],
        weather_info=None,
        news_items=[],
        excel_files=[],
        current_excel=None,
        rag_context=None,
        rag_sources=[],
        needs_rag=None,
        force_search_context=None,
        metadata={},
        created_at=now,
        updated_at=now,
    )
