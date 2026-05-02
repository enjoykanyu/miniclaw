"""
MiniClaw News Enhancer
Enhances news with background knowledge and context
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime

from miniclaw.rag.types import Document
from miniclaw.rag.vectorstore import get_vectorstore
from miniclaw.tools.news import fetch_news
from miniclaw.utils.helpers import format_datetime


@dataclass
class EnhancedNews:
    title: str
    summary: str
    source: str
    url: str
    published_at: str
    background: Optional[str] = None
    related_news: List[Dict[str, Any]] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)


class NewsEnhancer:
    def __init__(
        self,
        collection_name: str = "news_knowledge",
    ):
        self.collection_name = collection_name
        self._vectorstore = None
    
    @property
    def vectorstore(self):
        if self._vectorstore is None:
            self._vectorstore = get_vectorstore(collection_name=self.collection_name)
        return self._vectorstore
    
    def store_news(self, news_items: List[Dict[str, Any]]) -> int:
        documents = []
        
        for news in news_items:
            content = f"{news.get('title', '')}\n{news.get('summary', '')}"
            
            document = Document(
                content=content,
                metadata={
                    "type": "news",
                    "title": news.get("title", ""),
                    "source": news.get("source", ""),
                    "url": news.get("url", ""),
                    "published_at": news.get("published_at", ""),
                    "category": news.get("category", "general"),
                    "stored_at": format_datetime(),
                },
            )
            documents.append(document)
        
        return self.vectorstore.add_documents(documents)
    
    def fetch_and_store(
        self,
        category: str = "all",
        count: int = 10,
    ) -> List[Dict[str, Any]]:
        news_items = fetch_news(category, count)
        
        self.store_news(news_items)
        
        return news_items
    
    def find_related_news(
        self,
        query: str,
        k: int = 5,
    ) -> List[Dict[str, Any]]:
        results = self.vectorstore.similarity_search(query, k=k)
        
        related = []
        for doc in results:
            related.append({
                "title": doc.metadata.get("title", ""),
                "source": doc.metadata.get("source", ""),
                "published_at": doc.metadata.get("published_at", ""),
                "relevance_content": doc.content[:200],
            })
        
        return related
    
    def enhance_news(
        self,
        news_item: Dict[str, Any],
        background_k: int = 3,
    ) -> EnhancedNews:
        title = news_item.get("title", "")
        summary = news_item.get("summary", "")
        
        query = f"{title} {summary}"
        related = self.find_related_news(query, k=background_k)
        
        background = None
        if related:
            background_parts = ["相关背景:"]
            for item in related:
                if item["title"] != title:
                    background_parts.append(f"- {item['title']} ({item['source']})")
            background = "\n".join(background_parts)
        
        keywords = self._extract_keywords(title + " " + summary)
        
        return EnhancedNews(
            title=title,
            summary=summary,
            source=news_item.get("source", ""),
            url=news_item.get("url", ""),
            published_at=news_item.get("published_at", ""),
            background=background,
            related_news=related,
            keywords=keywords,
        )
    
    def _extract_keywords(self, text: str) -> List[str]:
        stopwords = {"的", "是", "在", "了", "和", "与", "或", "这", "那", "有", "为", "以"}
        
        words = []
        for word in text.split():
            word = word.strip()
            if len(word) >= 2 and word not in stopwords:
                words.append(word)
        
        seen = set()
        keywords = []
        for word in words:
            if word not in seen:
                seen.add(word)
                keywords.append(word)
        
        return keywords[:5]
    
    def get_news_digest(
        self,
        category: str = "all",
        count: int = 5,
    ) -> str:
        news_items = self.fetch_and_store(category, count)
        
        if not news_items:
            return "暂无新闻"
        
        digest_parts = ["📰 今日新闻摘要\n"]
        
        for i, news in enumerate(news_items, 1):
            enhanced = self.enhance_news(news)
            
            digest_parts.append(f"\n{i}. {enhanced.title}")
            digest_parts.append(f"   来源: {enhanced.source}")
            
            if enhanced.summary:
                digest_parts.append(f"   摘要: {enhanced.summary[:100]}...")
            
            if enhanced.keywords:
                digest_parts.append(f"   关键词: {', '.join(enhanced.keywords)}")
        
        return "\n".join(digest_parts)
    
    def search_news_history(
        self,
        query: str,
        k: int = 10,
    ) -> List[Dict[str, Any]]:
        results = self.vectorstore.similarity_search(query, k=k)
        
        news_list = []
        for doc in results:
            news_list.append({
                "title": doc.metadata.get("title", ""),
                "source": doc.metadata.get("source", ""),
                "published_at": doc.metadata.get("published_at", ""),
                "content": doc.content,
            })
        
        return news_list
