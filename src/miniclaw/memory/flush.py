import os
from datetime import datetime
from typing import Optional

from miniclaw.memory.types import MemoryFlushPlan
from miniclaw.memory.files import (
    get_daily_memory_path,
    ensure_memory_dir,
    write_memory_file,
)


DEFAULT_FLUSH_PROMPT = (
    "Pre-compaction memory flush. "
    "Store durable memories only in memory/YYYY-MM-DD.md (create memory/ if needed). "
    "Treat workspace bootstrap/reference files such as MEMORY.md, DREAMS.md, SOUL.md, TOOLS.md, "
    "and AGENTS.md as read-only during this flush. "
    "If memory/YYYY-MM-DD.md already exists, APPEND new content only and do not overwrite existing entries. "
    "Do NOT create timestamped variant files (e.g., YYYY-MM-DD-HHMM.md); "
    "always use the canonical YYYY-MM-DD.md filename. "
    "If nothing to store, reply with <silent>."
)

DEFAULT_FLUSH_SYSTEM_PROMPT = (
    "You are a memory assistant. Your job is to extract important, durable information "
    "from the conversation and write it to the daily memory file. Focus on: "
    "1. User preferences and personal information "
    "2. Important decisions and their rationale "
    "3. Key facts and insights discovered "
    "4. Action items and commitments "
    "Do NOT store: greetings, small talk, or already-known information."
)


def build_memory_flush_plan(
    workspace_dir: str,
    context_window_tokens: int = 128000,
    model: Optional[str] = None,
) -> MemoryFlushPlan:
    date = datetime.now()
    return MemoryFlushPlan(
        soft_threshold_tokens=4000,
        force_flush_transcript_bytes=2 * 1024 * 1024,
        reserve_tokens_floor=20000,
        model=model,
        relative_path=f"memory/{date.strftime('%Y-%m-%d')}.md",
        prompt=DEFAULT_FLUSH_PROMPT,
        system_prompt=DEFAULT_FLUSH_SYSTEM_PROMPT,
    )


def should_run_memory_flush(
    projected_token_count: int,
    context_window_tokens: int,
    reserve_tokens_floor: int = 20000,
    soft_threshold_tokens: int = 4000,
    already_flushed_this_cycle: bool = False,
    transcript_byte_size: int = 0,
    force_flush_transcript_bytes: int = 2 * 1024 * 1024,
) -> bool:
    if already_flushed_this_cycle:
        return False
    token_threshold = context_window_tokens - reserve_tokens_floor - soft_threshold_tokens
    if projected_token_count >= token_threshold:
        return True
    if transcript_byte_size >= force_flush_transcript_bytes:
        return True
    return False


def ensure_memory_flush_target_file(workspace_dir: str, relative_path: str) -> str:
    memory_dir = ensure_memory_dir(workspace_dir)
    target_path = os.path.join(workspace_dir, relative_path)
    target_dir = os.path.dirname(target_path)
    if not os.path.isdir(target_dir):
        os.makedirs(target_dir, exist_ok=True)
    if not os.path.isfile(target_path):
        write_memory_file(target_path, "")
    return target_path
