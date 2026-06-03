import os
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from memory.types import (
    CANONICAL_ROOT_MEMORY_FILENAME,
    MEMORY_DIR_NAME,
    DREAMS_FILENAME,
    MemorySource,
)


def is_memory_path(rel_path: str) -> bool:
    normalized = rel_path.replace("\\", "/").lstrip("/")
    if normalized == CANONICAL_ROOT_MEMORY_FILENAME:
        return True
    if normalized.lower() == DREAMS_FILENAME.lower():
        return True
    return normalized.startswith(MEMORY_DIR_NAME + "/")


def resolve_root_memory_file(workspace_dir: str) -> Optional[str]:
    canonical = os.path.join(workspace_dir, CANONICAL_ROOT_MEMORY_FILENAME)
    if os.path.isfile(canonical):
        return canonical
    legacy = os.path.join(workspace_dir, "memory.md")
    if os.path.isfile(legacy):
        return legacy
    return None


def list_memory_files(workspace_dir: str, extra_paths: Optional[List[str]] = None) -> List[str]:
    result: List[str] = []
    root_file = resolve_root_memory_file(workspace_dir)
    if root_file:
        result.append(root_file)
    memory_dir = os.path.join(workspace_dir, MEMORY_DIR_NAME)
    if os.path.isdir(memory_dir):
        result.extend(_collect_md_files(memory_dir))
    if extra_paths:
        for ep in extra_paths:
            if os.path.isfile(ep) and ep.endswith(".md"):
                abs_ep = os.path.abspath(ep)
                if abs_ep not in result:
                    result.append(abs_ep)
            elif os.path.isdir(ep):
                for f in _collect_md_files(ep):
                    abs_f = os.path.abspath(f)
                    if abs_f not in result:
                        result.append(abs_f)
    return sorted(result)


def _collect_md_files(directory: str) -> List[str]:
    result = []
    for root, _dirs, files in os.walk(directory):
        for fname in sorted(files):
            if fname.endswith(".md"):
                result.append(os.path.join(root, fname))
    return result


def parse_date_from_memory_path(rel_path: str) -> Optional[datetime]:
    normalized = rel_path.replace("\\", "/")
    match = re.search(r"memory/(\d{4}-\d{2}-\d{2})\.md", normalized)
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y-%m-%d")
        except ValueError:
            return None
    return None


def is_evergreen_path(rel_path: str) -> bool:
    normalized = rel_path.replace("\\", "/").lstrip("/")
    if normalized == CANONICAL_ROOT_MEMORY_FILENAME:
        return True
    if normalized.lower() == DREAMS_FILENAME.lower():
        return True
    if normalized.startswith(MEMORY_DIR_NAME + "/"):
        basename = os.path.basename(normalized)
        if not re.match(r"\d{4}-\d{2}-\d{2}", basename):
            return True
    return False


def ensure_memory_dir(workspace_dir: str) -> str:
    memory_dir = os.path.join(workspace_dir, MEMORY_DIR_NAME)
    os.makedirs(memory_dir, exist_ok=True)
    return memory_dir


def get_daily_memory_path(workspace_dir: str, date: Optional[datetime] = None) -> str:
    date = date or datetime.now()
    memory_dir = ensure_memory_dir(workspace_dir)
    return os.path.join(memory_dir, f"{date.strftime('%Y-%m-%d')}.md")


def read_memory_file(file_path: str) -> str:
    if not os.path.isfile(file_path):
        return ""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def write_memory_file(file_path: str, content: str, append: bool = False) -> bool:
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        mode = "a" if append else "w"
        with open(file_path, mode, encoding="utf-8") as f:
            f.write(content)
            if not content.endswith("\n"):
                f.write("\n")
        return True
    except Exception:
        return False


def append_to_daily_memory(workspace_dir: str, content: str, date: Optional[datetime] = None) -> bool:
    file_path = get_daily_memory_path(workspace_dir, date)
    if os.path.isfile(file_path):
        return write_memory_file(file_path, f"\n{content}", append=True)
    return write_memory_file(file_path, content)


def chunk_markdown(text: str, max_chunk_chars: int = 2000, overlap: int = 200) -> List[Tuple[int, int, str]]:
    if not text.strip():
        return []
    lines = text.split("\n")
    chunks = []
    current_lines = []
    current_start = 0
    current_len = 0

    for i, line in enumerate(lines):
        line_len = len(line) + 1
        if current_len + line_len > max_chunk_chars and current_lines:
            chunk_text = "\n".join(current_lines)
            chunks.append((current_start, current_start + len(current_lines) - 1, chunk_text))
            overlap_lines = []
            overlap_len = 0
            for ol in reversed(current_lines):
                if overlap_len + len(ol) + 1 > overlap:
                    break
                overlap_lines.insert(0, ol)
                overlap_len += len(ol) + 1
            current_start = i - len(overlap_lines)
            current_lines = overlap_lines
            current_len = overlap_len
        current_lines.append(line)
        current_len += line_len

    if current_lines:
        chunk_text = "\n".join(current_lines)
        chunks.append((current_start, current_start + len(current_lines) - 1, chunk_text))

    return chunks


def get_relative_path(file_path: str, workspace_dir: str) -> str:
    try:
        return os.path.relpath(file_path, workspace_dir).replace("\\", "/")
    except ValueError:
        return file_path
