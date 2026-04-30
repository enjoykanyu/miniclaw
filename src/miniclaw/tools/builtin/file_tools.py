"""
File Tools - read_file, write_file, list_files

权限分类:
- read_file: FILE_READ (只读，默认允许)
- write_file: FILE_WRITE (写入，需要确认)
- list_files: FILE_READ (只读，默认允许)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from miniclaw.tools.base import BuiltinTool, ToolCategory, ToolParam, ToolResult


class ReadFileTool(BuiltinTool):
    READONLY = True

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return "Read file content from disk. Returns up to 5000 characters."

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.FILE_READ

    @property
    def is_concurrency_safe(self) -> bool:
        return True

    def get_params(self) -> list[ToolParam]:
        return [
            ToolParam(name="path", type=str, description="Absolute file path to read"),
        ]

    async def execute(self, path: str = "", **kwargs) -> ToolResult:
        if not path:
            return ToolResult.fail("path is required")
        try:
            p = Path(path).expanduser().resolve()
            if not p.exists():
                return ToolResult.fail(f"File not found: {path}")
            if p.is_dir():
                return ToolResult.fail(f"Path is a directory, not a file: {path}")
            if p.stat().st_size > 10 * 1024 * 1024:
                return ToolResult.fail(f"File too large (>10MB): {path}")
            content = p.read_text(encoding="utf-8", errors="replace")
            return ToolResult.ok(content[:5000], path=str(p), size=p.stat().st_size)
        except PermissionError:
            return ToolResult.fail(f"Permission denied: {path}")
        except Exception as e:
            return ToolResult.fail(str(e))


class WriteFileTool(BuiltinTool):
    READONLY = False
    DANGEROUS_PATTERNS = []
    requires_confirmation = True

    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return "Write content to a file on disk. Creates parent directories if needed."

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.FILE_WRITE

    @property
    def is_concurrency_safe(self) -> bool:
        return False

    def get_params(self) -> list[ToolParam]:
        return [
            ToolParam(name="path", type=str, description="Absolute file path to write"),
            ToolParam(name="content", type=str, description="Content to write"),
        ]

    async def execute(self, path: str = "", content: str = "", **kwargs) -> ToolResult:
        if not path:
            return ToolResult.fail("path is required")
        try:
            p = Path(path).expanduser().resolve()
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return ToolResult.ok(f"Written {len(content)} chars to {p}", path=str(p))
        except PermissionError:
            return ToolResult.fail(f"Permission denied: {path}")
        except Exception as e:
            return ToolResult.fail(str(e))


class ListFilesTool(BuiltinTool):
    READONLY = True

    @property
    def name(self) -> str:
        return "list_files"

    @property
    def description(self) -> str:
        return "List files and directories in a given path."

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.FILE_READ

    @property
    def is_concurrency_safe(self) -> bool:
        return True

    def get_params(self) -> list[ToolParam]:
        return [
            ToolParam(name="path", type=str, description="Directory path to list"),
            ToolParam(name="recursive", type=bool, description="List recursively", required=False, default=False),
        ]

    async def execute(self, path: str = ".", recursive: bool = False, **kwargs) -> ToolResult:
        try:
            p = Path(path).expanduser().resolve()
            if not p.exists():
                return ToolResult.fail(f"Path not found: {path}")
            if not p.is_dir():
                return ToolResult.fail(f"Not a directory: {path}")

            entries = []
            if recursive:
                for root, dirs, files in os.walk(p):
                    rel_root = Path(root).relative_to(p)
                    for d in sorted(dirs):
                        entries.append(f"  {rel_root / d}/")
                    for f in sorted(files):
                        entries.append(f"  {rel_root / f}")
                    if len(entries) > 200:
                        entries.append(f"  ... (truncated, >200 entries)")
                        break
            else:
                for item in sorted(p.iterdir()):
                    suffix = "/" if item.is_dir() else ""
                    entries.append(f"  {item.name}{suffix}")
                if len(entries) > 100:
                    entries = entries[:100]
                    entries.append("  ... (truncated)")

            result = f"{p}:\n" + "\n".join(entries)
            return ToolResult.ok(result, path=str(p), count=len(entries))
        except PermissionError:
            return ToolResult.fail(f"Permission denied: {path}")
        except Exception as e:
            return ToolResult.fail(str(e))
