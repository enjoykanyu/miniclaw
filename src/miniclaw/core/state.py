"""
MiniClaw State Definition
Defines the state schema for LangGraph workflow
"""

from typing import TypedDict, List, Optional, Annotated, Any
from datetime import datetime
from langgraph.graph import add_messages


class TaskItem(TypedDict):
    id: str
    name: str
    description: str
    priority: str
    status: str
    deadline: Optional[str]
    created_at: str
    completed_at: Optional[str]


class LearningProgress(TypedDict):
    plan_id: str
    goal: str
    current_stage: int
    total_stages: int
    completed_tasks: int
    total_tasks: int
    last_review: Optional[str]
    next_review: Optional[str]


class ReminderItem(TypedDict):
    id: str
    type: str
    message: str
    scheduled_time: str
    is_sent: bool


class MiniClawState(TypedDict):
    messages: Annotated[list, add_messages]
    user_id: str
    session_id: str
    
    intent: Optional[str]
    current_agent: Optional[str]
    agent_response: Optional[str]
    
    task_context: Optional[dict]
    current_tasks: Optional[List[TaskItem]]
    
    learning_progress: Optional[LearningProgress]
    study_plans: Optional[List[dict]]
    
    reminders: Optional[List[ReminderItem]]
    
    weather_info: Optional[dict]
    news_items: Optional[List[dict]]
    
    excel_files: Optional[List[str]]
    current_excel: Optional[str]
    
    metadata: Optional[dict]
    created_at: Optional[str]
    updated_at: Optional[str]


def create_initial_state(user_id: str, session_id: str) -> MiniClawState:
    now = datetime.now().isoformat()
    return MiniClawState(
        messages=[],
        user_id=user_id,
        session_id=session_id,
        intent=None,
        current_agent=None,
        agent_response=None,
        task_context=None,
        current_tasks=[],
        learning_progress=None,
        study_plans=[],
        reminders=[],
        weather_info=None,
        news_items=[],
        excel_files=[],
        current_excel=None,
        metadata={},
        created_at=now,
        updated_at=now,
    )
