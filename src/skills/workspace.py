import os
from typing import Optional, List, Dict, Tuple

from skills.types import Skill, SkillEntry, SkillSnapshot
from skills.frontmatter import (
    parse_frontmatter,
    resolve_openclaw_metadata,
    resolve_skill_invocation_policy,
    resolve_skill_key,
)
from skills.config import filter_skill_entries


SKILL_FILENAME = "SKILL.md"


def _load_single_skill_directory(skill_dir: str, source: str = "") -> Optional[SkillEntry]:
    skill_file_path = os.path.join(skill_dir, SKILL_FILENAME)
    if not os.path.isfile(skill_file_path):
        return None
    try:
        with open(skill_file_path, "r", encoding="utf-8") as f:
            raw = f.read()
    except Exception:
        return None
    if not raw.strip():
        return None

    frontmatter = parse_frontmatter(raw)
    name = frontmatter.get("name", "").strip() or os.path.basename(skill_dir).strip()
    description = frontmatter.get("description", "").strip()
    if not name or not description:
        return None

    skill = Skill(
        name=name,
        description=description,
        file_path=skill_file_path,
        base_dir=skill_dir,
        source=source,
    )
    metadata = resolve_openclaw_metadata(frontmatter)
    invocation = resolve_skill_invocation_policy(frontmatter)

    return SkillEntry(
        skill=skill,
        frontmatter=frontmatter,
        metadata=metadata,
        invocation=invocation,
        sync_source_dir=skill_dir,
        sync_dir_name=os.path.basename(skill_dir),
    )


def _load_skills_from_dir(root_dir: str, source: str = "") -> List[SkillEntry]:
    if not os.path.isdir(root_dir):
        return []
    root_skill = _load_single_skill_directory(root_dir, source)
    if root_skill:
        return [root_skill]
    results = []
    try:
        entries = sorted(os.listdir(root_dir))
    except OSError:
        return []
    for entry_name in entries:
        if entry_name.startswith(".") or entry_name.startswith("_"):
            continue
        sub_dir = os.path.join(root_dir, entry_name)
        if not os.path.isdir(sub_dir):
            continue
        skill_entry = _load_single_skill_directory(sub_dir, source)
        if skill_entry:
            results.append(skill_entry)
    return results


def load_skill_entries(
    workspace_dir: str,
    config_dir: Optional[str] = None,
    bundled_skills_dir: Optional[str] = None,
    extra_dirs: Optional[List[str]] = None,
    enabled_skills: Optional[Dict[str, bool]] = None,
    skill_filter: Optional[List[str]] = None,
    bundled_allowlist: Optional[List[str]] = None,
) -> List[SkillEntry]:
    home_dir = os.path.expanduser("~")
    if config_dir is None:
        config_dir = os.path.join(home_dir, ".miniclaw")

    all_entries: Dict[str, SkillEntry] = {}

    load_sources = [
        (extra_dirs or [], "miniclaw-extra"),
        (bundled_skills_dir, "miniclaw-bundled"),
        (os.path.join(config_dir, "skills"), "miniclaw-managed"),
        (os.path.join(home_dir, ".agents", "skills"), "agents-skills-personal"),
        (os.path.join(workspace_dir, ".agents", "skills"), "agents-skills-project"),
        (os.path.join(workspace_dir, "skills"), "miniclaw-workspace"),
    ]

    for source_item, source_label in load_sources:
        if source_item is None:
            continue
        dirs = source_item if isinstance(source_item, list) else [source_item]
        for d in dirs:
            if not d or not os.path.isdir(d):
                continue
            entries = _load_skills_from_dir(d, source_label)
            for entry in entries:
                key = resolve_skill_key(entry.skill.name, entry)
                all_entries[key] = entry

    return filter_skill_entries(
        list(all_entries.values()),
        enabled_skills=enabled_skills,
        skill_filter=skill_filter,
        bundled_allowlist=bundled_allowlist,
    )


def format_skills_for_prompt(entries: List[SkillEntry]) -> str:
    if not entries:
        return ""
    lines = ["<skills>"]
    for entry in entries:
        key = resolve_skill_key(entry.skill.name, entry)
        desc = entry.skill.description
        source = entry.skill.source
        location = entry.skill.base_dir.replace(os.path.expanduser("~"), "~")
        lines.append(f"  <skill name=\"{key}\" source=\"{source}\" location=\"{location}\">")
        lines.append(f"    {desc}")
        lines.append(f"  </skill>")
    lines.append("</skills>")
    return "\n".join(lines)


def build_skill_snapshot(
    workspace_dir: str,
    config_dir: Optional[str] = None,
    bundled_skills_dir: Optional[str] = None,
    extra_dirs: Optional[List[str]] = None,
    enabled_skills: Optional[Dict[str, bool]] = None,
    skill_filter: Optional[List[str]] = None,
    bundled_allowlist: Optional[List[str]] = None,
    max_prompt_chars: int = 8000,
) -> SkillSnapshot:
    import time

    entries = load_skill_entries(
        workspace_dir=workspace_dir,
        config_dir=config_dir,
        bundled_skills_dir=bundled_skills_dir,
        extra_dirs=extra_dirs,
        enabled_skills=enabled_skills,
        skill_filter=skill_filter,
        bundled_allowlist=bundled_allowlist,
    )

    prompt = format_skills_for_prompt(entries)
    if len(prompt) > max_prompt_chars:
        compact_lines = ["<skills>"]
        for entry in entries:
            key = resolve_skill_key(entry.skill.name, entry)
            compact_lines.append(f"  <skill name=\"{key}\" />")
        compact_lines.append("</skills>")
        prompt = "\n".join(compact_lines)
        if len(prompt) > max_prompt_chars:
            prompt = prompt[:max_prompt_chars]

    skills_list = []
    for entry in entries:
        key = resolve_skill_key(entry.skill.name, entry)
        skill_info: Dict = {"name": key}
        if entry.metadata and entry.metadata.primary_env:
            skill_info["primaryEnv"] = entry.metadata.primary_env
        if entry.metadata and entry.metadata.requires_env:
            skill_info["requiredEnv"] = entry.metadata.requires_env
        skills_list.append(skill_info)

    return SkillSnapshot(
        prompt=prompt,
        skills=skills_list,
        skill_filter=skill_filter,
        version=int(time.time()),
    )
