# skills/loader.py
import os
import re
from pathlib import Path
from typing import List

import yaml

from .registry import Skill


class SkillLoader:
    """
    扫描 skills/ 目录下的所有 SKILL.md，解析 YAML frontmatter
    """
    
    def __init__(self, base_path: str = None):
        # 默认扫描项目下的 skills/ 目录
        if base_path is None:
            base_path = os.path.join(
                os.path.dirname(__file__),  # skills/
                "builtin"                   # skills/builtin/
            )
        self.base_path = Path(base_path)
    
    def load_all(self) -> List[Skill]:
        """递归扫描所有 SKILL.md"""
        skills = []
        
        # 查找所有 SKILL.md 文件
        for skill_file in self.base_path.rglob("SKILL.md"):
            skill = self._parse_file(skill_file)
            if skill:
                skills.append(skill)
        
        return skills
    
    def _parse_file(self, file_path: Path) -> Optional[Skill]:
        """
        解析单个 SKILL.md 文件
        
        格式:
        ---
        name: web_search
        description: ...
        agent: info
        tools:
          - trail
        ---
        
        # 网页搜索
        ...
        """
        content = file_path.read_text(encoding="utf-8")
        
        # 提取 YAML frontmatter (--- ... ---)
        match = re.match(r'^---\n(.*?)\n---\n(.*)', content, re.DOTALL)
        if not match:
            return None
        
        yaml_text = match.group(1)
        markdown_content = match.group(2).strip()
        
        try:
            frontmatter = yaml.safe_load(yaml_text)
        except yaml.YAMLError:
            return None
        
        return Skill(
            name=frontmatter.get("name", file_path.parent.name),
            description=frontmatter.get("description", ""),
            agent=frontmatter.get("agent", ""),
            tools=frontmatter.get("tools", []),
            content=markdown_content,
            source=str(file_path.relative_to(self.base_path.parent))
        )