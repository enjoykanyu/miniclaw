"""
MiniClaw Info Agent
Handles weather queries, news fetching, and knowledge Q&A
"""

from typing import Optional, Any

from langchain_core.tools import tool

from miniclaw.agents.base import BaseAgent
from miniclaw.utils.helpers import load_prompt_template


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
    """
    信息获取智能体

    功能：
    - 查询天气信息
    - 获取新闻头条
    - 知识库搜索
    """

    name = "info_agent"
    description = "信息获取助手，查询天气、推送新闻、知识问答"

    def __init__(self, llm=None, tools=None, use_react: bool = False):
        if tools is None:
            tools = [get_weather, get_news, search_knowledge]
        super().__init__(llm=llm, tools=tools, use_react=use_react)
        self._prompts = load_prompt_template("info")

    def _get_system_prompt(self) -> str:
        """获取信息获取的系统提示词"""
        return self._prompts.get("system", """你是信息获取助手，帮助用户查询天气、新闻和知识。

你可以：
1. 查询指定城市的天气信息
2. 获取最新新闻头条（科技、财经、国际等分类）
3. 搜索知识库获取相关信息

请提供准确、及时的信息。""")

    def format_tool_result(self, tool_name: str, result: Any) -> Optional[str]:
        """
        自定义工具结果格式化

        针对信息获取工具的特殊格式化
        """
        if tool_name == "get_weather" and isinstance(result, dict):
            if "error" in result:
                return f"❌ {result.get('message', '无法获取天气信息')}"

            city = result.get('city', '未知城市')
            temp = result.get('temperature', 'N/A')
            condition = result.get('condition', 'N/A')
            humidity = result.get('humidity', 'N/A')

            # 天气表情
            weather_emoji = {
                "晴": "☀️", "多云": "⛅", "阴": "☁️",
                "雨": "🌧️", "雪": "❄️", "雷": "⛈️"
            }
            emoji = "🌤️"
            for key, em in weather_emoji.items():
                if key in str(condition):
                    emoji = em
                    break

            lines = [
                f"{emoji} {city}天气",
                f"",
                f"🌡️ 温度: {temp}°C",
                f"☁️ 天气: {condition}",
            ]

            if humidity != 'N/A':
                lines.append(f"💧 湿度: {humidity}%")

            if result.get('wind'):
                lines.append(f"🌬️ 风力: {result['wind']}")

            return "\n".join(lines)

        elif tool_name == "get_news" and isinstance(result, list):
            if not result:
                return "📰 暂无新闻"

            # 检查是否有错误
            if len(result) == 1 and isinstance(result[0], dict) and "error" in result[0]:
                return f"❌ {result[0].get('message', '无法获取新闻')}"

            lines = ["📰 最新新闻", ""]

            for i, item in enumerate(result[:5], 1):
                if isinstance(item, dict):
                    title = item.get('title', '无标题')
                    category = item.get('category', '')
                    category_emoji = {"tech": "💻", "finance": "💰", "world": "🌍"}.get(category, "📌")
                    lines.append(f"{i}. {category_emoji} {title}")

            return "\n".join(lines)

        elif tool_name == "search_knowledge":
            return str(result)

        # 返回 None 使用默认格式化
        return None
