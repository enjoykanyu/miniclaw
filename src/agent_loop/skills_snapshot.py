from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

_global_version: int = 0


def bump_snapshot_version() -> int:
    """
    Bump 全局 snapshot 版本号

    对标 OpenClaw: bumpSkillsSnapshotVersion()
    调用时机：工具注册/注销、配置变更、MCP 连接变化

    为什么用 max(now, current+1)？
    → 时间戳天然递增，但系统时钟可能回拨（NTP 校正），
      所以加一个 +1 兜底，保证版本号永远递增。
    """
    global _global_version
    now_ms = int(time.time() * 1000)
    _global_version = max(now_ms, _global_version + 1)
    return _global_version


def get_snapshot_version() -> int:
    """获取当前全局版本号"""
    return _global_version


def should_refresh(cached_version: Optional[int], current_version: int) -> bool:
  
    cached = cached_version if cached_version is not None else 0
    current = current_version if current_version else 0
    if current == 0:
        return cached > 0  # 当前无变更，但缓存有旧数据 → 不需要刷新
    return cached < current  # 缓存版本 < 当前版本 → 需要刷新


@dataclass
class SkillEntry:
    """
    单个工具/技能的快照条目

    """
    name: str
    description: str
    category: str = "builtin"       # builtin / mcp / custom
    primary_env: Optional[str] = None   # 需要的环境变量（如 TAVILY_API_KEY）
    required_env: List[str] = field(default_factory=list)


@dataclass
class SkillsSnapshot:
    """
    在 Agent Loop 开始前一次性构建，整个 loop 期间不变。

    字段说明：
      prompt:       给 LLM 的工具描述文本（冻结！）
      skills:       工具条目列表（冻结！）
      tool_names:   工具名集合（快速查找用）
      version:      构建时的版本号
      skill_filter: 生成此 snapshot 时的 filter（用于判断是否需要重建）
      frozen_at:    冻结时间戳（调试用）
    """
    prompt: str
    skills: List[SkillEntry] = field(default_factory=list)
    tool_names: List[str] = field(default_factory=list)
    version: int = 0
    skill_filter: Optional[List[str]] = None
    frozen_at: str = ""

    def has_tool(self, name: str) -> bool:
        """快速判断工具是否在 snapshot 中"""
        return name in self.tool_names

    def get_skill(self, name: str) -> Optional[SkillEntry]:
        """按名称获取工具条目"""
        for s in self.skills:
            if s.name == name:
                return s
        return None

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典（用于 LangGraph state 存储）"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SkillsSnapshot:
        """从字典反序列化"""
        skills_data = data.pop("skills", [])
        skills = [SkillEntry(**s) if isinstance(s, dict) else s for s in skills_data]
        return cls(skills=skills, **data)


def build_skills_snapshot(
    agent_name: Optional[str] = None,
    skill_filter: Optional[List[str]] = None,
) -> SkillsSnapshot:
    """
    构建 Skills Snapshot
    流程：
    1. 扫描所有注册的工具（registry + 内置 + MCP）
    2. 按 agent_name 和 skill_filter 过滤
    3. 生成 prompt 文本
    4. 记录版本号和冻结时间

    """
    all_skills = _scan_all_skills()

    # 按 agent 过滤
    if agent_name:
        all_skills = _filter_skills_for_agent(all_skills, agent_name)

    # 按 skill_filter 过滤
    if skill_filter:
        all_skills = [s for s in all_skills if s.name in skill_filter]

    # 生成 prompt
    prompt = _build_skills_prompt(all_skills)

    # 记录版本号和冻结时间
    version = get_snapshot_version()
    frozen_at = time.strftime("%Y-%m-%dT%H:%M:%S%z")

    return SkillsSnapshot(
        prompt=prompt,
        skills=all_skills,
        tool_names=[s.name for s in all_skills],
        version=version,
        skill_filter=skill_filter,
        frozen_at=frozen_at,
    )


def _scan_all_skills() -> List[SkillEntry]:
    """
    扫描所有可用工具

    优先从 registry 读取，fallback 到内置模块扫描。
    """
    skills: List[SkillEntry] = []

    # 1. 从 ToolRegistry 读取
    try:
        from tools.registry import registry
        for name, tool in registry.get_all_tools().items():
            skills.append(SkillEntry(
                name=tool.name,
                description=tool.description,
                category=tool.category.value if hasattr(tool.category, "value") else str(tool.category),
            ))
    except Exception:
        pass

    # 2. 内置工具扫描
    builtin_modules = {
        "think": ("tools.think", "深度思考工具，用于复杂问题的推理和分析"),
        "get_weather": ("tools.weather", "查询天气信息"),
        "get_news": ("tools.news", "获取新闻资讯"),
        "tavily": ("tools.tavily", "联网搜索工具"),
    }
    existing_names = {s.name for s in skills}
    for name, (module_path, desc) in builtin_modules.items():
        if name not in existing_names:
            try:
                import importlib
                mod = importlib.import_module(module_path)
                if hasattr(mod, name):
                    skills.append(SkillEntry(
                        name=name,
                        description=desc,
                        category="builtin",
                    ))
            except Exception:
                pass

    # 3. MCP 工具
    try:
        from mcp.tools import mcp_tool_registry
        for tool in mcp_tool_registry.get_all_tools():
            if hasattr(tool, "name") and tool.name not in existing_names:
                skills.append(SkillEntry(
                    name=tool.name,
                    description=getattr(tool, "description", ""),
                    category="mcp",
                ))
    except Exception:
        pass

    return skills


def _filter_skills_for_agent(skills: List[SkillEntry], agent_name: str) -> List[SkillEntry]:
    """
    按 Agent 类型过滤工具

    对标 OpenClaw: filterWorkspaceSkillEntries() + resolveAgentSkillsFilter()

    苏格拉底式提问：为什么不同 Agent 看到不同的工具？
    → 因为"最小权限原则"。chat agent 不需要操作 Excel，
      data agent 不需要查天气。减少工具数量 = 减少 LLM 的选择空间
      = 减少选错工具的概率 = 提高推理质量。
    """
    agent_tool_map = {
        "learning": ["think"],
        "task": ["think"],
        "info": ["get_weather", "get_news", "think", "tavily"],
        "health": ["think"],
        "data": ["think"],
        "chat": ["think", "tavily"],
    }
    allowed = set(agent_tool_map.get(agent_name, ["think"]))
    return [s for s in skills if s.name in allowed]


def _build_skills_prompt(skills: List[SkillEntry]) -> str:
    """
    生成给 LLM 的工具描述文本

    对标 OpenClaw: formatSkillsForPrompt()

    苏格拉底式提问：为什么不用 JSON 格式而用自然语言？
    → 因为 LLM 对自然语言的理解优于 JSON。
      OpenClaw 也是用 Markdown 格式（每个 skill 一个标题 + 描述），
      而不是原始的 JSON schema。
    """
    if not skills:
        return "当前没有可用的工具。"

    lines = ["## 可用工具\n"]
    for s in skills:
        lines.append(f"- **{s.name}**: {s.description}")
        if s.primary_env:
            lines.append(f"  (需要环境变量: {s.primary_env})")

    return "\n".join(lines)
