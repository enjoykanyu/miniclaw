"""
Skills Snapshot — 对标 OpenClaw 的 SkillSnapshot + refresh-state

核心思想：
  在 Agent Loop 开始前，扫描所有可用工具/技能，构建一个"快照"。
  整个 loop 执行期间，快照不变——即便中途有人注册了新工具，
  本次 loop 依然使用起跑时的版本。

  这是为了防止"中途换 skill 导致语义漂移"：
    - Agent 在 T1 时刻基于 skill A v1 的描述做了决策
    - 但 T2 时刻 skill A 变成了 v2
    - 决策和执行不一致 → 结果不可预测

对标 OpenClaw 源码路径：
  - src/agents/skills/types.ts          → SkillSnapshot 类型
  - src/agents/skills/refresh-state.ts  → 版本号管理
  - src/agents/skills/snapshot-hydration.ts → 水合机制
  - src/agents/agent-command.ts L773-843 → 冻结逻辑

设计决策（为什么这样设计）：
  1. version 用时间戳 → 简单且单调递增，不需要分布式协调
  2. prompt 字段存给 LLM 的工具描述文本 → 冻结后 LLM 看到的世界不变
  3. tool_names 单独存 → 快速判断"这个工具在不在 snapshot 里"
  4. frozen_at 记录冻结时间 → 调试时可追溯"这个 snapshot 是什么时候拍的"
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


# ──────────────────────────────────────────────────────────
# 版本号管理 — 对标 refresh-state.ts
#
# 苏格拉底式提问：为什么用全局版本号而不是给每个工具单独版本号？
#
# 答：因为 Agent Loop 关心的是"整个工具集是否变了"，而不是
# "某个工具是否变了"。只要任何一个工具变了，snapshot 就需要重建。
# 全局版本号是最简单的实现方式——一次 bump 就够了。
# ──────────────────────────────────────────────────────────

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
    """
    判断是否需要刷新 snapshot

    对标 OpenClaw: shouldRefreshSnapshotForVersion()

    苏格拉底式提问：为什么 cached_version=0 且 current_version=0 不需要刷新？
    → 因为 0 代表"从未构建过"，而 current 也是 0 说明"从未有过变更"，
      两者一致，不需要重建。

    但 cached_version=0 且 current_version>0 呢？
    → cached=0 意味着"我还没有 snapshot"，current>0 意味着"世界已经变了"，
      当然需要构建一个新 snapshot。
    """
    cached = cached_version if cached_version is not None else 0
    current = current_version if current_version else 0
    if current == 0:
        return cached > 0  # 当前无变更，但缓存有旧数据 → 不需要刷新
    return cached < current  # 缓存版本 < 当前版本 → 需要刷新


# ──────────────────────────────────────────────────────────
# SkillsSnapshot — 对标 SkillSnapshot 类型
#
# 苏格拉底式提问：为什么用 frozen=True 的 dataclass？
# → Python 的 frozen dataclass 是不可变的，创建后不能修改字段。
#   这从语言层面保证了"snapshot 一旦创建就不会被篡改"。
#   但这里我们用 frozen=False，因为 LangGraph 的 state 需要能
#   序列化/反序列化，frozen dataclass 不方便。
#   我们用"约定"而非"强制"来保证不可变性。
# ──────────────────────────────────────────────────────────

@dataclass
class SkillEntry:
    """
    单个工具/技能的快照条目

    对标 OpenClaw: SkillSnapshot.skills 数组中的元素
    """
    name: str
    description: str
    category: str = "builtin"       # builtin / mcp / custom
    primary_env: Optional[str] = None   # 需要的环境变量（如 TAVILY_API_KEY）
    required_env: List[str] = field(default_factory=list)


@dataclass
class SkillsSnapshot:
    """
    工具/技能快照 — 对标 OpenClaw SkillSnapshot

    在 Agent Loop 开始前一次性构建，整个 loop 期间不变。

    字段说明：
      prompt:       给 LLM 的工具描述文本（冻结！）
      skills:       工具条目列表（冻结！）
      tool_names:   工具名集合（快速查找用）
      version:      构建时的版本号
      skill_filter: 生成此 snapshot 时的 filter（用于判断是否需要重建）
      frozen_at:    冻结时间戳（调试用）

    苏格拉底式提问：为什么 prompt 和 skills 都要存？
    → prompt 是给 LLM 看的文本，skills 是结构化数据。
      两者用途不同：prompt 注入 system message，skills 用于
      路由决策（"这个 agent 该用哪些工具"）。
      如果只存 prompt，每次路由都要重新解析文本；
      如果只存 skills，每次都要重新生成 prompt。
      两者都存，用空间换时间。
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


# ──────────────────────────────────────────────────────────
# Snapshot 构建 — 对标 buildWorkspaceSkillSnapshot()
#
# 苏格拉底式提问：为什么不直接在 agent_reason_node 里构建？
# → 因为 agent_reason_node 会被多次调用（ReAct 循环），
#   每次调用都构建 snapshot 就失去了"冻结"的意义。
#   必须在 loop 的最外层（app.py 的 chat()）构建一次，
#   然后传入 state，所有节点从 state 中读取。
# ──────────────────────────────────────────────────────────

def build_skills_snapshot(
    agent_name: Optional[str] = None,
    skill_filter: Optional[List[str]] = None,
) -> SkillsSnapshot:
    """
    构建 Skills Snapshot

    对标 OpenClaw: buildWorkspaceSkillSnapshot()

    流程：
    1. 扫描所有注册的工具（registry + 内置 + MCP）
    2. 按 agent_name 和 skill_filter 过滤
    3. 生成 prompt 文本
    4. 记录版本号和冻结时间

    苏格拉底式提问：为什么这里用同步函数而非 async？
    → 因为扫描工具注册表是纯内存操作，没有 I/O。
      OpenClaw 用同步也是同样的原因——buildWorkspaceSkillSnapshot
      只读文件系统（同步 walkDirectorySync），不涉及网络。
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

    对标 OpenClaw: loadWorkspaceSkillEntries()
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
