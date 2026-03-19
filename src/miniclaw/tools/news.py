"""
MiniClaw News Tools
Fetches news from various sources
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import httpx

from miniclaw.config.settings import settings


async def fetch_news_async(category: str = "all", count: int = 5) -> List[Dict[str, Any]]:
    api_key = settings.NEWS_API_KEY
    
    if not api_key:
        return [
            {
                "title": "新闻API未配置",
                "summary": "请配置 NEWS_API_KEY 环境变量以获取新闻",
                "source": "系统提示",
                "published_at": datetime.now().strftime("%Y-%m-%d"),
                "url": "",
            }
        ]
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://newsapi.org/v2/top-headlines",
                params={
                    "apiKey": api_key,
                    "category": category if category != "all" else "general",
                    "pageSize": count,
                    "language": "zh",
                },
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()
            
            articles = data.get("articles", [])
            return [
                {
                    "title": article.get("title", ""),
                    "summary": (article.get("description", "") or "")[:100],
                    "source": article.get("source", {}).get("name", ""),
                    "published_at": article.get("publishedAt", "")[:10] if article.get("publishedAt") else "",
                    "url": article.get("url", ""),
                }
                for article in articles[:count]
            ]
    except Exception as e:
        return [
            {
                "title": "获取新闻失败",
                "summary": str(e),
                "source": "错误",
                "published_at": datetime.now().strftime("%Y-%m-%d"),
                "url": "",
            }
        ]


def fetch_news(category: str = "all", count: int = 5) -> List[Dict[str, Any]]:
    api_key = settings.NEWS_API_KEY
    
    if not api_key:
        return [
            {
                "title": "新闻API未配置",
                "summary": "请配置 NEWS_API_KEY 环境变量以获取新闻",
                "source": "系统提示",
                "published_at": datetime.now().strftime("%Y-%m-%d"),
                "url": "",
            }
        ]
    
    try:
        with httpx.Client() as client:
            response = client.get(
                "https://newsapi.org/v2/top-headlines",
                params={
                    "apiKey": api_key,
                    "category": category if category != "all" else "general",
                    "pageSize": count,
                    "language": "zh",
                },
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()
            
            articles = data.get("articles", [])
            return [
                {
                    "title": article.get("title", ""),
                    "summary": (article.get("description", "") or "")[:100],
                    "source": article.get("source", {}).get("name", ""),
                    "published_at": article.get("publishedAt", "")[:10] if article.get("publishedAt") else "",
                    "url": article.get("url", ""),
                }
                for article in articles[:count]
            ]
    except Exception as e:
        return [
            {
                "title": "获取新闻失败",
                "summary": str(e),
                "source": "错误",
                "published_at": datetime.now().strftime("%Y-%m-%d"),
                "url": "",
            }
        ]


def format_news_summary(news_list: List[Dict[str, Any]]) -> str:
    if not news_list:
        return "暂无新闻"
    
    lines = ["📰 今日新闻摘要\n"]
    for i, news in enumerate(news_list, 1):
        lines.append(f"{i}. {news.get('title', '无标题')}")
        if news.get('summary'):
            lines.append(f"   {news['summary']}")
        lines.append(f"   来源: {news.get('source', '未知')} | {news.get('published_at', '')}")
        lines.append("")
    
    return "\n".join(lines)
