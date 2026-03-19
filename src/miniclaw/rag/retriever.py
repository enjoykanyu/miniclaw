"""
MiniClaw RAG Retriever
Unified retrieval interface for all RAG components
"""

from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass, field

from miniclaw.rag.vectorstore import get_vectorstore
from miniclaw.rag.pdf_loader import PDFKnowledgeBase
from miniclaw.rag.memory_store import MemoryStore, LongTermMemory
from miniclaw.rag.news_enhancer import NewsEnhancer
from miniclaw.config.settings import settings


@dataclass
class RetrievalResult:
    content: str
    source: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class RAGRetriever:
    def __init__(
        self,
        use_pdf: bool = True,
        use_memory: bool = True,
        use_news: bool = True,
        use_long_term: bool = True,
    ):
        self.use_pdf = use_pdf
        self.use_memory = use_memory
        self.use_news = use_news
        self.use_long_term = use_long_term
        
        self._pdf_kb = None
        self._memory_store = None
        self._news_enhancer = None
        self._long_term_memory = None
    
    @property
    def pdf_kb(self) -> PDFKnowledgeBase:
        if self._pdf_kb is None:
            self._pdf_kb = PDFKnowledgeBase()
        return self._pdf_kb
    
    @property
    def memory_store(self) -> MemoryStore:
        if self._memory_store is None:
            self._memory_store = MemoryStore()
        return self._memory_store
    
    @property
    def news_enhancer(self) -> NewsEnhancer:
        if self._news_enhancer is None:
            self._news_enhancer = NewsEnhancer()
        return self._news_enhancer
    
    @property
    def long_term_memory(self) -> LongTermMemory:
        if self._long_term_memory is None:
            self._long_term_memory = LongTermMemory()
        return self._long_term_memory
    
    def retrieve(
        self,
        query: str,
        k: int = 5,
    ) -> List[RetrievalResult]:
        results = []
        
        if self.use_memory:
            memory_results = self._retrieve_from_memory(query, k)
            results.extend(memory_results)
        
        if self.use_pdf:
            pdf_results = self._retrieve_from_pdf(query, k)
            results.extend(pdf_results)
        
        if self.use_news:
            news_results = self._retrieve_from_news(query, k)
            results.extend(news_results)
        
        if self.use_long_term:
            ltm_results = self._retrieve_from_long_term(query, k)
            results.extend(ltm_results)
        
        results.sort(key=lambda x: x.score, reverse=True)
        
        return results[:k]
    
    def _retrieve_from_memory(
        self,
        query: str,
        k: int,
    ) -> List[RetrievalResult]:
        memories = self.memory_store.search_memories(query, k=k)
        
        return [
            RetrievalResult(
                content=m["content"],
                source="conversation_memory",
                score=0.8,
                metadata={"role": m["role"], "timestamp": m["timestamp"]},
            )
            for m in memories
        ]
    
    def _retrieve_from_pdf(
        self,
        query: str,
        k: int,
    ) -> List[RetrievalResult]:
        pdf_results = self.pdf_kb.query(query, k=k)
        
        return [
            RetrievalResult(
                content=r["content"],
                source=f"pdf:{r['source']}",
                score=0.7,
                metadata={"page": r["page"]},
            )
            for r in pdf_results
        ]
    
    def _retrieve_from_news(
        self,
        query: str,
        k: int,
    ) -> List[RetrievalResult]:
        news_results = self.news_enhancer.search_news_history(query, k=k)
        
        return [
            RetrievalResult(
                content=n["content"],
                source=f"news:{n['source']}",
                score=0.6,
                metadata={
                    "title": n["title"],
                    "published_at": n["published_at"],
                },
            )
            for n in news_results
        ]
    
    def _retrieve_from_long_term(
        self,
        query: str,
        k: int,
    ) -> List[RetrievalResult]:
        facts = self.long_term_memory.recall(query, k=k)
        
        return [
            RetrievalResult(
                content=f["content"],
                source=f"long_term:{f['type']}",
                score=0.9,
                metadata={
                    "category": f["category"],
                    "importance": f["importance"],
                },
            )
            for f in facts
        ]
    
    def get_context(
        self,
        query: str,
        k: int = 5,
        max_length: int = 2000,
    ) -> str:
        results = self.retrieve(query, k)
        
        if not results:
            return ""
        
        context_parts = ["[检索到的相关上下文]"]
        current_length = 0
        
        for result in results:
            content = result.content
            if current_length + len(content) > max_length:
                content = content[:max_length - current_length]
            
            context_parts.append(f"\n来源: {result.source}")
            context_parts.append(content)
            
            current_length += len(content)
            if current_length >= max_length:
                break
        
        return "\n".join(context_parts)
    
    def add_conversation(
        self,
        user_message: str,
        assistant_message: str,
        session_id: str = "default",
    ) -> None:
        self.memory_store.add_user_message(user_message, session_id)
        self.memory_store.add_assistant_message(assistant_message, session_id)
    
    def add_fact(
        self,
        fact: str,
        category: str = "general",
        importance: int = 1,
    ) -> None:
        self.long_term_memory.store_fact(fact, category, importance)
    
    def add_preference(
        self,
        preference: str,
        category: str = "general",
    ) -> None:
        self.long_term_memory.store_preference(preference, category)
    
    def add_pdf_document(self, file_path: str) -> int:
        return self.pdf_kb.add_pdf(file_path)
    
    def add_pdf_directory(self, directory: str = None) -> int:
        return self.pdf_kb.add_directory(directory)


def create_rag_retriever(
    use_pdf: bool = True,
    use_memory: bool = True,
    use_news: bool = True,
    use_long_term: bool = True,
) -> RAGRetriever:
    return RAGRetriever(
        use_pdf=use_pdf,
        use_memory=use_memory,
        use_news=use_news,
        use_long_term=use_long_term,
    )
