"""
MiniClaw MCP (Model Context Protocol) Support
Enables integration with MCP servers and tools
"""

from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import json
from pathlib import Path


class MCPTransportType(str, Enum):
    STDIO = "stdio"
    HTTP = "http"
    WEBSOCKET = "websocket"


@dataclass
class MCPServerConfig:
    name: str
    command: Optional[str] = None
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    transport: MCPTransportType = MCPTransportType.STDIO
    url: Optional[str] = None


@dataclass
class MCPTool:
    name: str
    description: str
    input_schema: Dict[str, Any] = field(default_factory=dict)
    server_name: Optional[str] = None


class MCPClient:
    def __init__(self, config: MCPServerConfig):
        self.config = config
        self._tools: Dict[str, MCPTool] = {}
        self._process: Optional[asyncio.subprocess.Process] = None
    
    async def connect(self) -> None:
        if self.config.transport == MCPTransportType.STDIO and self.config.command:
            self._process = await asyncio.create_subprocess_exec(
                self.config.command,
                *self.config.args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=self.config.env,
            )
    
    async def disconnect(self) -> None:
        if self._process:
            self._process.terminate()
            await self._process.wait()
    
    async def list_tools(self) -> List[MCPTool]:
        if not self._process:
            return []
        
        request = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        
        self._process.stdin.write((json.dumps(request) + "\n").encode())
        await self._process.stdin.drain()
        
        response_line = await self._process.stdout.readline()
        response = json.loads(response_line.decode())
        
        tools = []
        for tool_data in response.get("result", {}).get("tools", []):
            tool = MCPTool(
                name=tool_data.get("name", ""),
                description=tool_data.get("description", ""),
                input_schema=tool_data.get("inputSchema", {}),
                server_name=self.config.name,
            )
            tools.append(tool)
            self._tools[tool.name] = tool
        
        return tools
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        if not self._process:
            raise RuntimeError("MCP client not connected")
        
        request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
        }
        
        self._process.stdin.write((json.dumps(request) + "\n").encode())
        await self._process.stdin.drain()
        
        response_line = await self._process.stdout.readline()
        response = json.loads(response_line.decode())
        
        return response.get("result", {}).get("content", [])


class MCPManager:
    _instance: Optional["MCPManager"] = None
    _servers: Dict[str, MCPClient] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def add_server(self, config: MCPServerConfig) -> None:
        client = MCPClient(config)
        self._servers[config.name] = client
    
    async def connect_server(self, server_name: str) -> None:
        if server_name in self._servers:
            await self._servers[server_name].connect()
    
    async def connect_all(self) -> None:
        for client in self._servers.values():
            await client.connect()
    
    async def disconnect_all(self) -> None:
        for client in self._servers.values():
            await client.disconnect()
    
    def get_tools(self, server_name: Optional[str] = None) -> List[MCPTool]:
        if server_name:
            client = self._servers.get(server_name)
            return list(client._tools.values()) if client else []
        
        all_tools = []
        for client in self._servers.values():
            all_tools.extend(client._tools.values())
        
        return all_tools
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        for client in self._servers.values():
            if tool_name in client._tools:
                return await client.call_tool(tool_name, arguments)
        
        raise ValueError(f"Tool not found: {tool_name}")


mcp_manager = MCPManager()


def load_mcp_config(config_path: str = "mcp_config.yaml") -> None:
    config_file = Path(config_path)
    
    if not config_file.exists():
        return
    
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
        )
        mcp_manager.add_server(mcp_config)
