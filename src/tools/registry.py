from tools.base import Tool, ToolCategory, MCPToolProxy, BuiltinTool
from typing import Optional, List, Dict, Any

class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def has(self, name: str) -> bool:
        return name in self._tools

    def get_all_tools(self) -> Dict[str, Tool]:
        return dict(self._tools)

    def get_langchain_tools(self) -> list:
        tools = []
        for t in self._tools.values():
            if t.langchain_tool is not None:
                tools.append(t.langchain_tool)
        return tools

    def get_tools_by_category(self, category: ToolCategory) -> List[Tool]:
        return [t for t in self._tools.values() if t.category == category]

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

registry = ToolRegistry()
