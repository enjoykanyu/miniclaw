"""
TAVILY Tool - 联网搜索工具

当用户强制启用联网搜索时，此工具被注入到 Agent 的工具列表中。
模型会在回答前，先调用此工具获取最新的网络信息。

实现方式：使用 Tavily 或类似的搜索 API 进行实时网络搜索。
"""

from typing import Optional

from langchain_core.tools import tool
from loguru import logger

from miniclaw.config.settings import settings


@tool
def tavily(query: str, max_results: int = 5) -> str:
    """
    联网搜索工具。当用户需要获取最新信息、实时数据或网络内容时使用此工具。

    适用场景：
    - 查询最新新闻、事件
    - 获取实时数据（股价、天气、比赛结果等）
    - 搜索特定知识或技术文档
    - 验证某个信息的准确性

    Args:
        query: 搜索查询语句，应该清晰、具体
        max_results: 返回结果数量（默认5条）

    Returns:
        搜索结果的摘要，包含标题、摘要和来源链接
    """
    logger.info(f"Trail Tool: {query}")

    try:
        # 优先使用 Tavily API（从统一配置读取）
        tavily_key = settings.TAVILY_API_KEY
        if tavily_key:
            return _search_tavily(query, max_results, tavily_key)

        # 降级：使用 DuckDuckGo 搜索（无需 API Key）
        return _search_duckduckgo(query, max_results)

    except Exception as e:
        return f"搜索失败: {str(e)}。请检查网络连接或搜索服务配置。"


def _search_tavily(query: str, max_results: int, api_key: str) -> str:
    """使用 Tavily API 进行搜索"""
    import requests

    response = requests.post(
        "https://api.tavily.com/search",
        headers={"Content-Type": "application/json"},
        json={
            "api_key": api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": "basic",
        },
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()

    results = data.get("results", [])
    if not results:
        return f"未找到与 '{query}' 相关的网络内容。"

    lines = [f"🔍 联网搜索结果: '{query}'", ""]
    for i, result in enumerate(results[:max_results], 1):
        title = result.get("title", "无标题")
        content = result.get("content", "")
        url = result.get("url", "")
        lines.append(f"{i}. {title}")
        if content:
            lines.append(f"   {content[:200]}...")
        if url:
            lines.append(f"   来源: {url}")
        lines.append("")

    return "\n".join(lines)


def _search_duckduckgo(query: str, max_results: int) -> str:
    """使用 DuckDuckGo 进行搜索（无需 API Key）"""
    try:
        from duckduckgo_search import DDGS

        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))

        if not results:
            return f"未找到与 '{query}' 相关的网络内容。"

        lines = [f"🔍 联网搜索结果: '{query}'", ""]
        for i, result in enumerate(results[:max_results], 1):
            title = result.get("title", "无标题")
            body = result.get("body", "")
            href = result.get("href", "")
            lines.append(f"{i}. {title}")
            if body:
                lines.append(f"   {body[:200]}...")
            if href:
                lines.append(f"   来源: {href}")
            lines.append("")

        return "\n".join(lines)

    except ImportError:
        return (
            "联网搜索需要安装依赖: pip install duckduckgo-search\n"
            "或者配置 TAVILY_API_KEY 环境变量使用 Tavily 搜索。"
        )
    except Exception as e:
        return f"DuckDuckGo 搜索失败: {str(e)}"
