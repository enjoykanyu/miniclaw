"""
MiniClaw Memory Store
Handles conversation history and memory retrieval
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
import json

from miniclaw.rag.types import Document
from miniclaw.rag.vectorstore import get_vectorstore
from miniclaw.utils.helpers import format_datetime


@dataclass
class Memory:
    content: str
    role: str
    timestamp: str
    session_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class MemoryStore:
    def __init__(
        self,
        collection_name: str = "conversation_memory",
        max_memories: int = 100,
    ):
        self.collection_name = collection_name
        self.max_memories = max_memories
        self._vectorstore = None
        self._recent_memories: List[Memory] = []
    
    @property
    def vectorstore(self):
        if self._vectorstore is None:
            self._vectorstore = get_vectorstore(collection_name=self.collection_name)
        return self._vectorstore
    
    def add_memory(
        self,
        content: str,
        role: str,
        session_id: str,
        metadata: Dict[str, Any] = None,
    ) -> None:
        memory = Memory(
            content=content,
            role=role,
            timestamp=format_datetime(),
            session_id=session_id,
            metadata=metadata or {},
        )
        
        self._recent_memories.append(memory)
        
        if len(self._recent_memories) > self.max_memories:
            self._recent_memories = self._recent_memories[-self.max_memories:]
        
        document = Document(
            content=f"{role}: {content}",
            metadata={
                "role": role,
                "timestamp": memory.timestamp,
                "session_id": session_id,
                **(metadata or {}),
            },
        )
        
        self.vectorstore.add_documents([document])
    
    def add_user_message(self, content: str, session_id: str = "default") -> None:
        self.add_memory(content, "user", session_id)
    
    def add_assistant_message(self, content: str, session_id: str = "default") -> None:
        self.add_memory(content, "assistant", session_id)
    
    def get_recent_memories(self, n: int = 10) -> List[Memory]:
        return self._recent_memories[-n:]
    
    def get_recent_context(self, n: int = 10) -> str:
        recent = self.get_recent_memories(n)
        
        if not recent:
            return ""
        
        context_parts = []
        for memory in recent:
            context_parts.append(f"{memory.role}: {memory.content}")
        
        return "\n".join(context_parts)
    
    def search_memories(
        self,
        query: str,
        k: int = 5,
    ) -> List[Dict[str, Any]]:
        results = self.vectorstore.similarity_search(query, k=k)
        
        memories = []
        for doc in results:
            role = doc.metadata.get("role", "unknown")
            timestamp = doc.metadata.get("timestamp", "")
            
            content = doc.content
            if content.startswith(f"{role}: "):
                content = content[len(f"{role}: "):]
            
            memories.append({
                "content": content,
                "role": role,
                "timestamp": timestamp,
                "relevance": "high",
            })
        
        return memories
    
    def search_relevant_context(
        self,
        query: str,
        k: int = 3,
    ) -> str:
        memories = self.search_memories(query, k)
        
        if not memories:
            return ""
        
        context_parts = ["[历史相关记忆]"]
        for memory in memories:
            context_parts.append(
                f"- {memory['timestamp']} [{memory['role']}]: {memory['content']}"
            )
        
        return "\n".join(context_parts)
    
    def get_session_memories(self, session_id: str) -> List[Memory]:
        return [m for m in self._recent_memories if m.session_id == session_id]
    
    def clear_session(self, session_id: str = None) -> None:
        if session_id:
            self._recent_memories = [
                m for m in self._recent_memories if m.session_id != session_id
            ]
        else:
            self._recent_memories.clear()
    
    def summarize_memories(self, memories: List[Memory] = None) -> str:
        memories = memories or self._recent_memories
        
        if not memories:
            return "暂无记忆"
        
        user_count = sum(1 for m in memories if m.role == "user")
        assistant_count = sum(1 for m in memories if m.role == "assistant")
        
        return (
            f"共 {len(memories)} 条记忆\n"
            f"- 用户消息: {user_count} 条\n"
            f"- 助手回复: {assistant_count} 条"
        )


class LongTermMemory:
    def __init__(
        self,
        collection_name: str = "long_term_memory",
    ):
        self.collection_name = collection_name
        self._vectorstore = None
    
    @property
    def vectorstore(self):
        if self._vectorstore is None:
            self._vectorstore = get_vectorstore(collection_name=self.collection_name)
        return self._vectorstore
    
    def store_fact(
        self,
        fact: str,
        category: str = "general",
        importance: int = 1,
    ) -> None:
        document = Document(
            content=fact,
            metadata={
                "type": "fact",
                "category": category,
                "importance": importance,
                "created_at": format_datetime(),
            },
        )
        
        self.vectorstore.add_documents([document])
    
    def store_preference(
        self,
        preference: str,
        category: str = "general",
    ) -> None:
        document = Document(
            content=preference,
            metadata={
                "type": "preference",
                "category": category,
                "created_at": format_datetime(),
            },
        )
        
        self.vectorstore.add_documents([document])
    
    def recall(
        self,
        query: str,
        k: int = 5,
        category: str = None,
    ) -> List[Dict[str, Any]]:
        filter_expr = None
        if category:
            filter_expr = {"category": category}

        results = self.vectorstore.similarity_search(query, k=k, filter_expr=filter_expr)
        
        return [
            {
                "content": doc.content,
                "type": doc.metadata.get("type", "unknown"),
                "category": doc.metadata.get("category", "general"),
                "importance": doc.metadata.get("importance", 1),
            }
            for doc in results
        ]
