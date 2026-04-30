"""
Search Tool - grep_search

权限分类: SEARCH (只读，默认允许)
"""

from __future__ import annotations

import subprocess
from typing import Any

from miniclaw.tools.base import BuiltinTool, ToolCategory, ToolParam, ToolResult


class GrepSearchTool(BuiltinTool):
    READONLY = True

    @property
    def name(self) -> str:
        return "grep_search"

    @property
    def description(self) -> str:
        return "Search for a pattern in files using ripgrep (rg). Returns matching lines."

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.SEARCH

    @property
    def is_concurrency_safe(self) -> bool:
        return True

    def get_params(self) -> list[ToolParam]:
        return [
            ToolParam(name="pattern", type=str, description="Regex pattern to search for"),
            ToolParam(name="path", type=str, description="Directory or file to search in", required=False, default="."),
            ToolParam(name="glob", type=str, description="File glob filter (e.g. '*.py')", required=False, default=None),
            ToolParam(name="max_results", type=int, description="Maximum number of results", required=False, default=50),
        ]

    async def execute(
        self,
        pattern: str = "",
        path: str = ".",
        glob: str | None = None,
        max_results: int = 50,
        **kwargs,
    ) -> ToolResult:
        if not pattern:
            return ToolResult.fail("pattern is required")
        try:
            cmd = ["rg", "--no-heading", "--line-number", "--color=never", "--max-count", str(max_results)]
            if glob:
                cmd.extend(["--glob", glob])
            cmd.extend([pattern, path])

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 2:
                return ToolResult.fail(f"ripgrep error: {result.stderr[:500]}")

            if result.returncode == 1:
                return ToolResult.ok("No matches found", matches=0)

            output = result.stdout[:5000]
            match_count = output.count("\n") + 1 if output else 0
            return ToolResult.ok(output, matches=match_count)

        except FileNotFoundError:
            return ToolResult.fail("ripgrep (rg) not installed. Install with: brew install ripgrep")
        except subprocess.TimeoutExpired:
            return ToolResult.fail("Search timed out")
        except Exception as e:
            return ToolResult.fail(str(e))
