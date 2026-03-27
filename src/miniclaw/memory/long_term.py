"""
MiniClaw Long-Term Memory
长期记忆 - Vector Store Based Retrieval

特性:
1. 基于向量存储的语义检索
2. 支持相似度搜索
3. 时间衰减权重
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import hashlib

from miniclaw.memory.base import BaseMemory, MemoryLevel, MemoryItem


class LongTermMemory(BaseMemory):
    """
    长期记忆
    
    使用向量存储保存历史对话，支持语义检索
    """
    
    def __init__(
        self,
        vector_store=None,
        embedding_model=None,
        retrieval_k: int = 3,
        similarity_threshold: float = 0.7,
        time_decay_days: int = 30,  # 30天后记忆衰减
    ):
        super().__init__(MemoryLevel.LONG_TERM)
        self._vector_store = vector_store
        self._embedding_model = embedding_model
        self.retrieval_k = retrieval_k
        self.similarity_threshold = similarity_threshold
        self.time_decay_days = time_decay_days
        
        # 如果没有提供向量存储，使用内存存储
        if self._vector_store is None:
            self._memory_store: Dict[str, Dict[str, Any]] = {}
        else:
            self._memory_store = None
    
    def _generate_id(self, content: str) -> str:
        """生成内容 ID"""
        return hashlib.md5(content.encode()).hexdigest()[:16]
    
    def _calculate_time_weight(self, timestamp: datetime) -> float:
        """计算时间衰减权重"""
        age_days = (datetime.now() - timestamp).days
        if age_days > self.time_decay_days:
            return 0.5  # 衰减到50%
        return 1.0 - (age_days / self.time_decay_days) * 0.5
    
    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, Any]) -> None:
        """保存对话上下文到长期记忆"""
        input_text = inputs.get("input", "")
        output_text = outputs.get("output", "")
        
        if not input_text and not output_text:
            return
        
        # 构建完整对话内容
        content = f"用户: {input_text}\n助手: {output_text}" if output_text else f"用户: {input_text}"
        
        memory_id = self._generate_id(content)
        timestamp = datetime.now()
        
        memory_data = {
            "id": memory_id,
            "content": content,
            "input": input_text,
            "output": output_text,
            "timestamp": timestamp,
            "metadata": {
                "timestamp": timestamp.isoformat(),
                "level": MemoryLevel.LONG_TERM.value,
            },
        }
        
        if self._vector_store:
            # 使用向量存储
            try:
                self._vector_store.add_texts(
                    texts=[content],
                    metadatas=[memory_data["metadata"]],
                    ids=[memory_id],
                )
            except Exception as e:
                # 向量存储失败时降级到内存
                if self._memory_store is not None:
                    self._memory_store[memory_id] = memory_data
        else:
            # 使用内存存储
            self._memory_store[memory_id] = memory_data
    
    def load_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        加载记忆变量
        
        基于当前输入进行语义检索
        """
        query = inputs.get("input", "")
        
        if not query:
            return {
                self.get_memory_key(): "",
                "retrieved_memories": [],
                "memory_items": [],
            }
        
        retrieved_memories = self._retrieve_memories(query)
        
        # 构建记忆文本
        if retrieved_memories:
            parts = ["【相关历史对话】"]
            for memory in retrieved_memories:
                parts.append(f"- {memory['content']}")
            memory_text = "\n".join(parts)
        else:
            memory_text = ""
        
        # 转换为 MemoryItem
        memory_items = [
            MemoryItem(
                content=m["content"],
                level=MemoryLevel.LONG_TERM,
                timestamp=m.get("timestamp", datetime.now()),
                metadata=m.get("metadata", {}),
            )
            for m in retrieved_memories
        ]
        
        return {
            self.get_memory_key(): memory_text,
            "retrieved_memories": retrieved_memories,
            "memory_items": memory_items,
        }
    
    def _retrieve_memories(self, query: str) -> List[Dict[str, Any]]:
        """检索相关记忆"""
        if self._vector_store:
            return self._retrieve_from_vector_store(query)
        else:
            return self._retrieve_from_memory(query)
    
    def _retrieve_from_vector_store(self, query: str) -> List[Dict[str, Any]]:
        """从向量存储检索"""
        try:
            results = self._vector_store.similarity_search_with_score(
                query,
                k=self.retrieval_k,
            )
            
            memories = []
            for doc, score in results:
                if score >= self.similarity_threshold:
                    timestamp = datetime.fromisoformat(
                        doc.metadata.get("timestamp", datetime.now().isoformat())
                    )
                    weight = self._calculate_time_weight(timestamp)
                    
                    memories.append({
                        "content": doc.page_content,
                        "score": score * weight,  # 应用时间衰减
                        "timestamp": timestamp,
                        "metadata": doc.metadata,
                    })
            
            # 按加权分数排序
            memories.sort(key=lambda x: x["score"], reverse=True)
            return memories[:self.retrieval_k]
            
        except Exception as e:
            # 向量检索失败时返回空
            return []
    
    def _retrieve_from_memory(self, query: str) -> List[Dict[str, Any]]:
        """从内存存储检索（简化版关键词匹配）"""
        if not self._memory_store:
            return []
        
        query_words = set(query.lower().split())
        scored_memories = []
        
        for memory_id, memory_data in self._memory_store.items():
            content = memory_data["content"].lower()
            content_words = set(content.split())
            
            # 计算重叠词数
            overlap = len(query_words & content_words)
            if overlap > 0:
                score = overlap / len(query_words)
                timestamp = memory_data.get("timestamp", datetime.now())
                weight = self._calculate_time_weight(timestamp)
                
                scored_memories.append({
                    "content": memory_data["content"],
                    "score": score * weight,
                    "timestamp": timestamp,
                    "metadata": memory_data.get("metadata", {}),
                })
        
        # 按分数排序
        scored_memories.sort(key=lambda x: x["score"], reverse=True)
        
        # 过滤低分结果
        return [
            m for m in scored_memories[:self.retrieval_k]
            if m["score"] >= self.similarity_threshold
        ]
    
    def add_memory(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """手动添加记忆"""
        memory_id = self._generate_id(content)
        timestamp = datetime.now()
        
        memory_data = {
            "id": memory_id,
            "content": content,
            "input": "",
            "output": content,
            "timestamp": timestamp,
            "metadata": {
                "timestamp": timestamp.isoformat(),
                "level": MemoryLevel.LONG_TERM.value,
                **(metadata or {}),
            },
        }
        
        if self._vector_store:
            try:
                self._vector_store.add_texts(
                    texts=[content],
                    metadatas=[memory_data["metadata"]],
                    ids=[memory_id],
                )
            except Exception:
                if self._memory_store is not None:
                    self._memory_store[memory_id] = memory_data
        else:
            if self._memory_store is not None:
                self._memory_store[memory_id] = memory_data
    
    def search(self, query: str, k: Optional[int] = None) -> List[Dict[str, Any]]:
        """搜索记忆"""
        if k is None:
            k = self.retrieval_k
        
        original_k = self.retrieval_k
        self.retrieval_k = k
        results = self._retrieve_memories(query)
        self.retrieval_k = original_k
        
        return results
    
    def clear(self) -> None:
        """清空记忆"""
        if self._memory_store is not None:
            self._memory_store.clear()
        
        if self._vector_store:
            try:
                # 向量存储的清空取决于具体实现
                pass
            except Exception:
                pass
    
    def get_stats(self) -> Dict[str, Any]:
        """获取记忆统计信息"""
        stats = {
            "total_memories": 0,
            "storage_type": "vector_store" if self._vector_store else "memory",
        }
        
        if self._memory_store is not None:
            stats["total_memories"] = len(self._memory_store)
        
        return stats
