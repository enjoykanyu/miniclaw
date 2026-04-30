"""
MiniClaw Tool Registry

集中管理所有工具的注册、发现和查找
借鉴 hermes-agent 的自注册模式 + cc-haha 的工具池合并

用法:
    from miniclaw.tools.registry import registry

    # 注册工具
    registry.register(my_tool)

    # 获取所有工具
    tools = registry.get_all_tools()

    # 获取 LangChain 格式工具
    lc_tools = registry.get_langchain_tools()

    # 按分类获取
    file_tools = registry.get_tools_by_category(ToolCategory.FILE_READ)
"""

from __future__ import annotations

import logging
from typing import Optional

from miniclaw.tools.base import Tool, ToolCategory, MCPToolProxy

logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    工具注册表

    特性:
    1. 按名称注册/查找工具
    2. 按分类过滤工具
    3. MCP 工具自动前缀 (mcp__server__tool)
    4. 内置工具优先（同名覆盖 MCP 工具）
    5. 导出为 LangChain BaseTool 列表
    """

    def __init__(self):
        self._tools: dict[str, Tool] = {}
        self._builtin_names: set[str] = set()
        self._mcp_names: set[str] = set()

    def register(self, tool: Tool, override: bool = False) -> None:
        name = tool.name
        if name in self._tools and not override:
            if isinstance(tool, MCPToolProxy) and name not in self._mcp_names:
                logger.debug(f"Built-in tool '{name}' takes priority over MCP tool, skipping")
                return
            if not isinstance(tool, MCPToolProxy) and name in self._builtin_names:
                logger.warning(f"Tool '{name}' already registered as builtin, skipping")
                return

        self._tools[name] = tool
        if isinstance(tool, MCPToolProxy):
            self._mcp_names.add(name)
        else:
            self._builtin_names.add(name)
        logger.debug(f"Registered tool: {name} ({tool.category.value})")

    def unregister(self, name: str) -> None:
        if name in self._tools:
            del self._tools[name]
            self._builtin_names.discard(name)
            self._mcp_names.discard(name)

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def get_all_tools(self) -> list[Tool]:
        return list(self._tools.values())

    def get_tool_names(self) -> list[str]:
        return list(self._tools.keys())

    def get_tools_by_category(self, category: ToolCategory) -> list[Tool]:
        return [t for t in self._tools.values() if t.category == category]

    def get_builtin_tools(self) -> list[Tool]:
        return [t for t in self._tools.values() if t.name in self._builtin_names]

    def get_mcp_tools(self) -> list[MCPToolProxy]:
        return [t for t in self._tools.values() if isinstance(t, MCPToolProxy)]

    def get_langchain_tools(self) -> list:
        return [t.to_langchain_tool() for t in self._tools.values()]

    def has(self, name: str) -> bool:
        return name in self._tools

    def clear(self) -> None:
        self._tools.clear()
        self._builtin_names.clear()
        self._mcp_names.clear()

    def clear_mcp_tools(self) -> None:
        for name in list(self._mcp_names):
            self._tools.pop(name, None)
        self._mcp_names.clear()

    def summary(self) -> dict:
        categories = {}
        for tool in self._tools.values():
            cat = tool.category.value
            categories[cat] = categories.get(cat, 0) + 1
        return {
            "total": len(self._tools),
            "builtin": len(self._builtin_names),
            "mcp": len(self._mcp_names),
            "categories": categories,
        }


registry = ToolRegistry()
