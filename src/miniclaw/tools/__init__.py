"""
MiniClaw Tools Module

核心组件:
- base: Tool 基类、ToolResult、MCPToolProxy
- registry: 工具注册表
- permissions: 权限管理系统
- executor: 工具执行器（权限+并发+Hook）
- mcp_bridge: MCP 远程工具桥接
- builtin/: 内置工具（read_file, write_file, list_files, bash, grep_search）
"""

from miniclaw.tools.base import (
    Tool,
    BuiltinTool,
    MCPToolProxy,
    ToolResult,
    ToolParam,
    ToolCategory,
    PermissionBehavior,
    PermissionMode,
    PermissionDecision,
)
from miniclaw.tools.registry import registry, ToolRegistry
from miniclaw.tools.permissions import permission_manager, PermissionManager, PermissionRule, RuleSource
from miniclaw.tools.executor import tool_executor, ToolExecutor, ToolCall, setup_default_tools
from miniclaw.tools.mcp_bridge import mcp_bridge, MCPBridge

__all__ = [
    "Tool", "BuiltinTool", "MCPToolProxy",
    "ToolResult", "ToolParam", "ToolCategory",
    "PermissionBehavior", "PermissionMode", "PermissionDecision",
    "registry", "ToolRegistry",
    "permission_manager", "PermissionManager", "PermissionRule", "RuleSource",
    "tool_executor", "ToolExecutor", "ToolCall", "setup_default_tools",
    "mcp_bridge", "MCPBridge",
]
