from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

class ToolCategory(Enum):
    BUILTIN = "builtin"
    MCP = "mcp"
    CUSTOM = "custom"

@dataclass
class ToolResult:
    output: str
    success: bool = True
    metadata: dict = field(default_factory=dict)

@dataclass
class Tool:
    name: str
    description: str
    category: ToolCategory = ToolCategory.BUILTIN
    func: Optional[Callable] = None
    langchain_tool: Optional[Any] = None

    def execute(self, **kwargs) -> ToolResult:
        if self.func:
            try:
                result = self.func(**kwargs)
                if isinstance(result, ToolResult):
                    return result
                return ToolResult(output=str(result))
            except Exception as e:
                return ToolResult(output=str(e), success=False)
        if self.langchain_tool:
            try:
                result = self.langchain_tool.invoke(kwargs)
                return ToolResult(output=str(result))
            except Exception as e:
                return ToolResult(output=str(e), success=False)
        return ToolResult(output="No execution method", success=False)

class MCPToolProxy:
    def __init__(self, name, description, server_name, schema=None):
        self.name = name
        self.description = description
        self.server_name = server_name
        self.schema = schema or {}

    def execute(self, **kwargs) -> ToolResult:
        return ToolResult(output="MCP tool not connected", success=False)

class BuiltinTool(Tool):
    def __init__(self, name, description, func=None, langchain_tool=None):
        super().__init__(
            name=name,
            description=description,
            category=ToolCategory.BUILTIN,
            func=func,
            langchain_tool=langchain_tool,
        )
