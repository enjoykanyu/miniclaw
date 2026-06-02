import re
from typing import Optional, Dict, List, Any

from miniclaw.skills.types import (
    ParsedSkillFrontmatter,
    OpenClawSkillMetadata,
    SkillInstallSpec,
    SkillInvocationPolicy,
)


def parse_frontmatter(content: str) -> ParsedSkillFrontmatter:
    result: ParsedSkillFrontmatter = {}
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if not match:
        return result
    yaml_str = match.group(1)
    try:
        import yaml
        parsed = yaml.safe_load(yaml_str)
        if isinstance(parsed, dict):
            for key, value in parsed.items():
                result[str(key)] = str(value) if value is not None else ""
    except Exception:
        for line in yaml_str.split("\n"):
            if ":" in line:
                key, _, value = line.partition(":")
                result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def resolve_openclaw_metadata(frontmatter: ParsedSkillFrontmatter) -> Optional[OpenClawSkillMetadata]:
    has_openclaw_block = any(k.startswith("openclaw") for k in frontmatter)
    if not has_openclaw_block:
        always_val = frontmatter.get("always", "")
        primary_env = frontmatter.get("primary-env", frontmatter.get("primaryEnv", ""))
        if not always_val and not primary_env:
            return None

    metadata = OpenClawSkillMetadata(
        always=_parse_bool(frontmatter.get("always", ""), False),
        skill_key=frontmatter.get("skill-key", frontmatter.get("skillKey", "")),
        primary_env=frontmatter.get("primary-env", frontmatter.get("primaryEnv", "")),
        emoji=frontmatter.get("emoji", ""),
        homepage=frontmatter.get("homepage", ""),
    )

    os_raw = frontmatter.get("os", "")
    if os_raw:
        metadata.os_list = [s.strip() for s in os_raw.split(",") if s.strip()]

    requires_bins = frontmatter.get("requires-bins", frontmatter.get("requiresBins", ""))
    if requires_bins:
        metadata.requires_bins = [s.strip() for s in requires_bins.split(",") if s.strip()]

    requires_any_bins = frontmatter.get("requires-any-bins", frontmatter.get("requiresAnyBins", ""))
    if requires_any_bins:
        metadata.requires_any_bins = [s.strip() for s in requires_any_bins.split(",") if s.strip()]

    requires_env = frontmatter.get("requires-env", frontmatter.get("requiresEnv", ""))
    if requires_env:
        metadata.requires_env = [s.strip() for s in requires_env.split(",") if s.strip()]

    return metadata


def resolve_skill_invocation_policy(frontmatter: ParsedSkillFrontmatter) -> SkillInvocationPolicy:
    return SkillInvocationPolicy(
        user_invocable=_parse_bool(frontmatter.get("user-invocable", frontmatter.get("userInvocable", "true")), True),
        disable_model_invocation=_parse_bool(
            frontmatter.get("disable-model-invocation", frontmatter.get("disableModelInvocation", "false")), False
        ),
    )


def resolve_skill_key(skill_name: str, entry=None) -> str:
    if entry and entry.metadata and entry.metadata.skill_key:
        return entry.metadata.skill_key
    return skill_name


def _parse_bool(value: str, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        low = value.lower().strip()
        if low in ("true", "yes", "1"):
            return True
        if low in ("false", "no", "0"):
            return False
    return default
