"""
MiniClaw Multi-Level Memory
多层记忆融合系统

整合短期、中期、长期记忆，提供统一的记忆接口
"""

from typing import Dict, Any, List, Optional

from miniclaw.memory.base import (
    BaseMemory, MemoryLevel, MemoryItem,
    MemoryFusionStrategy, DefaultFusionStrategy,
)
from miniclaw.memory.short_term import ShortTermMemory
from miniclaw.memory.mid_term import MidTermMemory
from miniclaw.memory.long_term import LongTermMemory


class MultiLevelMemory(BaseMemory):
    """
    多层记忆系统

    整合三层记忆：
    - 短期记忆：最近对话（Conversation Buffer）
    - 中期记忆：会话摘要 + 实体追踪
    - 长期记忆：向量存储语义检索

    使用融合策略将多层记忆整合为最终上下文
    """

    def __init__(
        self,
        short_term: Optional[ShortTermMemory] = None,
        mid_term: Optional[MidTermMemory] = None,
        long_term: Optional[LongTermMemory] = None,
        fusion_strategy: Optional[MemoryFusionStrategy] = None,
    ):
        super().__init__(MemoryLevel.SHORT_TERM)  # 默认使用短期记忆的 level

        # 初始化各层记忆
        self.short_term = short_term or ShortTermMemory(k=5)
        self.mid_term = mid_term or MidTermMemory()
        self.long_term = long_term or LongTermMemory()

        # 融合策略
        self.fusion_strategy = fusion_strategy or DefaultFusionStrategy()

        # 记忆开关
        self.enable_short_term = True
        self.enable_mid_term = True
        self.enable_long_term = True

    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, Any]) -> None:
        """保存对话上下文到各层记忆"""
        # 保存到短期记忆（总是保存）
        if self.enable_short_term:
            self.short_term.save_context(inputs, outputs)

        # 保存到中期记忆
        if self.enable_mid_term:
            self.mid_term.save_context(inputs, outputs)

        # 保存到长期记忆
        if self.enable_long_term:
            self.long_term.save_context(inputs, outputs)

    def load_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        加载记忆变量

        从各层记忆加载并融合
        """
        # 收集各层记忆
        all_memories: Dict[MemoryLevel, List[MemoryItem]] = {}
        all_variables = {}

        # 短期记忆
        if self.enable_short_term:
            short_term_vars = self.short_term.load_memory_variables(inputs)
            all_variables.update(short_term_vars)
            if "memory_items" in short_term_vars:
                all_memories[MemoryLevel.SHORT_TERM] = short_term_vars["memory_items"]

        # 中期记忆
        if self.enable_mid_term:
            mid_term_vars = self.mid_term.load_memory_variables(inputs)
            all_variables.update(mid_term_vars)
            if "memory_items" in mid_term_vars:
                all_memories[MemoryLevel.MID_TERM] = mid_term_vars["memory_items"]

        # 长期记忆
        if self.enable_long_term:
            long_term_vars = self.long_term.load_memory_variables(inputs)
            all_variables.update(long_term_vars)
            if "memory_items" in long_term_vars:
                all_memories[MemoryLevel.LONG_TERM] = long_term_vars["memory_items"]

        # 融合记忆
        fused_memory = self.fusion_strategy.fuse(all_memories)

        return {
            "memory": fused_memory,
            "short_term": all_variables.get("short_term_memory", ""),
            "mid_term": all_variables.get("mid_term_memory", ""),
            "long_term": all_variables.get("long_term_memory", ""),
            "history": all_variables.get("history", []),
            "entities": all_variables.get("entities", {}),
            "retrieved_memories": all_variables.get("retrieved_memories", []),
        }

    def clear(self) -> None:
        """清空所有记忆"""
        self.short_term.clear()
        self.mid_term.clear()
        self.long_term.clear()

    def get_short_term_memory(self) -> ShortTermMemory:
        """获取短期记忆"""
        return self.short_term

    def get_mid_term_memory(self) -> MidTermMemory:
        """获取中期记忆"""
        return self.mid_term

    def get_long_term_memory(self) -> LongTermMemory:
        """获取长期记忆"""
        return self.long_term

    def enable_all(self) -> None:
        """启用所有记忆层"""
        self.enable_short_term = True
        self.enable_mid_term = True
        self.enable_long_term = True

    def disable_all(self) -> None:
        """禁用所有记忆层"""
        self.enable_short_term = False
        self.enable_mid_term = False
        self.enable_long_term = False

    def get_stats(self) -> Dict[str, Any]:
        """获取记忆统计信息"""
        return {
            "short_term": {
                "enabled": self.enable_short_term,
                "turns": self.short_term.get_conversation_turns(),
            },
            "mid_term": {
                "enabled": self.enable_mid_term,
                "summary": self.mid_term.get_summary()[:100] + "..." if self.mid_term.get_summary() else "",
                "entity_count": len(self.mid_term.get_entities()),
            },
            "long_term": {
                "enabled": self.enable_long_term,
                **self.long_term.get_stats(),
            },
        }
