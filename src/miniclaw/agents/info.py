"""
MiniClaw Info Agent
Handles weather queries, news fetching, and knowledge Q&A
"""

from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool

from miniclaw.agents.base import BaseAgent
from miniclaw.core.state import MiniClawState
from miniclaw.utils.helpers import load_prompt_template
from miniclaw.config.settings import settings


@tool
def get_weather(city: str) -> dict:
    """
    Get current weather information for a city.
    
    Args:
        city: City name (e.g., "Beijing", "Shanghai")
    
    Returns:
        Weather information including temperature, conditions, and forecast
    """
    from miniclaw.tools.weather import fetch_weather
    
    try:
        weather_data = fetch_weather(city)
        return weather_data
    except Exception as e:
        return {"error": str(e), "city": city, "message": "无法获取天气信息，请稍后重试"}


@tool
def get_news(category: str = "all", count: int = 5) -> list:
    """
    Get latest news headlines.
    
    Args:
        category: News category - "tech", "world", "finance", or "all"
        count: Number of news items to return (default 5)
    
    Returns:
        List of news items with title, summary, and link
    """
    from miniclaw.tools.news import fetch_news
    
    try:
        news_data = fetch_news(category, count)
        return news_data
    except Exception as e:
        return [{"error": str(e), "message": "无法获取新闻，请稍后重试"}]


@tool
def search_knowledge(query: str) -> str:
    """
    Search knowledge base for relevant information.
    
    Args:
        query: Search query
    
    Returns:
        Relevant information from knowledge base
    """
    return f"知识库搜索结果: 关于 '{query}' 的相关信息暂未找到，请尝试其他关键词。"


class InfoAgent(BaseAgent):
    name = "info_agent"
    description = "信息获取助手，查询天气、推送新闻、知识问答"
    
    def __init__(self, llm=None, tools=None):
        if tools is None:
            tools = [get_weather, get_news, search_knowledge]
        super().__init__(llm=llm, tools=tools)
        self._prompts = load_prompt_template("info")
    
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
                            if "error" in result:
                                tool_messages.append(f"❌ {result.get('message', '操作失败')}")
                            elif "temperature" in result:
                                tool_messages.append(
                                    f"🌤️ {result.get('city', '')}天气:\n"
                                    f"温度: {result.get('temperature', 'N/A')}°C\n"
                                    f"天气: {result.get('condition', 'N/A')}\n"
                                    f"湿度: {result.get('humidity', 'N/A')}%"
                                )
                            else:
                                tool_messages.append(str(result))
                        elif isinstance(result, list):
                            for item in result[:5]:
                                if isinstance(item, dict) and "title" in item:
                                    tool_messages.append(f"📰 {item['title']}")
                        else:
                            tool_messages.append(str(result))
            
            return "\n\n".join(tool_messages) if tool_messages else response.content
        
        return response.content
