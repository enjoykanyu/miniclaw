"""
MiniClaw Health Agent
Handles health reminders, break notifications, and wellness tips
"""

from datetime import datetime, timedelta

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool

from miniclaw.agents.base import BaseAgent
from miniclaw.core.state import MiniClawState
from miniclaw.utils.helpers import load_prompt_template, format_datetime, get_weekday_name


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
    name = "health_agent"
    description = "健康提醒助手，定时提醒休息、管理作息、提供健康建议"
    
    def __init__(self, llm=None, tools=None):
        if tools is None:
            tools = [set_reminder, get_greeting, get_health_tips]
        super().__init__(llm=llm, tools=tools)
        self._prompts = load_prompt_template("health")
    
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
                        if isinstance(result, dict):
                            tool_messages.append(f"⏰ 已设置提醒: {result.get('message', '')}")
                        else:
                            tool_messages.append(str(result))
            
            return "\n\n".join(tool_messages) if tool_messages else response.content
        
        return response.content
