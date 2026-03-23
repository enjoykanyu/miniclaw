"""
MiniClaw Task Agent
Handles TODO list management, task creation, and daily summaries
"""

from typing import Optional, Any
from datetime import datetime

from langchain_core.tools import tool

from miniclaw.agents.base import BaseAgent
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
    """
    任务管理智能体

    功能：
    - 创建、列出、完成任务
    - 生成每日任务报告
    """

    name = "task_agent"
    description = "任务管理助手，管理TODO清单、创建任务、生成每日报告"

    def __init__(self, llm=None, tools=None, use_react: bool = False):
        if tools is None:
            tools = [create_task, list_tasks, complete_task, generate_daily_summary]
        super().__init__(llm=llm, tools=tools, use_react=use_react)
        self._prompts = load_prompt_template("task")

    def _get_system_prompt(self) -> str:
        """获取任务管理的系统提示词"""
        return self._prompts.get("system", """你是任务管理助手，帮助用户管理TODO清单。

你可以：
1. 创建新任务（指定名称、描述、优先级、截止日期）
2. 列出所有任务（可按状态筛选）
3. 标记任务为完成
4. 生成每日任务完成报告

请友好、高效地帮助用户管理任务。""")

    def format_tool_result(self, tool_name: str, result: Any) -> Optional[str]:
        """
        自定义工具结果格式化

        针对任务管理工具的特殊格式化
        """
        if tool_name == "create_task" and isinstance(result, dict):
            if "error" in result:
                return f"❌ 创建任务失败: {result.get('message', '未知错误')}"

            priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(
                result.get("priority", ""), "⚪"
            )

            lines = [
                f"✅ 任务创建成功！",
                f"",
                f"📋 {result.get('name', '未命名任务')}",
                f"{priority_emoji} 优先级: {result.get('priority', '未设置')}",
            ]

            if result.get("deadline"):
                lines.append(f"📅 截止日期: {result['deadline']}")

            lines.append(f"🆔 任务ID: {result.get('id', 'N/A')}")

            return "\n".join(lines)

        elif tool_name == "list_tasks":
            return str(result)

        elif tool_name == "complete_task":
            return f"✅ {result}"

        elif tool_name == "generate_daily_summary" and isinstance(result, dict):
            if "error" in result:
                return f"❌ 生成报告失败: {result.get('message', '未知错误')}"

            lines = [
                f"📊 每日任务报告 ({result.get('date', '今天')})",
                f"",
                f"📋 总任务: {result.get('total_tasks', 0)}",
                f"✅ 已完成: {result.get('completed_tasks', 0)}",
                f"⏳ 待处理: {result.get('pending_tasks', 0)}",
                f"📈 完成率: {result.get('completion_rate', '0%')}",
                f"",
                f"💡 {result.get('summary', '')}",
            ]
            return "\n".join(lines)

        # 返回 None 使用默认格式化
        return None
