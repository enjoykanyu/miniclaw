"""
MiniClaw Chat Agent
Handles general conversation and fallback responses
"""

from langchain_core.messages import HumanMessage, SystemMessage

from miniclaw.agents.base import BaseAgent
from miniclaw.core.state import MiniClawState


CHAT_SYSTEM_PROMPT = """你是MiniClaw，一个友好、智能的个人助手。

你的能力包括：
1. 学习规划 - 帮助制定学习计划、追踪进度
2. 任务管理 - 管理TODO清单、提醒任务
3. 信息获取 - 查询天气、推送新闻
4. 健康提醒 - 定时提醒休息、作息管理
5. 数据处理 - Excel操作、数据分析

请用简洁、友好的方式回应用户。如果用户需要特定功能，引导他们使用相应的命令。

例如：
- "帮我制定一个Python学习计划" - 学习规划
- "创建任务：明天开会" - 任务管理
- "今天天气怎么样" - 信息获取
- "提醒我每小时站起来休息" - 健康提醒
- "新建一个Excel表格" - 数据处理
"""


class ChatAgent(BaseAgent):
    name = "chat_agent"
    description = "日常聊天助手，处理一般对话和引导用户使用功能"
    
    def __init__(self, llm=None, tools=None):
        super().__init__(llm=llm, tools=tools)
    
    async def process(self, state: MiniClawState) -> str:
        user_message = self.get_last_user_message(state)
        
        messages = [
            SystemMessage(content=CHAT_SYSTEM_PROMPT),
            HumanMessage(content=user_message),
        ]
        
        response = await self.llm.ainvoke(messages)
        
        return response.content
