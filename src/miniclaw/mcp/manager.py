"""
MCP Manager - 管理多个 MCP 客户端连接
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path
import yaml

from miniclaw.mcp.client import MCPClient, MCPServerConfig, MCPTransportType
from miniclaw.mcp.protocol import MCPTool, MCPResource, MCPPrompt

logger = logging.getLogger(__name__)


class MCPManager:
    """
    MCP 管理器
    
    单例模式管理所有 MCP 服务器连接
    """
    
    _instance: Optional["MCPManager"] = None
    _lock = asyncio.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._servers: Dict[str, MCPClient] = {}
        self._initialized = True
    
    def add_server(self, config: MCPServerConfig) -> None:
        """添加服务器配置"""
        if config.name in self._servers:
            logger.warning(f"Server {config.name} already exists, replacing")
        
        client = MCPClient(config)
        self._servers[config.name] = client
        logger.info(f"Added MCP server: {config.name}")
    
    async def connect_server(self, server_name: str) -> None:
        """连接指定服务器"""
        if server_name not in self._servers:
            raise ValueError(f"Server not found: {server_name}")
        
        client = self._servers[server_name]
        await client.connect()
        
        # 自动发现工具、资源、提示模板
        await client.discover_tools()
        
        if client.capabilities.resources:
            await client.discover_resources()
        
        if client.capabilities.prompts:
            await client.discover_prompts()
        
        logger.info(f"Connected to MCP server: {server_name}")
    
    async def connect_all(self) -> None:
        """连接所有服务器"""
        for server_name in self._servers:
            try:
                await self.connect_server(server_name)
            except Exception as e:
                logger.error(f"Failed to connect to {server_name}: {e}")
    
    async def disconnect_server(self, server_name: str) -> None:
        """断开指定服务器"""
        if server_name in self._servers:
            await self._servers[server_name].disconnect()
            logger.info(f"Disconnected from MCP server: {server_name}")
    
    async def disconnect_all(self) -> None:
        """断开所有服务器"""
        for server_name, client in self._servers.items():
            try:
                await client.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting from {server_name}: {e}")
        
        logger.info("Disconnected from all MCP servers")
    
    def get_server(self, server_name: str) -> Optional[MCPClient]:
        """获取指定服务器客户端"""
        return self._servers.get(server_name)
    
    def get_all_tools(self) -> List[MCPTool]:
        """获取所有服务器的工具"""
        all_tools = []
        for client in self._servers.values():
            all_tools.extend(client.tools)
        return all_tools
    
    def get_all_resources(self) -> List[MCPResource]:
        """获取所有服务器的资源"""
        all_resources = []
        for client in self._servers.values():
            all_resources.extend(client.resources)
        return all_resources
    
    def get_all_prompts(self) -> List[MCPPrompt]:
        """获取所有服务器的提示模板"""
        all_prompts = []
        for client in self._servers.values():
            all_prompts.extend(client.prompts)
        return all_prompts
    
    async def call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        server_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        调用工具
        
        Args:
            tool_name: 工具名称
            arguments: 工具参数
            server_name: 指定服务器（可选）
        
        Returns:
            工具执行结果
        """
        if server_name:
            client = self._servers.get(server_name)
            if not client:
                raise ValueError(f"Server not found: {server_name}")
            return await client.call_tool(tool_name, arguments)
        
        # 在所有服务器中查找工具
        for client in self._servers.values():
            if any(t.name == tool_name for t in client.tools):
                return await client.call_tool(tool_name, arguments)
        
        raise ValueError(f"Tool not found: {tool_name}")
    
    async def read_resource(
        self,
        uri: str,
        server_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """读取资源"""
        if server_name:
            client = self._servers.get(server_name)
            if not client:
                raise ValueError(f"Server not found: {server_name}")
            return await client.read_resource(uri)
        
        for client in self._servers.values():
            if any(r.uri == uri for r in client.resources):
                return await client.read_resource(uri)
        
        raise ValueError(f"Resource not found: {uri}")
    
    async def get_prompt(
        self,
        name: str,
        arguments: Optional[Dict[str, Any]] = None,
        server_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """获取提示模板"""
        if server_name:
            client = self._servers.get(server_name)
            if not client:
                raise ValueError(f"Server not found: {server_name}")
            return await client.get_prompt(name, arguments)
        
        for client in self._servers.values():
            if any(p.name == name for p in client.prompts):
                return await client.get_prompt(name, arguments)
        
        raise ValueError(f"Prompt not found: {name}")


# 全局 MCP 管理器实例
mcp_manager = MCPManager()


def load_mcp_config(config_path: str = "mcp_config.yaml") -> None:
    """
    从配置文件加载 MCP 服务器配置
    
    配置文件格式:
    ```yaml
    servers:
      - name: filesystem
        command: mcp-server-filesystem
        args: ["--root", "./data"]
        transport: stdio
        env:
          LOG_LEVEL: info
    ```
    """
    config_file = Path(config_path)
    
    if not config_file.exists():
        logger.warning(f"MCP config file not found: {config_path}")
        return
    
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        
        for server_config in config.get("servers", []):
            mcp_config = MCPServerConfig(
                name=server_config.get("name", ""),
                command=server_config.get("command"),
                args=server_config.get("args", []),
                env=server_config.get("env", {}),
                transport=MCPTransportType(server_config.get("transport", "stdio")),
                url=server_config.get("url"),
                timeout=server_config.get("timeout", 30.0),
            )
            mcp_manager.add_server(mcp_config)
        
        logger.info(f"Loaded {len(config.get('servers', []))} MCP servers from config")
        
    except Exception as e:
        logger.error(f"Error loading MCP config: {e}")


async def init_mcp() -> None:
    """初始化 MCP 连接"""
    load_mcp_config()
    await mcp_manager.connect_all()


async def close_mcp() -> None:
    """关闭 MCP 连接"""
    await mcp_manager.disconnect_all()
