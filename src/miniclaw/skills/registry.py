from dataclasses import dataclass
from typing import List, Optional
@dataclass
class Skill:
    name: str
    description: str
    agent: str           # 绑定到哪个 Agent，如 "info"
    tools: List[str]     # 需要的工具列表
    content: str         # SKILL.md 中 YAML 后面的 Markdown 内容
    source: str          # 文件路径，用于调试


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
        print(f"[SkillRegistry] 加载了 {len(self._skills)} 个 skills: {list(self._skills.keys())}")
    
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
            tools.update(skill.tools)
        return list(tools)
    
    def build_prompt_for_agent(self, agent_name: str) -> str:
        """
        为指定 Agent 构建 skill 提示词
        
        将所有匹配的 skill 内容拼接成字符串
        """
        skills = self.get_for_agent(agent_name)
        if not skills:
            return ""
        
        sections = []
        for skill in skills:
            sections.append(f"## {skill.name}\n{skill.description}\n\n{skill.content}")
        
        return "\n\n---\n\n".join(sections)


# 全局单例
skill_registry = SkillRegistry()
