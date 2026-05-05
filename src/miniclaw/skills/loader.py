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
    
    渐进式披露设计：
    - 启动时只加载 frontmatter（name, description, agent, tools）
    - content 延迟加载，需要时通过 load_skill_content() 读取
    
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
        # 记录文件路径映射，用于延迟加载 content
        self._file_map: Dict[str, Path] = {}
    
    def load_all(self) -> List[Skill]:
        """递归扫描所有 SKILL.md，只加载 frontmatter"""
        skills = []
        
        # 查找所有 SKILL.md 文件
        for skill_file in self.base_path.rglob("SKILL.md"):
            skill = self._parse_file(skill_file)
            if skill:
                skills.append(skill)
                # 记录 name -> file_path 映射，用于后续延迟加载
                self._file_map[skill.name] = skill_file
        
        return skills
    
    def load_skill_content(self, name: str) -> Optional[str]:
        """
        按需加载指定 skill 的完整内容（渐进式披露）
        
        Args:
            name: skill 名称
            
        Returns:
            SKILL.md 的完整内容（包括 frontmatter），如果找不到返回 None
        """
        file_path = self._file_map.get(name)
        if not file_path or not file_path.exists():
            return None
        
        return file_path.read_text(encoding="utf-8")
    
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
        解析单个 SKILL.md 文件的 frontmatter（渐进式披露 Level 1）
        
        只读取 YAML frontmatter，不加载 Markdown body
        Markdown body 通过 load_skill_content() 按需加载
        
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
        # 不读取 markdown_content，延迟加载
        # markdown_content = match.group(2).strip()
        
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
            content=None,  # 延迟加载，不读取 Markdown body
            source=str(file_path.relative_to(self.base_path.parent))
        )