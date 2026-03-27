"""
MiniClaw Entity Memory
实体记忆 - 提取和追踪对话中的关键实体

特性:
1. 自动提取人名、地点、组织、时间等实体
2. 维护实体属性和关系
3. 支持实体更新和查询
"""

import re
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict

from miniclaw.memory.base import MemoryLevel


@dataclass
class Entity:
    """实体定义"""
    name: str
    type: str  # person, location, organization, time, etc.
    attributes: Dict[str, Any] = field(default_factory=dict)
    mentions: int = 1  # 提及次数
    first_seen: datetime = field(default_factory=datetime.now)
    last_seen: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type,
            "attributes": self.attributes,
            "mentions": self.mentions,
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
        }


class EntityMemory:
    """
    实体记忆
    
    提取和追踪对话中的关键实体
    """
    
    # 简单的实体类型模式（实际项目中可以使用 NER 模型）
    ENTITY_PATTERNS = {
        "time": [
            r"\d{4}年\d{1,2}月\d{1,2}日",
            r"\d{1,2}月\d{1,2}日",
            r"明天|后天|今天|昨天",
            r"\d{1,2}:\d{2}",
        ],
        "location": [
            r"北京|上海|广州|深圳|杭州|成都|武汉|西安",
            r"[\u4e00-\u9fa5]{2,}(?:市|省|区|县)",
        ],
        "person": [
            r"(?:我|你|他|她|我们|你们|他们)",
        ],
    }
    
    def __init__(self):
        self._entities: Dict[str, Entity] = {}
        self._type_index: Dict[str, Set[str]] = defaultdict(set)
    
    def extract_entities(self, text: str) -> List[Entity]:
        """
        从文本中提取实体
        
        简化版实现，实际项目应使用 NER 模型
        """
        found_entities = []
        
        for entity_type, patterns in self.ENTITY_PATTERNS.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text)
                for match in matches:
                    name = match.group()
                    entity = self._get_or_create_entity(name, entity_type)
                    entity.mentions += 1
                    entity.last_seen = datetime.now()
                    found_entities.append(entity)
        
        return found_entities
    
    def _get_or_create_entity(self, name: str, entity_type: str) -> Entity:
        """获取或创建实体"""
        key = f"{entity_type}:{name}"
        
        if key not in self._entities:
            self._entities[key] = Entity(
                name=name,
                type=entity_type,
            )
            self._type_index[entity_type].add(key)
        
        return self._entities[key]
    
    def update_entity_attribute(
        self,
        name: str,
        entity_type: str,
        attribute: str,
        value: Any,
    ) -> None:
        """更新实体属性"""
        key = f"{entity_type}:{name}"
        if key in self._entities:
            self._entities[key].attributes[attribute] = value
            self._entities[key].last_seen = datetime.now()
    
    def get_entity(self, name: str, entity_type: str) -> Optional[Entity]:
        """获取指定实体"""
        key = f"{entity_type}:{name}"
        return self._entities.get(key)
    
    def get_entities_by_type(self, entity_type: str) -> List[Entity]:
        """获取某类型的所有实体"""
        keys = self._type_index.get(entity_type, set())
        return [self._entities[key] for key in keys if key in self._entities]
    
    def get_all_entities(self) -> List[Entity]:
        """获取所有实体"""
        return list(self._entities.values())
    
    def get_top_entities(self, n: int = 5) -> List[Entity]:
        """获取提及次数最多的 N 个实体"""
        sorted_entities = sorted(
            self._entities.values(),
            key=lambda e: e.mentions,
            reverse=True,
        )
        return sorted_entities[:n]
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "entities": {k: v.to_dict() for k, v in self._entities.items()},
            "total_count": len(self._entities),
            "type_counts": {
                t: len(keys) for t, keys in self._type_index.items()
            },
        }
    
    def clear(self) -> None:
        """清空实体记忆"""
        self._entities.clear()
        self._type_index.clear()
    
    def format_entities_for_prompt(self) -> str:
        """格式化实体为提示词"""
        if not self._entities:
            return ""
        
        lines = ["【已识别的实体】"]
        
        # 按类型分组
        for entity_type in ["person", "location", "time", "organization"]:
            entities = self.get_entities_by_type(entity_type)
            if entities:
                type_name = {
                    "person": "人物",
                    "location": "地点",
                    "time": "时间",
                    "organization": "组织",
                }.get(entity_type, entity_type)
                
                lines.append(f"{type_name}:")
                for entity in sorted(entities, key=lambda e: e.mentions, reverse=True)[:3]:
                    attr_str = ", ".join([f"{k}={v}" for k, v in entity.attributes.items()])
                    if attr_str:
                        lines.append(f"  - {entity.name} ({attr_str}) [提及{entity.mentions}次]")
                    else:
                        lines.append(f"  - {entity.name} [提及{entity.mentions}次]")
        
        return "\n".join(lines)
