"""
MiniClaw Learning Agent
Handles study planning, progress tracking, and quiz generation
"""

from typing import List, Optional
from datetime import datetime, timedelta

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool

from miniclaw.agents.base import BaseAgent
from miniclaw.core.state import MiniClawState
from miniclaw.utils.helpers import load_prompt_template, format_datetime
from miniclaw.utils.llm import get_smart_llm


@tool
def create_study_plan(goal: str, duration: str, daily_hours: int, mode: str) -> dict:
    """
    Create a study plan based on user's learning goal.
    
    Args:
        goal: The learning goal (e.g., "Learn Python programming")
        duration: Time range (e.g., "2 weeks", "1 month")
        daily_hours: Available hours per day for study
        mode: Learning mode - "daily", "intensive", or "longterm"
    
    Returns:
        A structured study plan with stages and tasks
    """
    stages = []
    total_days = 14 if "week" in duration.lower() else 30
    
    if "python" in goal.lower():
        stages = [
            {"name": "基础语法", "days": total_days // 4, "tasks": ["变量与数据类型", "控制流", "函数", "模块"]},
            {"name": "进阶特性", "days": total_days // 4, "tasks": ["面向对象", "异常处理", "文件操作", "装饰器"]},
            {"name": "实战项目", "days": total_days // 4, "tasks": ["项目规划", "编码实现", "测试调试", "优化完善"]},
            {"name": "复习巩固", "days": total_days // 4, "tasks": ["知识回顾", "练习题", "总结笔记"]},
        ]
    else:
        stages = [
            {"name": "基础阶段", "days": total_days // 3, "tasks": ["基础概念", "核心知识"]},
            {"name": "进阶阶段", "days": total_days // 3, "tasks": ["深入理解", "实践应用"]},
            {"name": "巩固阶段", "days": total_days // 3, "tasks": ["复习总结", "项目实战"]},
        ]
    
    return {
        "goal": goal,
        "duration": duration,
        "total_days": total_days,
        "daily_hours": daily_hours,
        "mode": mode,
        "stages": stages,
        "created_at": format_datetime(),
    }


@tool
def generate_excel_plan(plan: dict, filename: str) -> str:
    """
    Generate an Excel file from the study plan.
    
    Args:
        plan: The study plan dictionary
        filename: Output filename (without extension)
    
    Returns:
        Path to the generated Excel file
    """
    from miniclaw.tools.excel import create_study_excel
    
    filepath = create_study_excel(plan, filename)
    return f"学习计划已生成: {filepath}"


@tool
def schedule_review(plan_id: str, stage: int) -> dict:
    """
    Schedule review sessions based on Ebbinghaus forgetting curve.
    
    Args:
        plan_id: The study plan ID
        stage: Current stage number
    
    Returns:
        Review schedule with recommended dates
    """
    now = datetime.now()
    
    review_intervals = [1, 2, 4, 7, 15, 30]
    
    reviews = []
    for i, days in enumerate(review_intervals):
        review_date = now + timedelta(days=days)
        reviews.append({
            "review_num": i + 1,
            "date": format_datetime(review_date, "%Y-%m-%d"),
            "interval_days": days,
        })
    
    return {
        "plan_id": plan_id,
        "stage": stage,
        "review_schedule": reviews,
    }


class LearningAgent(BaseAgent):
    name = "learning_agent"
    description = "学习规划助手，帮助制定学习计划、追踪进度、安排复习"
    
    def __init__(self, llm=None, tools=None):
        if tools is None:
            tools = [create_study_plan, generate_excel_plan, schedule_review]
        super().__init__(llm=llm, tools=tools)
        self._prompts = load_prompt_template("learning")
    
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
                        tool_messages.append(f"[{tool_name}] {result}")
            
            return "\n".join(tool_messages) if tool_messages else response.content
        
        return response.content
