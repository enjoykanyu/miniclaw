"""
MiniClaw Memory System - 多层次记忆系统

架构:
┌─────────────────────────────────────────────────────────────┐
│                    Multi-Level Memory                        │
├───────────────┬───────────────┬─────────────────────────────┤
│  Short-Term   │   Mid-Term    │         Long-Term           │
│   (短期记忆)   │   (中期记忆)   │          (长期记忆)          │
├───────────────┼───────────────┼─────────────────────────────┤
│ Conversation  │   Summary     │      Vector Store           │
│    Buffer     │   + Entity    │    (向量数据库)              │
│  (最近5轮)     │  (会话摘要)    │   (语义检索历史)            │
└───────────────┴───────────────┴─────────────────────────────┘

使用示例:
```python
from miniclaw.memory import MultiLevelMemory

memory = MultiLevelMemory(
    short_term_limit=5,
    enable_summary=True,
    vector_store=chroma_store,
)

# 保存对话
memory.save_context({"input": "你好"}, {"output": "你好！有什么可以帮助你？"})

# 加载记忆
context = memory.load_memory_variables({"input": "今天天气怎么样？"})
# 返回融合后的上下文
```
"""

from miniclaw.memory.base import BaseMemory, MemoryLevel
from miniclaw.memory.short_term import ShortTermMemory
from miniclaw.memory.mid_term import MidTermMemory
from miniclaw.memory.long_term import LongTermMemory
from miniclaw.memory.multi_level import MultiLevelMemory
from miniclaw.memory.entity import EntityMemory, Entity

__all__ = [
    # 基础类
    "BaseMemory",
    "MemoryLevel",
    # 各层记忆
    "ShortTermMemory",
    "MidTermMemory",
    "LongTermMemory",
    # 融合记忆
    "MultiLevelMemory",
    # 实体记忆
    "EntityMemory",
    "Entity",
]
