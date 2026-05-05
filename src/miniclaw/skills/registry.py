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
    
    渐进式披露设计：
    - 启动时只加载 frontmatter（name, description, agent, tools）
    - content 延迟加载，需要时通过 get_skill_content() 读取
    - 已加载的 content 会缓存，避免重复读取文件
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._skills = {}
            cls._instance._loaded = False
            cls._instance._loader = None  # SkillLoader 实例，用于延迟加载
        return cls._instance
    
    def load_all(self, loader=None):
        """加载所有 skills，幂等设计"""
        if self._loaded:
            return
        
        if loader is None:
            from .loader import SkillLoader
            loader = SkillLoader()
        
        self._loader = loader
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
    
    def get_skill_content(self, name: str) -> Optional[str]:
        """
        获取 Skill 完整内容（带缓存的延迟加载）
        
        渐进式披露核心方法：
        - 如果 content 已加载，直接返回缓存
        - 如果 content 未加载，从文件系统读取并缓存
        
        Args:
            name: skill 名称
            
        Returns:
            SKILL.md 中 frontmatter 后面的 Markdown 内容
        """
        skill = self._skills.get(name)
        if not skill:
            return None
        
        # 如果 content 已加载，直接返回缓存
        if skill.content is not None:
            return skill.content
        
        # 延迟加载：从文件系统读取完整内容
        if self._loader:
            import re
            full_text = self._loader.load_skill_content(name)
            if full_text:
                # 解析 frontmatter，提取 Markdown body
                match = re.match(r'^---\n(.*?)\n---\n(.*)', full_text, re.DOTALL)
                if match:
                    skill.content = match.group(2).strip()
                else:
                    skill.content = full_text
                logger.info(f"[SkillRegistry] 延迟加载 skill '{name}' 内容")
                return skill.content
        
        return None
    
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
    



# 全局单例
skill_registry = SkillRegistry()
