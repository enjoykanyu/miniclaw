from langchain_community.tools.tavily_search import TavilySearchResults
from miniclaw.config.settings import settings

async def _search_tavily(query: str, max_results: int = 5) -> str:
    if not settings.TAVILY_API_KEY:
        return ""
    try:
        tool = TavilySearchResults(max_results=max_results, tavily_api_key=settings.TAVILY_API_KEY)
        results = await tool.ainvoke(query)
        return str(results)
    except Exception:
        return ""

async def _search_duckduckgo(query: str, max_results: int = 5) -> str:
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if not results:
            return ""
        parts = []
        for r in results:
            parts.append(f"- {r.get('title', '')}: {r.get('body', '')} ({r.get('href', '')})")
        return "\n".join(parts)
    except Exception:
        return ""
