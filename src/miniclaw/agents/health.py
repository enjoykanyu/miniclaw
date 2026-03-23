"""
MiniClaw Health Agent
Handles health reminders, break notifications, and wellness tips
"""

from datetime import datetime, timedelta
from typing import Any, Optional

from langchain_core.tools import tool

from miniclaw.agents.base import BaseAgent
from miniclaw.utils.helpers import load_prompt_template, format_datetime


@tool
def set_reminder(reminder_type: str, message: str, minutes: int = 60) -> dict:
    """
    Set a health reminder.

    Args:
        reminder_type: Type of reminder - "standup", "water", "eye_exercise", "break"
        message: Custom reminder message
        minutes: Interval in minutes

    Returns:
        Reminder details
    """
    return {
        "id": f"reminder_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "type": reminder_type,
        "message": message,
        "interval_minutes": minutes,
        "created_at": format_datetime(),
        "status": "active",
    }


@tool
def get_greeting(greeting_type: str) -> str:
    """
    Get a time-appropriate greeting message.

    Args:
        greeting_type: Type of greeting - "morning", "noon", "night"

    Returns:
        Greeting message
    """
    now = datetime.now()
    hour = now.hour

    greetings = {
        "morning": [
            "早上好！新的一天开始了，祝你精力充沛！",
            "早安！又是美好的一天，加油！",
            "早上好！记得吃早餐哦～",
        ],
        "noon": [
            "中午好！该休息一下了，记得吃午饭。",
            "午安！适当午休可以恢复精力。",
            "中午好！站起来活动一下吧。",
        ],
        "night": [
            "晚上好！今天辛苦了，早点休息。",
            "晚安！充足的睡眠是健康的基石。",
            "夜深了，该准备休息了，明天继续加油！",
        ],
    }

    if greeting_type == "auto":
        if 5 <= hour < 12:
            greeting_type = "morning"
        elif 12 <= hour < 18:
            greeting_type = "noon"
        else:
            greeting_type = "night"

    messages = greetings.get(greeting_type, greetings["morning"])
    return messages[hour % len(messages)]


@tool
def get_health_tips(situation: str) -> str:
    """
    Get health tips based on current situation.

    Args:
        situation: Current situation - "sitting", "tired", "stressed", "eye_strain"

    Returns:
        Health tips and recommendations
    """
    tips = {
        "sitting": "你已经坐了很久了！建议：\n1. 站起来活动5-10分钟\n2. 做一些简单的伸展运动\n3. 看看远处的风景放松眼睛",
        "tired": "看起来你有些疲惫。建议：\n1. 适当休息一下\n2. 喝杯水或茶\n3. 深呼吸几次",
        "stressed": "压力可能会影响健康。建议：\n1. 深呼吸放松\n2. 听听舒缓的音乐\n3. 和朋友聊聊天",
        "eye_strain": "眼睛疲劳了吗？建议：\n1. 远眺窗外风景\n2. 做眼保健操\n3. 用热毛巾敷眼",
    }

    return tips.get(situation, "保持健康的生活习惯，定时休息，多喝水！")


class HealthAgent(BaseAgent):
    """
    健康提醒智能体

    功能：
    - 设置健康提醒（站立、喝水、眼保健操）
    - 根据时间提供问候
    - 提供健康建议
    """

    name = "health_agent"
    description = "健康提醒助手，定时提醒休息、管理作息、提供健康建议"

    def __init__(self, llm=None, tools=None, use_react: bool = False):
        if tools is None:
            tools = [set_reminder, get_greeting, get_health_tips]
        super().__init__(llm=llm, tools=tools, use_react=use_react)
        self._prompts = load_prompt_template("health")

    def _get_system_prompt(self) -> str:
        """获取健康提醒的系统提示词"""
        return self._prompts.get("system", """你是健康提醒助手，帮助用户保持健康的工作和生活习惯。

你可以：
1. 设置健康提醒（定时站立、喝水、眼保健操等）
2. 根据时间提供合适的问候
3. 根据当前状况提供健康建议

请关注用户的身心健康。""")

    def format_tool_result(self, tool_name: str, result: Any) -> Optional[str]:
        """
        自定义工具结果格式化

        针对健康提醒工具的特殊格式化
        """
        if tool_name == "set_reminder" and isinstance(result, dict):
            if "error" in result:
                return f"❌ 设置提醒失败: {result.get('message', '未知错误')}"

            reminder_type = result.get('type', 'reminder')
            type_emoji = {
                "standup": "🧍",
                "water": "💧",
                "eye_exercise": "👁️",
                "break": "☕"
            }.get(reminder_type, "⏰")

            lines = [
                f"{type_emoji} 提醒已设置！",
                f"",
                f"📝 内容: {result.get('message', '')}",
                f"⏱️ 间隔: 每 {result.get('interval_minutes', 60)} 分钟",
                f"🆔 提醒ID: {result.get('id', 'N/A')}",
            ]

            return "\n".join(lines)

        elif tool_name == "get_greeting":
            return f"👋 {result}"

        elif tool_name == "get_health_tips":
            return f"💡 健康建议:\n{result}"

        # 返回 None 使用默认格式化
        return None
