from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class Skill:
    name: str
    description: str
    file_path: str = ""
    base_dir: str = ""
    source: str = ""


@dataclass
class SkillInstallSpec:
    kind: str = ""
    formula: str = ""
    package: str = ""
    module: str = ""
    url: str = ""
    bins: Optional[List[str]] = None
    os_list: Optional[List[str]] = None


@dataclass
class OpenClawSkillMetadata:
    always: bool = False
    skill_key: str = ""
    primary_env: str = ""
    emoji: str = ""
    homepage: str = ""
    os_list: Optional[List[str]] = None
    requires_bins: Optional[List[str]] = None
    requires_any_bins: Optional[List[str]] = None
    requires_env: Optional[List[str]] = None
    requires_config: Optional[List[str]] = None
    install: Optional[List[SkillInstallSpec]] = None


@dataclass
class SkillInvocationPolicy:
    user_invocable: bool = True
    disable_model_invocation: bool = False


@dataclass
class SkillExposure:
    include_in_runtime_registry: bool = True
    include_in_available_skills_prompt: bool = True
    user_invocable: bool = True


ParsedSkillFrontmatter = Dict[str, str]


@dataclass
class SkillEntry:
    skill: Skill
    frontmatter: ParsedSkillFrontmatter = field(default_factory=dict)
    metadata: Optional[OpenClawSkillMetadata] = None
    invocation: Optional[SkillInvocationPolicy] = None
    exposure: Optional[SkillExposure] = None
    sync_source_dir: str = ""
    sync_dir_name: str = ""


@dataclass
class SkillSnapshot:
    prompt: str = ""
    skills: List[Dict[str, Any]] = field(default_factory=list)
    skill_filter: Optional[List[str]] = None
    version: int = 0
