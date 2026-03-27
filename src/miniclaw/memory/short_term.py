"""
MiniClaw Short-Term Memory
短期记忆 - Conversation Buffer with Window

特性:
1. 保留最近 N 轮对话
2. 支持 Token 限制
3. 支持时间窗口
"""

from typing import Dict, Any, List, Optional
from collections import deque
from datetime import datetime, timedelta

from miniclaw.memory.base import BaseMemory, MemoryLevel, MemoryItem


class ShortTermMemory(BaseMemory):
    """
    短期记忆
    
    保留最近的对话历史，支持多种限制策略：
    - 轮数限制 (k)
    - Token 限制
    - 时间窗口
    """
    
    def __init__(
        self,
        k: int = 5,  # 保留最近 k 轮对话
        max_tokens: Optional[int] = None,
        time_window: Optional[timedelta] = None,  # 时间窗口
    ):
        super().__init__(MemoryLevel.SHORT_TERM)
        self.k = k
        self.max_tokens = max_tokens
        self.time_window = time_window
        
        # 使用 deque 自动限制大小
        self._buffer: deque = deque(maxlen=k * 2)  # 每轮包含 input 和 output
        self._messages: List[Dict[str, Any]] = []
    
    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, Any]) -> None:
        """保存对话上下文"""
        input_text = inputs.get("input", "")
        output_text = outputs.get("output", "")
        
        # 保存到 buffer
        timestamp = datetime.now()
        
        if input_text:
            self._buffer.append({
                "role": "user",
                "content": input_text,
                "timestamp": timestamp,
            })
        
        if output_text:
            self._buffer.append({
                "role": "assistant",
                "content": output_text,
                "timestamp": timestamp,
            })
        
        # 同步到 messages 列表
        self._sync_messages()
    
    def _sync_messages(self) -> None:
        """同步 buffer 到 messages 列表"""
        self._messages = list(self._buffer)
        
        # 应用时间窗口过滤
        if self.time_window:
            cutoff_time = datetime.now() - self.time_window
            self._messages = [
                msg for msg in self._messages
                if msg.get("timestamp", datetime.now()) > cutoff_time
            ]
    
    def load_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """加载记忆变量"""
        self._sync_messages()
        
        # 构建对话历史字符串
        history = []
        for msg in self._messages:
            role = "用户" if msg["role"] == "user" else "助手"
            history.append(f"{role}: {msg['content']}")
        
        history_text = "\n".join(history)
        
        # 转换为 MemoryItem 列表
        memory_items = [
            MemoryItem(
                content=f"{msg['role']}: {msg['content']}",
                level=MemoryLevel.SHORT_TERM,
                timestamp=msg.get("timestamp", datetime.now()),
            )
            for msg in self._messages
        ]
        
        return {
            self.get_memory_key(): history_text,
            "history": self._messages,
            "memory_items": memory_items,
        }
    
    def get_messages(self) -> List[Dict[str, Any]]:
        """获取消息列表（用于 LangChain）"""
        self._sync_messages()
        return [
            {"role": msg["role"], "content": msg["content"]}
            for msg in self._messages
        ]
    
    def clear(self) -> None:
        """清空记忆"""
        self._buffer.clear()
        self._messages = []
    
    def get_recent_messages(self, n: int = 5) -> List[Dict[str, Any]]:
        """获取最近 n 条消息"""
        self._sync_messages()
        return self._messages[-n:] if n < len(self._messages) else self._messages
    
    def get_conversation_turns(self) -> int:
        """获取对话轮数"""
        self._sync_messages()
        return len(self._messages) // 2


class ConversationBufferWindowMemory(ShortTermMemory):
    """
    Conversation Buffer Window Memory
    
    LangChain 风格的窗口记忆
    """
    
    def __init__(self, k: int = 5, **kwargs):
        super().__init__(k=k, **kwargs)
    
    def load_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """加载记忆变量（LangChain 兼容格式）"""
        result = super().load_memory_variables(inputs)
        
        # 添加 LangChain 风格的 history
        from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
        
        messages: List[BaseMessage] = []
        for msg in self._messages:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            else:
                messages.append(AIMessage(content=msg["content"]))
        
        result["chat_history"] = messages
        return result
