"""
MCP Tools Integration for Agents
将 MCP 工具转换为 LangChain 工具，供 Agent 使用
"""

from typing import Dict, Any, Optional, List, Callable
from langchain_core.tools import BaseTool, Tool
from pydantic import BaseModel, Field, create_model
import json

from miniclaw.mcp.manager import mcp_manager
from miniclaw.mcp.protocol import MCPTool


def create_mcp_tool_wrapper(mcp_tool: MCPTool) -> BaseTool:
    """
    将 MCP 工具包装为 LangChain Tool
    
    Args:
        mcp_tool: MCP 工具定义
    
    Returns:
        LangChain BaseTool
    """
    
    # 从 JSON Schema 创建 Pydantic 模型
    schema = mcp_tool.inputSchema
    properties = schema.get("properties", {})
    required = schema.get("required", [])
    
    # 构建字段定义
    fields = {}
    for prop_name, prop_def in properties.items():
        prop_type = prop_def.get("type", "string")
        description = prop_def.get("description", f"Parameter: {prop_name}")
        
        # 映射 JSON Schema 类型到 Python 类型
        if prop_type == "string":
            field_type = str
        elif prop_type == "integer":
            field_type = int
        elif prop_type == "number":
            field_type = float
        elif prop_type == "boolean":
            field_type = bool
        elif prop_type == "array":
            field_type = list
        elif prop_type == "object":
            field_type = dict
        else:
            field_type = str
        
        # 创建字段
        if prop_name in required:
            fields[prop_name] = (field_type, Field(description=description))
        else:
            fields[prop_name] = (Optional[field_type], Field(default=None, description=description))
    
    # 创建参数模型
    if fields:
        ArgsModel = create_model(f"{mcp_tool.name}Args", **fields)
    else:
        ArgsModel = create_model(f"{mcp_tool.name}Args")
    
    # 定义工具执行函数
    async def execute_tool(**kwargs) -> str:
        """执行 MCP 工具"""
        try:
            result = await mcp_manager.call_tool(mcp_tool.name, kwargs)
            
            # 格式化结果
            if isinstance(result, list):
                texts = []
                for item in result:
                    if isinstance(item, dict):
                        if item.get("type") == "text":
                            texts.append(item.get("text", ""))
                        elif item.get("type") == "image":
                            texts.append(f"[Image: {item.get('mimeType', 'unknown')}]")
                        elif item.get("type") == "resource":
                            texts.append(f"[Resource: {item.get('resource', {})}]")
                return "\n".join(texts) if texts else json.dumps(result, ensure_ascii=False)
            
            return json.dumps(result, ensure_ascii=False)
            
        except Exception as e:
            return f"Error executing tool {mcp_tool.name}: {str(e)}"
    
    # 创建 LangChain Tool
    return Tool(
        name=mcp_tool.name,
        description=mcp_tool.description,
        func=execute_tool,
        coroutine=execute_tool,
        args_schema=ArgsModel,
    )


async def get_all_mcp_tools() -> List[BaseTool]:
    """
    获取所有 MCP 服务器提供的工具，转换为 LangChain Tools
    
    Returns:
        LangChain Tool 列表
    """
    tools = []
    
    for mcp_tool in mcp_manager.get_all_tools():
        try:
            tool = create_mcp_tool_wrapper(mcp_tool)
            tools.append(tool)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to create tool wrapper for {mcp_tool.name}: {e}")
    
    return tools


class MCPToolRegistry:
    """
    MCP 工具注册表
    
    缓存和管理 MCP 工具的 LangChain 包装器
    """
    
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._initialized = False
    
    async def initialize(self) -> None:
        """初始化注册表"""
        if self._initialized:
            return
        
        tools = await get_all_mcp_tools()
        for tool in tools:
            self._tools[tool.name] = tool
        
        self._initialized = True
    
    def get_tool(self, name: str) -> Optional[BaseTool]:
        """获取指定工具"""
        return self._tools.get(name)
    
    def get_all_tools(self) -> List[BaseTool]:
        """获取所有工具"""
        return list(self._tools.values())
    
    def clear(self) -> None:
        """清空注册表"""
        self._tools.clear()
        self._initialized = False


# 全局 MCP 工具注册表
mcp_tool_registry = MCPToolRegistry()
