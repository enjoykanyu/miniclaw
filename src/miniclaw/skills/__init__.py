"""
MiniClaw Skill System
渐进式披露 Skill 系统 - 统一使用 SKILL.md + SkillRegistry

设计原则：
1. 启动时只加载 frontmatter（name, description, agent, tools）
2. content 延迟加载，需要时通过 get_skill_content() 读取
3. 已加载的 content 会缓存，避免重复读取文件
"""

from miniclaw.skills.registry import SkillRegistry, skill_registry, Skill, SkillToolDef
from miniclaw.skills.loader import SkillLoader

__all__ = [
    "SkillRegistry",
    "skill_registry",
    "Skill",
    "SkillToolDef",
    "SkillLoader",
]
