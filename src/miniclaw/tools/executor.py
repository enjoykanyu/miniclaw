"""
MiniClaw Tool Executor

整合权限检查 + 并发执行 + Hook 的工具执行器
借鉴 cc-haha 的工具执行流水线

执行流程:
1. 查找工具
2. 权限检查 (PermissionManager)
3. Pre-hook 执行
4. 工具执行（并发安全工具可并行）
5. Post-hook 执行
6. 返回 ToolMessage
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable, Optional

from langchain_core.messages import ToolMessage

from miniclaw.tools.base import (
    Tool, ToolResult, PermissionBehavior, PermissionMode, PermissionDecision,
)
from miniclaw.tools.registry import registry
from miniclaw.tools.permissions import permission_manager

logger = logging.getLogger(__name__)


@dataclass
class HookResult:
    proceed: bool = True
    modified_args: dict[str, Any] | None = None
    message: str = ""


HookFn = Callable[[str, dict[str, Any]], Awaitable[HookResult]]


@dataclass
class ToolCall:
    id: str
    name: str
    args: dict[str, Any]


@dataclass
class ExecutionStats:
    total_calls: int = 0
    allowed_calls: int = 0
    denied_calls: int = 0
    error_calls: int = 0
    total_time_ms: float = 0.0


class ToolExecutor:
    """
    工具执行器

    特性:
    1. 权限检查流水线 (deny → ask → tool → security → bypass → allow → default)
    2. 并发安全工具并行执行
    3. Pre/Post Hook 支持
    4. 执行统计
    5. 超时控制
    """

    def __init__(self):
        self._pre_hooks: list[HookFn] = []
        self._post_hooks: list[HookFn] = []
        self._stats = ExecutionStats()
        self._default_timeout: float = 60.0

    def add_pre_hook(self, hook: HookFn) -> None:
        self._pre_hooks.append(hook)

    def add_post_hook(self, hook: HookFn) -> None:
        self._post_hooks.append(hook)

    @property
    def stats(self) -> ExecutionStats:
        return self._stats

    async def execute_tool_call(self, tool_call: ToolCall) -> ToolMessage:
        """
        执行单个工具调用

        完整流程: 查找 → 权限 → pre-hook → 执行 → post-hook → 返回
        """
        start_time = time.monotonic()
        self._stats.total_calls += 1

        tool = registry.get(tool_call.name)
        if tool is None:
            self._stats.error_calls += 1
            return ToolMessage(
                content=f"Error: Tool '{tool_call.name}' not found",
                tool_call_id=tool_call.id,
            )

        # Step 1: 权限检查
        decision = await permission_manager.check(tool, tool_call.args)
        if decision.behavior == PermissionBehavior.DENY:
            self._stats.denied_calls += 1
            elapsed = (time.monotonic() - start_time) * 1000
            self._stats.total_time_ms += elapsed
            return ToolMessage(
                content=f"Permission denied: {decision.reason}",
                tool_call_id=tool_call.id,
            )

        # Step 2: Pre-hooks
        current_args = tool_call.args.copy()
        for hook in self._pre_hooks:
            try:
                hook_result = await hook(tool_call.name, current_args)
                if not hook_result.proceed:
                    self._stats.denied_calls += 1
                    return ToolMessage(
                        content=f"Blocked by pre-hook: {hook_result.message}",
                        tool_call_id=tool_call.id,
                    )
                if hook_result.modified_args is not None:
                    current_args = hook_result.modified_args
            except Exception as e:
                logger.error(f"Pre-hook error for {tool_call.name}: {e}")

        # Step 3: 执行工具
        try:
            result = await asyncio.wait_for(
                tool.execute(**current_args),
                timeout=self._default_timeout,
            )
            self._stats.allowed_calls += 1
        except asyncio.TimeoutError:
            self._stats.error_calls += 1
            result = ToolResult.fail(f"Tool execution timed out after {self._default_timeout}s")
        except Exception as e:
            self._stats.error_calls += 1
            result = ToolResult.fail(f"Tool execution error: {e}")

        # Step 4: Post-hooks
        for hook in self._post_hooks:
            try:
                await hook(tool_call.name, current_args)
            except Exception as e:
                logger.error(f"Post-hook error for {tool_call.name}: {e}")

        elapsed = (time.monotonic() - start_time) * 1000
        self._stats.total_time_ms += elapsed
        logger.debug(f"Tool {tool_call.name} executed in {elapsed:.1f}ms")

        return result.to_tool_message(tool_call.id)

    async def execute_tool_calls(
        self, tool_calls: list[ToolCall]
    ) -> list[ToolMessage]:
        """
        执行多个工具调用

        并发安全工具并行执行，非安全工具串行执行
        """
        if not tool_calls:
            return []

        safe_calls: list[tuple[ToolCall, Tool]] = []
        unsafe_calls: list[tuple[ToolCall, Tool]] = []

        for tc in tool_calls:
            tool = registry.get(tc.name)
            if tool is None:
                safe_calls.append((tc, None))
            elif tool.is_concurrency_safe:
                safe_calls.append((tc, tool))
            else:
                unsafe_calls.append((tc, tool))

        results: list[ToolMessage] = []

        # 并发执行安全工具
        if safe_calls:
            safe_tasks = []
            for tc, tool in safe_calls:
                if tool is None:
                    safe_tasks.append(self._make_not_found_task(tc))
                else:
                    safe_tasks.append(self.execute_tool_call(tc))

            safe_results = await asyncio.gather(*safe_tasks)
            results.extend(safe_results)

        # 串行执行非安全工具
        for tc, tool in unsafe_calls:
            result = await self.execute_tool_call(tc)
            results.append(result)

        return results

    async def _make_not_found_task(self, tc: ToolCall) -> ToolMessage:
        self._stats.error_calls += 1
        return ToolMessage(
            content=f"Error: Tool '{tc.name}' not found",
            tool_call_id=tc.id,
        )

    async def execute_langchain_tool_calls(self, tool_calls: list[dict]) -> list[ToolMessage]:
        """
        从 LangChain tool_calls 格式执行

        LangChain tool_calls 格式:
        [
            {"id": "call_xxx", "name": "read_file", "args": {"path": "/tmp/test.txt"}},
            ...
        ]
        """
        calls = [
            ToolCall(id=tc["id"], name=tc["name"], args=tc.get("args", {}))
            for tc in tool_calls
        ]
        return await self.execute_tool_calls(calls)


def setup_default_tools() -> None:
    """
    注册所有内置工具并初始化默认权限规则

    在应用启动时调用一次
    """
    from miniclaw.tools.builtin import BUILTIN_TOOLS

    for ToolClass in BUILTIN_TOOLS:
        tool = ToolClass()
        registry.register(tool)

    permission_manager.load_default_rules()

    logger.info(f"Registered {len(registry.get_all_tools())} builtin tools")
    logger.info(f"Registry summary: {registry.summary()}")


tool_executor = ToolExecutor()
