"""
MiniClaw Mid-Term Memory
中期记忆 - Conversation Summary + Entity Tracking

特性:
1. 自动总结对话历史
2. 实体追踪和更新
3. 支持手动添加关键信息
"""

from typing import Dict, Any, List, Optional
from datetime import datetime

from miniclaw.memory.base import BaseMemory, MemoryLevel, MemoryItem
from miniclaw.memory.entity import EntityMemory, Entity
from miniclaw.utils.llm import get_smart_llm


class MidTermMemory(BaseMemory):
    """
    中期记忆
    
    维护会话级别的摘要和实体信息
    """
    
    def __init__(
        self,
        llm=None,
        max_summary_length: int = 500,
        summary_interval: int = 5,  # 每5轮对话生成一次摘要
    ):
        super().__init__(MemoryLevel.MID_TERM)
        self._llm = llm
        self.max_summary_length = max_summary_length
        self.summary_interval = summary_interval
        
        # 摘要历史
        self._summaries: List[MemoryItem] = []
        self._current_summary: str = ""
        
        # 实体记忆
        self._entity_memory = EntityMemory()
        
        # 对话计数
        self._conversation_count = 0
        
        # 关键信息（手动添加）
        self._key_facts: List[MemoryItem] = []
    
    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, Any]) -> None:
        """保存对话上下文"""
        input_text = inputs.get("input", "")
        output_text = outputs.get("output", "")
        
        # 提取实体
        self._entity_memory.extract_entities(input_text)
        self._entity_memory.extract_entities(output_text)
        
        # 增加对话计数
        self._conversation_count += 1
        
        # 达到间隔时生成摘要
        if self._conversation_count % self.summary_interval == 0:
            self._generate_summary()
    
    def _generate_summary(self) -> None:
        """生成对话摘要"""
        if not self._llm:
            return
        
        # 构建摘要提示
        prompt = f"""请总结以下对话的关键信息（不超过{self.max_summary_length}字）：

当前会话摘要：{self._current_summary}

最近实体信息：
{self._entity_memory.format_entities_for_prompt()}

请生成简洁的会话摘要，包含：
1. 用户的主要需求或问题
2. 已完成的任务
3. 待处理的事项
4. 关键实体信息

摘要："""
        
        try:
            response = self._llm.invoke(prompt)
            summary_text = response.content if hasattr(response, 'content') else str(response)
            
            # 保存为新的摘要
            memory_item = MemoryItem(
                content=summary_text,
                level=MemoryLevel.MID_TERM,
                metadata={"type": "summary", "conversation_count": self._conversation_count},
            )
            
            self._summaries.append(memory_item)
            self._current_summary = summary_text
            
            # 只保留最近3个摘要
            if len(self._summaries) > 3:
                self._summaries = self._summaries[-3:]
                
        except Exception as e:
            # 摘要生成失败不影响主流程
            pass
    
    def add_key_fact(self, fact: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """手动添加关键事实"""
        memory_item = MemoryItem(
            content=fact,
            level=MemoryLevel.MID_TERM,
            metadata={"type": "key_fact", **(metadata or {})},
        )
        self._key_facts.append(memory_item)
    
    def load_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """加载记忆变量"""
        # 构建记忆内容
        parts = []
        
        # 当前摘要
        if self._current_summary:
            parts.append(f"【会话摘要】\n{self._current_summary}")
        
        # 历史摘要
        if len(self._summaries) > 1:
            parts.append("【历史摘要】")
            for item in self._summaries[:-1]:
                parts.append(f"- {item.content}")
        
        # 关键事实
        if self._key_facts:
            parts.append("【关键信息】")
            for item in self._key_facts[-5:]:  # 最近5条
                parts.append(f"- {item.content}")
        
        # 实体信息
        entity_info = self._entity_memory.format_entities_for_prompt()
        if entity_info:
            parts.append(entity_info)
        
        memory_text = "\n\n".join(parts)
        
        # 收集所有 MemoryItem
        all_items = []
        all_items.extend(self._summaries)
        all_items.extend(self._key_facts)
        
        return {
            self.get_memory_key(): memory_text,
            "summary": self._current_summary,
            "summaries": [item.to_dict() for item in self._summaries],
            "key_facts": [item.to_dict() for item in self._key_facts],
            "entities": self._entity_memory.to_dict(),
            "memory_items": all_items,
        }
    
    def get_entity_memory(self) -> EntityMemory:
        """获取实体记忆"""
        return self._entity_memory
    
    def update_entity(self, name: str, entity_type: str, attribute: str, value: Any) -> None:
        """更新实体属性"""
        self._entity_memory.update_entity_attribute(name, entity_type, attribute, value)
    
    def clear(self) -> None:
        """清空记忆"""
        self._summaries.clear()
        self._current_summary = ""
        self._key_facts.clear()
        self._entity_memory.clear()
        self._conversation_count = 0
    
    def get_summary(self) -> str:
        """获取当前摘要"""
        return self._current_summary
    
    def get_entities(self) -> List[Entity]:
        """获取所有实体"""
        return self._entity_memory.get_all_entities()
