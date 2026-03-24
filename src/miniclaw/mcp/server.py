"""
MCP Server Implementation
支持 STDIO、SSE、HTTP 三种传输方式
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional, List, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod

from miniclaw.mcp.protocol import (
    JSONRPCRequest, JSONRPCResponse, JSONRPCError, JSONRPCNotification,
    parse_jsonrpc_message, MCPMessageBuilder,
    MCPTool, MCPResource, MCPPrompt,
    ServerCapabilities, ClientCapabilities,
    MCPErrorCode, MCP_PROTOCOL_VERSION,
)

logger = logging.getLogger(__name__)


class MCPServerError(Exception):
    """MCP 服务器错误"""
    pass


@dataclass
class ToolHandler:
    """工具处理器"""
    tool: MCPTool
    handler: Callable[[Dict[str, Any]], Any]


@dataclass
class ResourceHandler:
    """资源处理器"""
    resource: MCPResource
    handler: Callable[[], Any]


@dataclass
class PromptHandler:
    """提示模板处理器"""
    prompt: MCPPrompt
    handler: Callable[[Optional[Dict[str, Any]]], Any]


class MCPServer:
    """
    MCP 服务器基类
    
    提供工具、资源、提示模板的注册和管理
    """
    
    def __init__(
        self,
        name: str,
        version: str = "0.1.0",
        capabilities: Optional[ServerCapabilities] = None,
    ):
        self.name = name
        self.version = version
        self.capabilities = capabilities or ServerCapabilities(
            tools={"listChanged": True},
            resources={"subscribe": True, "listChanged": True},
            prompts={"listChanged": True},
        )
        
        # 注册表
        self._tools: Dict[str, ToolHandler] = {}
        self._resources: Dict[str, ResourceHandler] = {}
        self._prompts: Dict[str, PromptHandler] = {}
        
        # 客户端信息
        self._client_capabilities: Optional[ClientCapabilities] = None
        self._client_info: Optional[Dict[str, Any]] = None
        
        # 状态
        self._initialized = False
        self._request_id = 0
    
    # ============ 工具注册 ============
    
    def register_tool(
        self,
        name: str,
        description: str,
        input_schema: Dict[str, Any],
        handler: Callable[[Dict[str, Any]], Any],
    ) -> None:
        """注册工具"""
        tool = MCPTool(
            name=name,
            description=description,
            inputSchema=input_schema,
        )
        self._tools[name] = ToolHandler(tool=tool, handler=handler)
        logger.info(f"Registered tool: {name}")
    
    def tool(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        input_schema: Optional[Dict[str, Any]] = None,
    ):
        """工具装饰器"""
        def decorator(func: Callable) -> Callable:
            tool_name = name or func.__name__
            tool_desc = description or func.__doc__ or f"Tool: {tool_name}"
            schema = input_schema or self._infer_schema(func)
            
            self.register_tool(tool_name, tool_desc, schema, func)
            return func
        return decorator
    
    def _infer_schema(self, func: Callable) -> Dict[str, Any]:
        """从函数签名推断输入 schema"""
        import inspect
        sig = inspect.signature(func)
        
        properties = {}
        required = []
        
        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue
                
            param_type = "string"
            if param.annotation != inspect.Parameter.empty:
                if param.annotation == int:
                    param_type = "integer"
                elif param.annotation == float:
                    param_type = "number"
                elif param.annotation == bool:
                    param_type = "boolean"
                elif param.annotation == list or param.annotation == List:
                    param_type = "array"
                elif param.annotation == dict or param.annotation == Dict:
                    param_type = "object"
            
            properties[param_name] = {"type": param_type}
            
            if param.default == inspect.Parameter.empty:
                required.append(param_name)
        
        return {
            "type": "object",
            "properties": properties,
            "required": required,
        }
    
    # ============ 资源注册 ============
    
    def register_resource(
        self,
        uri: str,
        name: str,
        description: Optional[str] = None,
        mime_type: Optional[str] = None,
        handler: Optional[Callable[[], Any]] = None,
    ) -> None:
        """注册资源"""
        resource = MCPResource(
            uri=uri,
            name=name,
            description=description,
            mimeType=mime_type,
        )
        self._resources[uri] = ResourceHandler(
            resource=resource,
            handler=handler or (lambda: None),
        )
        logger.info(f"Registered resource: {uri}")
    
    # ============ 提示模板注册 ============
    
    def register_prompt(
        self,
        name: str,
        description: Optional[str] = None,
        arguments: Optional[List[Dict[str, Any]]] = None,
        handler: Optional[Callable[[Optional[Dict[str, Any]]], Any]] = None,
    ) -> None:
        """注册提示模板"""
        prompt = MCPPrompt(
            name=name,
            description=description,
            arguments=arguments,
        )
        self._prompts[name] = PromptHandler(
            prompt=prompt,
            handler=handler or (lambda args: None),
        )
        logger.info(f"Registered prompt: {name}")
    
    # ============ 请求处理 ============
    
    async def handle_request(self, request_data: Union[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """处理请求"""
        try:
            message = parse_jsonrpc_message(request_data)
            
            if isinstance(message, JSONRPCRequest):
                return await self._handle_method(message)
            elif isinstance(message, JSONRPCNotification):
                await self._handle_notification(message)
                return None
            else:
                return JSONRPCError.create(
                    code=MCPErrorCode.INVALID_REQUEST,
                    message="Invalid message type",
                ).to_dict()
                
        except Exception as e:
            logger.error(f"Error handling request: {e}")
            return JSONRPCError.create(
                code=MCPErrorCode.INTERNAL_ERROR,
                message=str(e),
            ).to_dict()
    
    async def _handle_method(self, request: JSONRPCRequest) -> Dict[str, Any]:
        """处理方法调用"""
        method = request.method
        params = request.params or {}
        
        # 初始化前只允许 initialize 方法
        if not self._initialized and method != "initialize":
            return JSONRPCError.create(
                code=MCPErrorCode.INVALID_REQUEST,
                message="Server not initialized",
                id=request.id,
            ).to_dict()
        
        handlers = {
            "initialize": self._handle_initialize,
            "tools/list": self._handle_tools_list,
            "tools/call": self._handle_tools_call,
            "resources/list": self._handle_resources_list,
            "resources/read": self._handle_resources_read,
            "prompts/list": self._handle_prompts_list,
            "prompts/get": self._handle_prompts_get,
            "shutdown": self._handle_shutdown,
        }
        
        handler = handlers.get(method)
        if not handler:
            return JSONRPCError.create(
                code=MCPErrorCode.METHOD_NOT_FOUND,
                message=f"Method not found: {method}",
                id=request.id,
            ).to_dict()
        
        try:
            result = await handler(params)
            return JSONRPCResponse(
                result=result,
                id=request.id,
            ).to_dict()
        except Exception as e:
            logger.error(f"Error in {method}: {e}")
            return JSONRPCError.create(
                code=MCPErrorCode.INTERNAL_ERROR,
                message=str(e),
                id=request.id,
            ).to_dict()
    
    async def _handle_notification(self, notification: JSONRPCNotification) -> None:
        """处理通知"""
        method = notification.method
        
        if method == "notifications/initialized":
            self._initialized = True
            logger.info("Client initialized")
        elif method == "exit":
            logger.info("Client requested exit")
        elif method == "$/cancelRequest":
            # 处理取消请求
            pass
    
    # ============ 具体方法处理 ============
    
    async def _handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理 initialize 请求"""
        protocol_version = params.get("protocolVersion", MCP_PROTOCOL_VERSION)
        
        # 保存客户端信息
        self._client_capabilities = ClientCapabilities(
            roots=params.get("capabilities", {}).get("roots"),
            sampling=params.get("capabilities", {}).get("sampling"),
        )
        self._client_info = params.get("clientInfo", {})
        
        logger.info(f"Client initializing: {self._client_info}")
        
        return {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": self.capabilities.to_dict(),
            "serverInfo": {
                "name": self.name,
                "version": self.version,
            },
        }
    
    async def _handle_tools_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理 tools/list 请求"""
        tools = [handler.tool.to_dict() for handler in self._tools.values()]
        return {"tools": tools}
    
    async def _handle_tools_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理 tools/call 请求"""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        if tool_name not in self._tools:
            raise MCPServerError(f"Tool not found: {tool_name}")
        
        handler = self._tools[tool_name]
        
        # 执行工具
        try:
            if asyncio.iscoroutinefunction(handler.handler):
                result = await handler.handler(arguments)
            else:
                result = handler.handler(arguments)
            
            # 格式化结果
            content = self._format_tool_result(result)
            return {"content": content}
            
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Error: {str(e)}",
                    }
                ],
                "isError": True,
            }
    
    def _format_tool_result(self, result: Any) -> List[Dict[str, Any]]:
        """格式化工具结果为 MCP 内容格式"""
        if isinstance(result, list):
            return result
        
        if isinstance(result, dict):
            if "type" in result:
                return [result]
            return [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]
        
        return [{"type": "text", "text": str(result)}]
    
    async def _handle_resources_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理 resources/list 请求"""
        resources = [handler.resource.to_dict() for handler in self._resources.values()]
        return {"resources": resources}
    
    async def _handle_resources_read(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理 resources/read 请求"""
        uri = params.get("uri")
        
        if uri not in self._resources:
            raise MCPServerError(f"Resource not found: {uri}")
        
        handler = self._resources[uri]
        
        if asyncio.iscoroutinefunction(handler.handler):
            content = await handler.handler()
        else:
            content = handler.handler()
        
        return {"contents": [{"uri": uri, "text": str(content)}]}
    
    async def _handle_prompts_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理 prompts/list 请求"""
        prompts = [handler.prompt.to_dict() for handler in self._prompts.values()]
        return {"prompts": prompts}
    
    async def _handle_prompts_get(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理 prompts/get 请求"""
        name = params.get("name")
        arguments = params.get("arguments", {})
        
        if name not in self._prompts:
            raise MCPServerError(f"Prompt not found: {name}")
        
        handler = self._prompts[name]
        
        if asyncio.iscoroutinefunction(handler.handler):
            result = await handler.handler(arguments)
        else:
            result = handler.handler(arguments)
        
        return {
            "description": handler.prompt.description,
            "messages": result if isinstance(result, list) else [{"role": "user", "content": {"type": "text", "text": str(result)}}],
        }
    
    async def _handle_shutdown(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理 shutdown 请求"""
        self._initialized = False
        return None


class MCPServerStdio(MCPServer):
    """
    STDIO 传输的 MCP 服务器
    """
    
    async def run(self) -> None:
        """运行 STDIO 服务器"""
        logger.info(f"Starting MCP server (STDIO): {self.name}")
        
        try:
            while True:
                # 读取输入
                line = await asyncio.get_event_loop().run_in_executor(
                    None, input
                )
                
                if not line:
                    continue
                
                # 处理请求
                response = await self.handle_request(line)
                
                # 发送响应（通知无响应）
                if response:
                    print(json.dumps(response), flush=True)
                    
        except EOFError:
            logger.info("STDIO input closed")
        except Exception as e:
            logger.error(f"Server error: {e}")


class MCPServerSse(MCPServer):
    """
    SSE 传输的 MCP 服务器
    """
    
    def __init__(self, *args, host: str = "localhost", port: int = 3000, **kwargs):
        super().__init__(*args, **kwargs)
        self.host = host
        self.port = port
        self._clients: Dict[str, Any] = {}
    
    async def run(self) -> None:
        """运行 SSE 服务器"""
        from aiohttp import web
        
        app = web.Application()
        app.router.add_get("/sse", self._handle_sse)
        app.router.add_post("/message", self._handle_message)
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        
        logger.info(f"Starting MCP server (SSE): {self.name} on {self.host}:{self.port}")
        await site.start()
        
        # 保持运行
        while True:
            await asyncio.sleep(3600)
    
    async def _handle_sse(self, request):
        """处理 SSE 连接"""
        from aiohttp import web
        
        response = web.StreamResponse()
        response.headers["Content-Type"] = "text/event-stream"
        response.headers["Cache-Control"] = "no-cache"
        response.headers["Connection"] = "keep-alive"
        await response.prepare(request)
        
        client_id = str(id(request))
        self._clients[client_id] = response
        
        try:
            while True:
                await asyncio.sleep(1)
        except:
            pass
        finally:
            del self._clients[client_id]
        
        return response
    
    async def _handle_message(self, request):
        """处理消息"""
        from aiohttp import web
        
        data = await request.json()
        response = await self.handle_request(data)
        
        return web.json_response(response or {})
