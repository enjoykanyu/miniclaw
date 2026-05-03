"""
MiniClaw Learning Agent - Worker Agent
Handles study planning, progress tracking, and quiz generation
"""

from typing import List, Optional, Any
from datetime import datetime, timedelta

from langchain_core.tools import tool

from miniclaw.agents.worker import BaseWorker
from miniclaw.utils.helpers import load_prompt_template, format_datetime


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


class LearningAgent(BaseWorker):
    """
    学习规划 Worker Agent

    功能：
    - 制定学习计划
    - 生成 Excel 学习计划表
    - 安排艾宾浩斯复习
    """

    name = "learning"
    description = "学习规划助手，帮助制定学习计划、追踪进度、安排复习"

    def __init__(self, llm=None, tools=None, use_react: bool = False):
        if tools is None:
            tools = [create_study_plan, generate_excel_plan, schedule_review]
        super().__init__(llm=llm, tools=tools, use_react=use_react)
        self._prompts = load_prompt_template("learning")

    def _get_system_prompt(self) -> str:
        """获取学习规划的系统提示词"""
        return self._prompts.get("system", """你是学习规划助手，帮助用户制定学习计划和管理学习进度。

你可以：
1. 根据学习目标制定详细的学习计划
2. 生成 Excel 格式的学习计划表
3. 基于艾宾浩斯遗忘曲线安排复习计划

请帮助用户高效、系统地学习。""")

    def format_tool_result(self, tool_name: str, result: Any) -> Optional[str]:
        """自定义工具结果格式化"""
        if tool_name == "create_study_plan" and isinstance(result, dict):
            if "error" in result:
                return f"❌ 创建学习计划失败: {result.get('message', '未知错误')}"

            lines = [
                f"📚 学习计划: {result.get('goal', '未命名')}",
                f"",
                f"⏱️ 学习周期: {result.get('duration', '未设置')} ({result.get('total_days', 0)}天)",
                f"📅 每日学习: {result.get('daily_hours', 0)} 小时",
                f"🎯 学习模式: {result.get('mode', 'daily')}",
                f"",
                "📋 学习阶段:",
            ]

            for i, stage in enumerate(result.get('stages', []), 1):
                stage_name = stage.get('name', f'阶段{i}')
                days = stage.get('days', 0)
                tasks = stage.get('tasks', [])
                lines.append(f"  {i}. {stage_name} ({days}天)")
                for task in tasks:
                    lines.append(f"     - {task}")

            return "\n".join(lines)

        elif tool_name == "generate_excel_plan":
            return f"📊 {result}"

        elif tool_name == "schedule_review" and isinstance(result, dict):
            if "error" in result:
                return f"❌ 安排复习失败: {result.get('message', '未知错误')}"

            lines = [
                f"🔄 艾宾浩斯复习计划",
                f"",
                f"计划ID: {result.get('plan_id', 'N/A')}",
                f"当前阶段: {result.get('stage', 1)}",
                f"",
                "📅 复习时间表:",
            ]

            for review in result.get('review_schedule', []):
                lines.append(f"  第{review.get('review_num')}次复习: {review.get('date')} (间隔{review.get('interval_days')}天)")

            return "\n".join(lines)

        return None
