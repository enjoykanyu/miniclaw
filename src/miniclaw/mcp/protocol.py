"""
MCP (Model Context Protocol) Protocol Implementation
基于官方规范: https://modelcontextprotocol.io/specification/2025-03-26

核心概念:
1. JSON-RPC 2.0 消息格式
2. 生命周期管理: initialize → initialized → operation → shutdown
3. 能力协商 (Capability Negotiation)
4. 三种传输方式: STDIO、SSE、Streamable HTTP
"""

from typing import Dict, Any, Optional, List, Union, Literal
from dataclasses import dataclass, field
from enum import Enum
import json
from datetime import datetime


# ============ MCP 协议常量 ============

JSONRPC_VERSION = "2.0"
MCP_PROTOCOL_VERSION = "2025-03-26"


class MCPErrorCode(int, Enum):
    """MCP 标准错误码"""
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    
    # MCP 特定错误码
    RESOURCE_NOT_FOUND = -32002
    RESOURCE_ACCESS_DENIED = -32001
    TOOL_NOT_FOUND = -32601
    TOOL_EXECUTION_ERROR = -32000


# ============ 基础消息类型 ============

@dataclass
class JSONRPCMessage:
    """JSON-RPC 基础消息"""
    jsonrpc: str = JSONRPC_VERSION
    
    def to_dict(self) -> Dict[str, Any]:
        return {"jsonrpc": self.jsonrpc}
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict())


@dataclass
class JSONRPCRequest(JSONRPCMessage):
    """JSON-RPC 请求"""
    method: str = ""
    params: Optional[Dict[str, Any]] = None
    id: Optional[Union[str, int]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data["method"] = self.method
        if self.params is not None:
            data["params"] = self.params
        if self.id is not None:
            data["id"] = self.id
        return data


@dataclass
class JSONRPCResponse(JSONRPCMessage):
    """JSON-RPC 响应"""
    result: Optional[Any] = None
    id: Optional[Union[str, int]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data["result"] = self.result
        data["id"] = self.id
        return data


@dataclass
class JSONRPCError(JSONRPCMessage):
    """JSON-RPC 错误"""
    error: Dict[str, Any] = field(default_factory=dict)
    id: Optional[Union[str, int]] = None
    
    @classmethod
    def create(cls, code: int, message: str, data: Any = None, id: Optional[Union[str, int]] = None):
        error = {"code": code, "message": message}
        if data is not None:
            error["data"] = data
        return cls(error=error, id=id)
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data["error"] = self.error
        data["id"] = self.id
        return data


@dataclass
class JSONRPCNotification(JSONRPCMessage):
    """JSON-RPC 通知 (无 id)"""
    method: str = ""
    params: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data["method"] = self.method
        if self.params is not None:
            data["params"] = self.params
        return data


# ============ MCP 能力定义 ============

@dataclass
class ServerCapabilities:
    """服务器能力声明"""
    tools: Optional[Dict[str, Any]] = None
    resources: Optional[Dict[str, Any]] = None
    prompts: Optional[Dict[str, Any]] = None
    logging: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        caps = {}
        if self.tools is not None:
            caps["tools"] = self.tools
        if self.resources is not None:
            caps["resources"] = self.resources
        if self.prompts is not None:
            caps["prompts"] = self.prompts
        if self.logging is not None:
            caps["logging"] = self.logging
        return caps


@dataclass
class ClientCapabilities:
    """客户端能力声明"""
    roots: Optional[Dict[str, Any]] = None
    sampling: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        caps = {}
        if self.roots is not None:
            caps["roots"] = self.roots
        if self.sampling is not None:
            caps["sampling"] = self.sampling
        return caps


# ============ MCP 特定类型 ============

@dataclass
class MCPTool:
    """MCP 工具定义"""
    name: str
    description: str
    inputSchema: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.inputSchema,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MCPTool":
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            inputSchema=data.get("inputSchema", {}),
        )


@dataclass
class MCPResource:
    """MCP 资源定义"""
    uri: str
    name: str
    description: Optional[str] = None
    mimeType: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        data = {
            "uri": self.uri,
            "name": self.name,
        }
        if self.description:
            data["description"] = self.description
        if self.mimeType:
            data["mimeType"] = self.mimeType
        return data


@dataclass
class MCPPrompt:
    """MCP 提示模板定义"""
    name: str
    description: Optional[str] = None
    arguments: Optional[List[Dict[str, Any]]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        data = {"name": self.name}
        if self.description:
            data["description"] = self.description
        if self.arguments:
            data["arguments"] = self.arguments
        return data


# ============ 消息解析 ============

def parse_jsonrpc_message(data: Union[str, Dict[str, Any]]) -> Union[
    JSONRPCRequest, JSONRPCResponse, JSONRPCError, JSONRPCNotification
]:
    """解析 JSON-RPC 消息"""
    if isinstance(data, str):
        data = json.loads(data)
    
    if "error" in data:
        return JSONRPCError(
            error=data["error"],
            id=data.get("id"),
        )
    
    if "result" in data:
        return JSONRPCResponse(
            result=data.get("result"),
            id=data.get("id"),
        )
    
    if "id" not in data:
        return JSONRPCNotification(
            method=data.get("method", ""),
            params=data.get("params"),
        )
    
    return JSONRPCRequest(
        method=data.get("method", ""),
        params=data.get("params"),
        id=data.get("id"),
    )


# ============ 标准请求/响应构建器 ============

class MCPMessageBuilder:
    """MCP 消息构建器"""
    
    _id_counter = 0
    
    @classmethod
    def next_id(cls) -> int:
        cls._id_counter += 1
        return cls._id_counter
    
    @classmethod
    def initialize(cls, client_capabilities: Optional[ClientCapabilities] = None) -> JSONRPCRequest:
        """构建 initialize 请求"""
        return JSONRPCRequest(
            method="initialize",
            params={
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": client_capabilities.to_dict() if client_capabilities else {},
                "clientInfo": {
                    "name": "miniclaw-client",
                    "version": "0.1.0",
                },
            },
            id=cls.next_id(),
        )
    
    @classmethod
    def initialized(cls) -> JSONRPCNotification:
        """构建 initialized 通知"""
        return JSONRPCNotification(method="notifications/initialized")
    
    @classmethod
    def list_tools(cls) -> JSONRPCRequest:
        """构建 tools/list 请求"""
        return JSONRPCRequest(
            method="tools/list",
            id=cls.next_id(),
        )
    
    @classmethod
    def call_tool(cls, name: str, arguments: Dict[str, Any]) -> JSONRPCRequest:
        """构建 tools/call 请求"""
        return JSONRPCRequest(
            method="tools/call",
            params={
                "name": name,
                "arguments": arguments,
            },
            id=cls.next_id(),
        )
    
    @classmethod
    def list_resources(cls) -> JSONRPCRequest:
        """构建 resources/list 请求"""
        return JSONRPCRequest(
            method="resources/list",
            id=cls.next_id(),
        )
    
    @classmethod
    def read_resource(cls, uri: str) -> JSONRPCRequest:
        """构建 resources/read 请求"""
        return JSONRPCRequest(
            method="resources/read",
            params={"uri": uri},
            id=cls.next_id(),
        )
    
    @classmethod
    def list_prompts(cls) -> JSONRPCRequest:
        """构建 prompts/list 请求"""
        return JSONRPCRequest(
            method="prompts/list",
            id=cls.next_id(),
        )
    
    @classmethod
    def get_prompt(cls, name: str, arguments: Optional[Dict[str, Any]] = None) -> JSONRPCRequest:
        """构建 prompts/get 请求"""
        params = {"name": name}
        if arguments:
            params["arguments"] = arguments
        return JSONRPCRequest(
            method="prompts/get",
            params=params,
            id=cls.next_id(),
        )
    
    @classmethod
    def shutdown(cls) -> JSONRPCRequest:
        """构建 shutdown 请求"""
        return JSONRPCRequest(
            method="shutdown",
            id=cls.next_id(),
        )
    
    @classmethod
    def exit_notification(cls) -> JSONRPCNotification:
        """构建 exit 通知"""
        return JSONRPCNotification(method="exit")
