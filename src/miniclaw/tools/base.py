"""
MiniClaw Tool System - Base Classes

核心抽象:
1. ToolParam - 工具参数定义
2. ToolResult - 工具执行结果
3. Tool - 工具基类（所有工具必须继承）
4. BuiltinTool - 内置工具基类（带权限检查）
5. MCPToolProxy - MCP 远程工具代理
"""

from __future__ import annotations

import asyncio
import time
import traceback
from abc import ABC, abstractmethod
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Union, Awaitable

from langchain_core.tools import BaseTool
from langchain_core.messages import ToolMessage
from pydantic import BaseModel, Field, create_model


class PermissionBehavior(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"


class PermissionMode(str, Enum):
    DEFAULT = "default"
    PLAN = "plan"
    AUTO = "auto"
    BYPASS = "bypass"
    DONT_ASK = "dont_ask"


class ToolCategory(str, Enum):
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    SHELL = "shell"
    SEARCH = "search"
    WEB = "web"
    MCP = "mcp"
    SYSTEM = "system"


@dataclass
class ToolParam:
    name: str
    type: type = str
    description: str = ""
    required: bool = True
    default: Any = None


@dataclass
class ToolResult:
    success: bool
    content: str
    error: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_tool_message(self, tool_call_id: str) -> ToolMessage:
        return ToolMessage(
            content=self.content if self.success else f"Error: {self.error or self.content}",
            tool_call_id=tool_call_id,
        )

    @classmethod
    def ok(cls, content: str, **metadata) -> "ToolResult":
        return cls(success=True, content=content, metadata=metadata)

    @classmethod
    def fail(cls, error: str, content: str = "") -> "ToolResult":
        return cls(success=False, content=content, error=error)


@dataclass
class PermissionDecision:
    behavior: PermissionBehavior
    reason: str = ""
    tool_name: str = ""
    rule_source: str = ""


class Tool(ABC):
    """
    工具基类

    所有工具必须实现:
    - name: 工具名称
    - description: 工具描述
    - execute: 异步执行函数
    - get_params: 参数定义

    可选实现:
    - check_permissions: 权限检查（默认允许）
    - category: 工具分类（默认 SYSTEM）
    - is_concurrency_safe: 是否可并发执行（默认 False）
    """

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        ...

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.SYSTEM

    @property
    def is_concurrency_safe(self) -> bool:
        return False

    @property
    def requires_confirmation(self) -> bool:
        return False

    @abstractmethod
    def get_params(self) -> list[ToolParam]:
        ...

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        ...

    def check_permissions(self, args: dict[str, Any], mode: PermissionMode = PermissionMode.DEFAULT) -> PermissionDecision:
        return PermissionDecision(behavior=PermissionBehavior.ALLOW)

    def _build_args_schema(self) -> type[BaseModel]:
        params = self.get_params()
        fields = {}
        for p in params:
            if p.required:
                fields[p.name] = (p.type, Field(description=p.description))
            else:
                fields[p.name] = (p.type | None, Field(default=p.default, description=p.description))
        return create_model(f"{self.name}Args", **fields) if fields else create_model(f"{self.name}Args")

    def to_langchain_tool(self) -> BaseTool:
        from langchain_core.tools import Tool as LCTool

        async def _arun(**kwargs) -> str:
            result = await self.execute(**kwargs)
            return result.content if result.success else f"Error: {result.error}"

        def _run(**kwargs) -> str:
            return asyncio.get_event_loop().run_until_complete(_arun(**kwargs))

        return LCTool(
            name=self.name,
            description=self.description,
            func=_run,
            coroutine=_arun,
            args_schema=self._build_args_schema(),
        )


class BuiltinTool(Tool):
    """
    内置工具基类

    提供标准化的权限检查和危险操作检测
    """

    DANGEROUS_PATTERNS: list[str] = []
    READONLY: bool = True

    def check_permissions(self, args: dict[str, Any], mode: PermissionMode = PermissionMode.DEFAULT) -> PermissionDecision:
        if mode == PermissionMode.PLAN and not self.READONLY:
            return PermissionDecision(
                behavior=PermissionBehavior.DENY,
                reason="Plan mode only allows readonly tools",
                tool_name=self.name,
                rule_source="mode",
            )

        if self.DANGEROUS_PATTERNS:
            for pattern in self.DANGEROUS_PATTERNS:
                for arg_val in args.values():
                    if isinstance(arg_val, str) and pattern in arg_val:
                        return PermissionDecision(
                            behavior=PermissionBehavior.ASK,
                            reason=f"Dangerous pattern detected: {pattern}",
                            tool_name=self.name,
                            rule_source="dangerous_pattern",
                        )

        if self.requires_confirmation:
            return PermissionDecision(
                behavior=PermissionBehavior.ASK,
                reason=f"Tool {self.name} requires confirmation",
                tool_name=self.name,
                rule_source="requires_confirmation",
            )

        return PermissionDecision(behavior=PermissionBehavior.ALLOW)


class MCPToolProxy(Tool):
    """
    MCP 远程工具代理

    将 MCP 服务器上的工具代理为本地 Tool 对象
    命名格式: mcp__{server_name}__{tool_name}
    """

    def __init__(
        self,
        server_name: str,
        tool_name: str,
        description: str,
        input_schema: dict[str, Any],
        call_fn: Callable[[str, dict[str, Any]], Awaitable[ToolResult]],
    ):
        self._server_name = server_name
        self._tool_name = tool_name
        self._description = description
        self._input_schema = input_schema
        self._call_fn = call_fn
        self._params = self._parse_params(input_schema)

    @property
    def name(self) -> str:
        return f"mcp__{self._server_name}__{self._tool_name}"

    @property
    def original_name(self) -> str:
        return self._tool_name

    @property
    def server_name(self) -> str:
        return self._server_name

    @property
    def description(self) -> str:
        return self._description

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.MCP

    @property
    def is_concurrency_safe(self) -> bool:
        return True

    def get_params(self) -> list[ToolParam]:
        return self._params

    async def execute(self, **kwargs) -> ToolResult:
        try:
            return await self._call_fn(self._tool_name, kwargs)
        except asyncio.TimeoutError:
            return ToolResult.fail(f"MCP tool {self.name} timed out")
        except asyncio.CancelledError:
            task = asyncio.current_task()
            if task is not None and task.cancelling() > 0:
                raise
            return ToolResult.fail(f"MCP tool {self.name} was cancelled")
        except Exception as e:
            return ToolResult.fail(f"MCP tool {self.name} error: {e}")

    def check_permissions(self, args: dict[str, Any], mode: PermissionMode = PermissionMode.DEFAULT) -> PermissionDecision:
        if mode == PermissionMode.PLAN:
            return PermissionDecision(
                behavior=PermissionBehavior.ASK,
                reason="MCP tools require confirmation in plan mode",
                tool_name=self.name,
                rule_source="mcp_plan_mode",
            )
        return PermissionDecision(behavior=PermissionBehavior.ALLOW)

    @staticmethod
    def _parse_params(schema: dict[str, Any]) -> list[ToolParam]:
        type_map = {
            "string": str, "integer": int, "number": float,
            "boolean": bool, "array": list, "object": dict,
        }
        properties = schema.get("properties", {})
        required = set(schema.get("required", []))
        params = []
        for prop_name, prop_def in properties.items():
            prop_type = type_map.get(prop_def.get("type", "string"), str)
            params.append(ToolParam(
                name=prop_name,
                type=prop_type,
                description=prop_def.get("description", ""),
                required=prop_name in required,
                default=None if prop_name in required else prop_def.get("default"),
            ))
        return params
