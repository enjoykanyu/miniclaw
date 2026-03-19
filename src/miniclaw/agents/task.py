"""
MiniClaw Task Agent
Handles TODO list management, task creation, and daily summaries
"""

from typing import Optional
from datetime import datetime

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool

from miniclaw.agents.base import BaseAgent
from miniclaw.core.state import MiniClawState
from miniclaw.utils.helpers import load_prompt_template, format_datetime


@tool
def create_task(name: str, description: str, priority: str, deadline: Optional[str] = None) -> dict:
    """
    Create a new task.
    
    Args:
        name: Task name
        description: Task description
        priority: Priority level - "high", "medium", or "low"
        deadline: Optional deadline in YYYY-MM-DD format
    
    Returns:
        Created task details
    """
    return {
        "id": f"task_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "name": name,
        "description": description,
        "priority": priority,
        "status": "pending",
        "deadline": deadline,
        "created_at": format_datetime(),
    }


@tool
def list_tasks(status: Optional[str] = None) -> str:
    """
    List all tasks, optionally filtered by status.
    
    Args:
        status: Optional filter - "pending", "in_progress", or "completed"
    
    Returns:
        Formatted task list
    """
    return f"任务列表（状态筛选: {status or '全部'}）:\n暂无任务"


@tool
def complete_task(task_id: str) -> str:
    """
    Mark a task as completed.
    
    Args:
        task_id: The task ID to mark as completed
    
    Returns:
        Confirmation message
    """
    return f"任务 {task_id} 已标记为完成"


@tool
def generate_daily_summary(date: str) -> dict:
    """
    Generate a daily task completion summary.
    
    Args:
        date: Date in YYYY-MM-DD format
    
    Returns:
        Daily summary with statistics
    """
    return {
        "date": date,
        "total_tasks": 0,
        "completed_tasks": 0,
        "pending_tasks": 0,
        "completion_rate": "0%",
        "summary": "今日暂无任务记录",
    }


class TaskAgent(BaseAgent):
    name = "task_agent"
    description = "任务管理助手，管理TODO清单、创建任务、生成每日报告"
    
    def __init__(self, llm=None, tools=None):
        if tools is None:
            tools = [create_task, list_tasks, complete_task, generate_daily_summary]
        super().__init__(llm=llm, tools=tools)
        self._prompts = load_prompt_template("task")
    
    async def process(self, state: MiniClawState) -> str:
        user_message = self.get_last_user_message(state)
        
        system_prompt = self._prompts.get("system", "")
        
        llm_with_tools = self.bind_tools()
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ]
        
        response = await llm_with_tools.ainvoke(messages)
        
        if hasattr(response, "tool_calls") and response.tool_calls:
            tool_messages = []
            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                
                for tool in self._tools:
                    if tool.name == tool_name:
                        result = tool.invoke(tool_args)
                        tool_messages.append(f"{result}")
            
            return "\n".join(tool_messages) if tool_messages else response.content
        
        return response.content
