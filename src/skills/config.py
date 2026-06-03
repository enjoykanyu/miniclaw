import os
import platform
import shutil
from typing import Optional, List, Dict

from skills.types import SkillEntry, OpenClawSkillMetadata
from skills.frontmatter import resolve_skill_key


def should_include_skill(
    entry: SkillEntry,
    enabled_skills: Optional[Dict[str, bool]] = None,
    bundled_allowlist: Optional[List[str]] = None,
) -> bool:
    if enabled_skills is None:
        enabled_skills = {}
    if bundled_allowlist is None:
        bundled_allowlist = []

    skill_key = resolve_skill_key(entry.skill.name, entry)

    if skill_key in enabled_skills and enabled_skills[skill_key] is False:
        return False

    if entry.skill.source in ("openclaw-bundled", "bundled"):
        if bundled_allowlist and skill_key not in bundled_allowlist:
            return False

    return _evaluate_runtime_eligibility(entry)


def _evaluate_runtime_eligibility(entry: SkillEntry) -> bool:
    metadata = entry.metadata
    if not metadata:
        return True
    if metadata.always:
        return True

    if metadata.os_list:
        current_os = platform.system().lower()
        os_matched = any(
            _os.lower() in current_os or current_os in _os.lower()
            for _os in metadata.os_list
        )
        if not os_matched:
            return False

    if metadata.requires_bins:
        for bin_name in metadata.requires_bins:
            if not shutil.which(bin_name):
                return False

    if metadata.requires_any_bins:
        any_found = any(shutil.which(b) for b in metadata.requires_any_bins)
        if not any_found:
            return False

    if metadata.requires_env:
        for env_name in metadata.requires_env:
            if not os.environ.get(env_name):
                return False

    return True


def normalize_skill_filter(skill_filter: Optional[List[str]] = None) -> Optional[List[str]]:
    if skill_filter is None:
        return None
    return [s.strip() for s in skill_filter if s.strip()]


def filter_skill_entries(
    entries: List[SkillEntry],
    enabled_skills: Optional[Dict[str, bool]] = None,
    skill_filter: Optional[List[str]] = None,
    bundled_allowlist: Optional[List[str]] = None,
) -> List[SkillEntry]:
    filtered = [
        e for e in entries
        if should_include_skill(e, enabled_skills, bundled_allowlist)
    ]
    normalized_filter = normalize_skill_filter(skill_filter)
    if normalized_filter is not None:
        if normalized_filter:
            filtered = [
                e for e in filtered
                if resolve_skill_key(e.skill.name, e) in normalized_filter
            ]
        else:
            filtered = []
    return filtered
