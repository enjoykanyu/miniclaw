"""
Shell Tool - bash

权限分类: SHELL (需要确认，危险命令检测)
"""

from __future__ import annotations

import subprocess
from typing import Any

from miniclaw.tools.base import BuiltinTool, ToolCategory, ToolParam, ToolResult


class BashTool(BuiltinTool):
    READONLY = False
    requires_confirmation = True

    @property
    def name(self) -> str:
        return "bash"

    @property
    def description(self) -> str:
        return "Execute a shell command and return stdout/stderr. Use with caution."

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.SHELL

    @property
    def is_concurrency_safe(self) -> bool:
        return False

    def get_params(self) -> list[ToolParam]:
        return [
            ToolParam(name="command", type=str, description="Shell command to execute"),
            ToolParam(name="timeout", type=int, description="Timeout in seconds", required=False, default=30),
            ToolParam(name="cwd", type=str, description="Working directory", required=False, default=None),
        ]

    async def execute(
        self, command: str = "", timeout: int = 30, cwd: str | None = None, **kwargs
    ) -> ToolResult:
        if not command:
            return ToolResult.fail("command is required")
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd,
            )
            output = result.stdout[:5000] if result.stdout else ""
            error = result.stderr[:2000] if result.stderr else ""

            if result.returncode != 0:
                content = f"Exit code: {result.returncode}\n"
                if output:
                    content += f"stdout:\n{output}\n"
                if error:
                    content += f"stderr:\n{error}\n"
                return ToolResult(
                    success=False,
                    content=content,
                    error=f"Command exited with code {result.returncode}",
                    metadata={"returncode": result.returncode},
                )

            content = output or "(no output)"
            if error:
                content += f"\nstderr:\n{error}"
            return ToolResult.ok(content, returncode=result.returncode)

        except subprocess.TimeoutExpired:
            return ToolResult.fail(f"Command timed out after {timeout}s")
        except Exception as e:
            return ToolResult.fail(str(e))
