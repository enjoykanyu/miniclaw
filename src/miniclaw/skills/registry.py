from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from loguru import logger

@dataclass
class SkillToolDef:
    """Skill 中定义的工具配置"""
    name: str
    condition: Optional[str] = None  # 注入条件，如 "force_search"
    required: bool = False           # 是否强制要求调用

@dataclass
class Skill:
    name: str
    description: str
    agent: str           # 绑定到哪个 Agent，如 "info"
    tools: List[SkillToolDef] = field(default_factory=list)  # 工具定义列表
    content: Optional[str] = None  # SKILL.md 中 YAML 后面的 Markdown 内容（延迟加载）
    source: str = ""     # 文件路径，用于调试


class SkillRegistry:
    """
    Skill 注册表 - 全局单例管理所有已加载的 skills
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._skills = {}
            cls._instance._loaded = False
        return cls._instance
    
    def load_all(self, loader: SkillLoader = None):
        """加载所有 skills，幂等设计"""
        if self._loaded:
            return
        
        if loader is None:
            loader = SkillLoader()
        
        for skill in loader.load_all():
            self._skills[skill.name] = skill
        
        self._loaded = True
        logger.info(f"[SkillRegistry] 加载了 {len(self._skills)} 个 skills: {list(self._skills.keys())}")
    
    def get(self, name: str) -> Optional[Skill]:
        """按名称获取 skill"""
        return self._skills.get(name)
    
    def get_for_agent(self, agent_name: str) -> List[Skill]:
        """
        获取绑定到指定 Agent 的所有 skills
        
        例如 InfoAgent 调用 → 返回所有 agent == "info" 的 skill
        """
        return [
            skill for skill in self._skills.values()
            if skill.agent == agent_name
        ]
    
    def get_all_tools(self, agent_name: str) -> List[str]:
        """获取某个 Agent 需要的所有工具名称（去重）"""
        skills = self.get_for_agent(agent_name)
        tools = set()
        for skill in skills:
            for tool_def in skill.tools:
                tools.add(tool_def.name)
        return list(tools)
    
    def build_skills_summary(self, agent_name: str) -> str:
        """
        为指定 Agent 构建技能目录摘要（渐进式披露 Level 1）
        
        只包含 name + description，不加载完整 content
        供 LLM 自主判断是否需要某个 skill
        
        Args:
            agent_name: Agent 名称，如 "info"
            
        Returns:
            格式化的技能目录字符串
        """
        skills = self.get_for_agent(agent_name)
        if not skills:
            return ""
        
        lines = ["【可用技能目录】"]
        for skill in skills:
            lines.append(f"- {skill.name}: {skill.description}")
        
        return "\n".join(lines)
    
    def build_prompt_for_agent(self, agent_name: str) -> str:
        """
        为指定 Agent 构建 skill 提示词（完整内容，非渐进式）
        
        将所有匹配的 skill 内容拼接成字符串
        注意：此方法会加载所有 skill 的完整内容，不适合大量 skill 场景
        """
        skills = self.get_for_agent(agent_name)
        if not skills:
            return ""
        
        sections = []
        for skill in skills:
            content = skill.content or ""
            sections.append(f"## {skill.name}\n{skill.description}\n\n{content}")
        
        return "\n\n---\n\n".join(sections)


# 全局单例
skill_registry = SkillRegistry()
