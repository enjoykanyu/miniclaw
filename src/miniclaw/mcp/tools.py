from miniclaw.tools.base import MCPToolProxy, ToolCategory, Tool
from miniclaw.tools.registry import registry
from typing import Dict, List, Optional

class MCPToolRegistry:
    def __init__(self):
        self._servers: Dict[str, dict] = {}
        self._tools: Dict[str, MCPToolProxy] = {}

    def register_server(self, name: str, config: dict) -> None:
        self._servers[name] = config

    def register_tool(self, tool: MCPToolProxy) -> None:
        self._tools[tool.name] = tool

    def get_all_tools(self) -> List[MCPToolProxy]:
        return list(self._tools.values())

    def get_langchain_tools(self) -> list:
        return []

    def has(self, name: str) -> bool:
        return name in self._tools

mcp_tool_registry = MCPToolRegistry()
