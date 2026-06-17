from langchain_core.tools import tool


@tool
def get_news(topic: str = "general") -> str:
    """获取指定主题的新闻信息"""
    return f"暂无{topic}类别的实时新闻数据，请配置新闻API后使用。"


async def fetch_news(topic: str = "general") -> str:
    return get_news.invoke({"topic": topic})


async def fetch_news_async(topic: str = "general") -> str:
    return await fetch_news(topic)
