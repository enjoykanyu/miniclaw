# skills/loader.py
import os
import re
from pathlib import Path
from typing import List, Optional

import yaml

from .registry import Skill, SkillToolDef


class SkillLoader:
    """
    扫描 skills/ 目录下的所有 SKILL.md，解析 YAML frontmatter
    
    支持两种 tools 格式：
    1. 简单列表: tools: [tavily, get_news]
    2. 详细定义:
       tools:
         - name: tavily
           condition: force_search
           required: true
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
    
    def _parse_tools(self, tools_raw: list) -> List[SkillToolDef]:
        """
        解析 tools 字段，支持两种格式
        
        Args:
            tools_raw: YAML 解析后的 tools 列表
            
        Returns:
            List[SkillToolDef]: 统一的工具定义列表
        """
        if not tools_raw:
            return []
        
        result = []
        for item in tools_raw:
            if isinstance(item, str):
                # 简单格式: "tavily"
                result.append(SkillToolDef(name=item))
            elif isinstance(item, dict):
                # 详细格式: {name: tavily, condition: force_search}
                result.append(SkillToolDef(
                    name=item.get("name", ""),
                    condition=item.get("condition"),
                    required=item.get("required", False)
                ))
        return result
    
    def _parse_file(self, file_path: Path) -> Optional[Skill]:
        """
        解析单个 SKILL.md 文件
        
        格式:
        ---
        name: web_search
        description: ...
        agent: info
        tools:
          - name: tavily
            condition: force_search
            required: true
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
        
        # 解析 tools 字段（支持两种格式）
        tools_raw = frontmatter.get("tools", [])
        tools = self._parse_tools(tools_raw)
        
        return Skill(
            name=frontmatter.get("name", file_path.parent.name),
            description=frontmatter.get("description", ""),
            agent=frontmatter.get("agent", ""),
            tools=tools,
            content=markdown_content,
            source=str(file_path.relative_to(self.base_path.parent))
        )