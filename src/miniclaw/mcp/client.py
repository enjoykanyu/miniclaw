"""
MCP Client Implementation
支持 STDIO、SSE、HTTP 三种传输方式
"""

import asyncio
import json
import logging
import os
from typing import Dict, Any, Optional, List, Callable, AsyncGenerator
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import aiohttp

from miniclaw.mcp.protocol import (
    JSONRPCRequest, JSONRPCResponse, JSONRPCError, JSONRPCNotification,
    parse_jsonrpc_message, MCPMessageBuilder,
    MCPTool, MCPResource, MCPPrompt,
    ClientCapabilities, ServerCapabilities,
    MCPErrorCode, MCP_PROTOCOL_VERSION,
)

logger = logging.getLogger(__name__)


class MCPTransportType(str, Enum):
    """MCP 传输类型"""
    STDIO = "stdio"
    SSE = "sse"
    HTTP = "http"


@dataclass
class MCPServerConfig:
    """MCP 服务器配置"""
    name: str
    command: Optional[str] = None
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    transport: MCPTransportType = MCPTransportType.STDIO
    url: Optional[str] = None
    timeout: float = 30.0


class MCPClientError(Exception):
    """MCP 客户端错误"""
    pass


class MCPConnectionError(MCPClientError):
    """MCP 连接错误"""
    pass


class MCPTimeoutError(MCPClientError):
    """MCP 超时错误"""
    pass


class MCPClient:
    """
    MCP 客户端
    
    支持三种传输方式:
    1. STDIO: 通过子进程标准输入输出通信
    2. SSE: Server-Sent Events
    3. HTTP: HTTP POST 请求
    """
    
    def __init__(self, config: MCPServerConfig):
        self.config = config
        self._tools: Dict[str, MCPTool] = {}
        self._resources: Dict[str, MCPResource] = {}
        self._prompts: Dict[str, MCPPrompt] = {}
        
        # STDIO 模式
        self._process: Optional[asyncio.subprocess.Process] = None
        self._stdin_lock = asyncio.Lock()
        self._pending_requests: Dict[Union[str, int], asyncio.Future] = {}
        
        # HTTP/SSE 模式
        self._session: Optional[aiohttp.ClientSession] = None
        self._sse_task: Optional[asyncio.Task] = None
        
        # 服务器能力
        self._server_capabilities: Optional[ServerCapabilities] = None
        self._server_info: Optional[Dict[str, Any]] = None
        
        # 状态
        self._initialized = False
        self._message_id = 0
    
    @property
    def tools(self) -> List[MCPTool]:
        """获取已发现的工具列表"""
        return list(self._tools.values())
    
    @property
    def resources(self) -> List[MCPResource]:
        """获取已发现的资源列表"""
        return list(self._resources.values())
    
    @property
    def prompts(self) -> List[MCPPrompt]:
        """获取已发现的提示模板列表"""
        return list(self._prompts.values())
    
    async def connect(self) -> None:
        """连接到 MCP 服务器"""
        if self.config.transport == MCPTransportType.STDIO:
            await self._connect_stdio()
        elif self.config.transport in (MCPTransportType.SSE, MCPTransportType.HTTP):
            await self._connect_http()
        
        # 执行初始化握手
        await self._initialize()
    
    async def _connect_stdio(self) -> None:
        """STDIO 模式连接"""
        if not self.config.command:
            raise MCPConnectionError("STDIO transport requires a command")
        
        try:
            self._process = await asyncio.create_subprocess_exec(
                self.config.command,
                *self.config.args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**dict(os.environ), **self.config.env},
            )
            
            # 启动消息读取循环
            asyncio.create_task(self._read_stdio_messages())
            
            logger.info(f"Connected to MCP server via STDIO: {self.config.name}")
            
        except Exception as e:
            raise MCPConnectionError(f"Failed to connect via STDIO: {e}")
    
    async def _connect_http(self) -> None:
        """HTTP/SSE 模式连接"""
        if not self.config.url:
            raise MCPConnectionError("HTTP/SSE transport requires a URL")
        
        self._session = aiohttp.ClientSession()
        
        if self.config.transport == MCPTransportType.SSE:
            # 启动 SSE 连接
            self._sse_task = asyncio.create_task(self._connect_sse())
        
        logger.info(f"Connected to MCP server via {self.config.transport}: {self.config.name}")
    
    async def _connect_sse(self) -> None:
        """SSE 连接"""
        try:
            async with self._session.get(
                f"{self.config.url}/sse",
                headers={"Accept": "text/event-stream"},
            ) as response:
                async for line in response.content:
                    line = line.decode().strip()
                    if line.startswith("data: "):
                        data = line[6:]
                        await self._handle_message(data)
        except Exception as e:
            logger.error(f"SSE connection error: {e}")
    
    async def _read_stdio_messages(self) -> None:
        """STDIO 消息读取循环"""
        try:
            while self._process and self._process.returncode is None:
                line = await self._process.stdout.readline()
                if not line:
                    break
                
                try:
                    message = line.decode().strip()
                    if message:
                        await self._handle_message(message)
                except Exception as e:
                    logger.error(f"Error parsing message: {e}")
                    
        except Exception as e:
            logger.error(f"STDIO read error: {e}")
    
    async def _handle_message(self, data: str) -> None:
        """处理收到的消息"""
        try:
            message = parse_jsonrpc_message(data)
            
            if isinstance(message, JSONRPCResponse):
                # 处理响应
                if message.id in self._pending_requests:
                    future = self._pending_requests.pop(message.id)
                    future.set_result(message.result)
                    
            elif isinstance(message, JSONRPCError):
                # 处理错误
                if message.id in self._pending_requests:
                    future = self._pending_requests.pop(message.id)
                    future.set_exception(MCPClientError(
                        f"MCP Error {message.error.get('code')}: {message.error.get('message')}"
                    ))
                    
            elif isinstance(message, JSONRPCNotification):
                # 处理通知
                await self._handle_notification(message)
                
        except Exception as e:
            logger.error(f"Error handling message: {e}")
    
    async def _handle_notification(self, notification: JSONRPCNotification) -> None:
        """处理通知消息"""
        method = notification.method
        params = notification.params or {}
        
        if method == "notifications/tools/list_changed":
            # 工具列表变化，重新获取
            await self.discover_tools()
        elif method == "notifications/resources/list_changed":
            # 资源列表变化
            await self.discover_resources()
        elif method == "notifications/prompts/list_changed":
            # 提示模板列表变化
            await self.discover_prompts()
    
    async def _send_request(self, request: JSONRPCRequest) -> Any:
        """发送请求并等待响应"""
        if not self._initialized and request.method != "initialize":
            raise MCPClientError("Client not initialized")
        
        # 创建 Future 等待响应
        future = asyncio.get_event_loop().create_future()
        self._pending_requests[request.id] = future
        
        try:
            # 发送消息
            message = request.to_json()
            
            if self.config.transport == MCPTransportType.STDIO:
                async with self._stdin_lock:
                    self._process.stdin.write((message + "\n").encode())
                    await self._process.stdin.drain()
                    
            elif self.config.transport in (MCPTransportType.SSE, MCPTransportType.HTTP):
                async with self._session.post(
                    f"{self.config.url}/message",
                    json=request.to_dict(),
                    timeout=self.config.timeout,
                ) as response:
                    result = await response.json()
                    if "error" in result:
                        raise MCPClientError(f"MCP Error: {result['error']}")
                    return result.get("result")
            
            # 等待响应
            return await asyncio.wait_for(future, timeout=self.config.timeout)
            
        except asyncio.TimeoutError:
            self._pending_requests.pop(request.id, None)
            raise MCPTimeoutError(f"Request timeout: {request.method}")
        except Exception as e:
            self._pending_requests.pop(request.id, None)
            raise
    
    async def _send_notification(self, notification: JSONRPCNotification) -> None:
        """发送通知（无需响应）"""
        message = notification.to_json()
        
        if self.config.transport == MCPTransportType.STDIO:
            async with self._stdin_lock:
                self._process.stdin.write((message + "\n").encode())
                await self._process.stdin.drain()
                
        elif self.config.transport in (MCPTransportType.SSE, MCPTransportType.HTTP):
            async with self._session.post(
                f"{self.config.url}/message",
                json=notification.to_dict(),
            ) as response:
                pass
    
    async def _initialize(self) -> None:
        """执行初始化握手"""
        # 发送 initialize 请求
        request = MCPMessageBuilder.initialize()
        result = await self._send_request(request)
        
        # 解析服务器能力
        self._server_capabilities = ServerCapabilities(
            tools=result.get("capabilities", {}).get("tools"),
            resources=result.get("capabilities", {}).get("resources"),
            prompts=result.get("capabilities", {}).get("prompts"),
            logging=result.get("capabilities", {}).get("logging"),
        )
        self._server_info = result.get("serverInfo", {})
        
        # 发送 initialized 通知
        await self._send_notification(MCPMessageBuilder.initialized())
        
        self._initialized = True
        logger.info(f"MCP client initialized: {self._server_info}")
    
    async def discover_tools(self) -> List[MCPTool]:
        """发现可用工具"""
        request = MCPMessageBuilder.list_tools()
        result = await self._send_request(request)
        
        tools = []
        for tool_data in result.get("tools", []):
            tool = MCPTool.from_dict(tool_data)
            self._tools[tool.name] = tool
            tools.append(tool)
        
        logger.info(f"Discovered {len(tools)} tools from {self.config.name}")
        return tools
    
    async def discover_resources(self) -> List[MCPResource]:
        """发现可用资源"""
        request = MCPMessageBuilder.list_resources()
        result = await self._send_request(request)
        
        resources = []
        for resource_data in result.get("resources", []):
            resource = MCPResource(
                uri=resource_data.get("uri", ""),
                name=resource_data.get("name", ""),
                description=resource_data.get("description"),
                mimeType=resource_data.get("mimeType"),
            )
            self._resources[resource.uri] = resource
            resources.append(resource)
        
        logger.info(f"Discovered {len(resources)} resources from {self.config.name}")
        return resources
    
    async def discover_prompts(self) -> List[MCPPrompt]:
        """发现可用提示模板"""
        request = MCPMessageBuilder.list_prompts()
        result = await self._send_request(request)
        
        prompts = []
        for prompt_data in result.get("prompts", []):
            prompt = MCPPrompt(
                name=prompt_data.get("name", ""),
                description=prompt_data.get("description"),
                arguments=prompt_data.get("arguments"),
            )
            self._prompts[prompt.name] = prompt
            prompts.append(prompt)
        
        logger.info(f"Discovered {len(prompts)} prompts from {self.config.name}")
        return prompts
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> List[Dict[str, Any]]:
        """调用工具"""
        if tool_name not in self._tools:
            raise MCPClientError(f"Tool not found: {tool_name}")
        
        request = MCPMessageBuilder.call_tool(tool_name, arguments)
        result = await self._send_request(request)
        
        return result.get("content", [])
    
    async def read_resource(self, uri: str) -> List[Dict[str, Any]]:
        """读取资源"""
        request = MCPMessageBuilder.read_resource(uri)
        result = await self._send_request(request)
        
        return result.get("contents", [])
    
    async def get_prompt(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """获取提示模板"""
        request = MCPMessageBuilder.get_prompt(name, arguments)
        result = await self._send_request(request)
        
        return result
    
    async def disconnect(self) -> None:
        """断开连接"""
        try:
            if self._initialized:
                # 发送 shutdown 请求
                try:
                    request = MCPMessageBuilder.shutdown()
                    await self._send_request(request)
                except:
                    pass
                
                # 发送 exit 通知
                try:
                    await self._send_notification(MCPMessageBuilder.exit_notification())
                except:
                    pass
            
            # STDIO 清理
            if self._process:
                self._process.terminate()
                try:
                    await asyncio.wait_for(self._process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    self._process.kill()
                self._process = None
            
            # HTTP/SSE 清理
            if self._sse_task:
                self._sse_task.cancel()
                try:
                    await self._sse_task
                except asyncio.CancelledError:
                    pass
            
            if self._session:
                await self._session.close()
                self._session = None
            
            self._initialized = False
            logger.info(f"Disconnected from MCP server: {self.config.name}")
            
        except Exception as e:
            logger.error(f"Error during disconnect: {e}")
    
    async def __aenter__(self):
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()
