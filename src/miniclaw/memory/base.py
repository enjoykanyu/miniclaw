"""
MiniClaw Memory Base Classes
记忆系统基础类和接口定义
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class MemoryLevel(str, Enum):
    """记忆层级"""
    SHORT_TERM = "short_term"    # 短期记忆（最近对话）
    MID_TERM = "mid_term"        # 中期记忆（会话摘要）
    LONG_TERM = "long_term"      # 长期记忆（向量存储）


@dataclass
class MemoryItem:
    """记忆项"""
    content: str
    level: MemoryLevel
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "level": self.level.value,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


class BaseMemory(ABC):
    """
    记忆系统基类
    
    所有记忆层（短期、中期、长期）都需要实现此接口
    """
    
    def __init__(self, level: MemoryLevel):
        self.level = level
    
    @abstractmethod
    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, Any]) -> None:
        """
        保存对话上下文
        
        Args:
            inputs: 用户输入 {"input": "..."}
            outputs: 模型输出 {"output": "..."}
        """
        pass
    
    @abstractmethod
    def load_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        加载记忆变量
        
        Args:
            inputs: 当前输入
            
        Returns:
            记忆变量字典
        """
        pass
    
    @abstractmethod
    def clear(self) -> None:
        """清空记忆"""
        pass
    
    def get_memory_key(self) -> str:
        """获取记忆的键名"""
        return f"{self.level.value}_memory"


class MemoryFusionStrategy(ABC):
    """
    记忆融合策略
    
    用于融合多层记忆为最终上下文
    """
    
    @abstractmethod
    def fuse(self, memories: Dict[MemoryLevel, List[MemoryItem]]) -> str:
        """
        融合多层记忆
        
        Args:
            memories: 各层记忆 {MemoryLevel: [MemoryItem, ...]}
            
        Returns:
            融合后的上下文字符串
        """
        pass


class DefaultFusionStrategy(MemoryFusionStrategy):
    """默认记忆融合策略"""
    
    def fuse(self, memories: Dict[MemoryLevel, List[MemoryItem]]) -> str:
        """
        按优先级融合记忆：
        1. 短期记忆（最近对话）- 最高优先级
        2. 中期记忆（会话摘要）
        3. 长期记忆（相关历史）- 最低优先级
        """
        parts = []
        
        # 长期记忆 - 作为背景知识
        if MemoryLevel.LONG_TERM in memories and memories[MemoryLevel.LONG_TERM]:
            long_term = memories[MemoryLevel.LONG_TERM]
            parts.append("【相关历史】")
            for item in long_term[:3]:  # 最多3条
                parts.append(f"- {item.content}")
            parts.append("")
        
        # 中期记忆 - 会话摘要
        if MemoryLevel.MID_TERM in memories and memories[MemoryLevel.MID_TERM]:
            mid_term = memories[MemoryLevel.MID_TERM]
            parts.append("【会话摘要】")
            for item in mid_term:
                parts.append(item.content)
            parts.append("")
        
        # 短期记忆 - 最近对话
        if MemoryLevel.SHORT_TERM in memories and memories[MemoryLevel.SHORT_TERM]:
            short_term = memories[MemoryLevel.SHORT_TERM]
            parts.append("【最近对话】")
            for item in short_term:
                parts.append(item.content)
        
        return "\n".join(parts)
