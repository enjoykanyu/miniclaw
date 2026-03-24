"""
MiniClaw MCP (Model Context Protocol) Support
基于官方规范: https://modelcontextprotocol.io/specification/2025-03-26

MCP 是一种开放协议，用于标准化地为 LLM 提供上下文和工具。

核心组件:
1. Protocol - MCP 协议消息类型和构建器
2. Client - MCP 客户端实现（支持 STDIO/SSE/HTTP）
3. Server - MCP 服务器实现
4. Manager - MCP 管理器（单例模式管理多连接）

使用示例:
```python
# 作为客户端使用外部 MCP 服务器
from miniclaw.mcp import mcp_manager, load_mcp_config

# 加载配置
load_mcp_config("mcp_config.yaml")

# 连接所有服务器
await mcp_manager.connect_all()

# 调用工具
result = await mcp_manager.call_tool("read_file", {"path": "/tmp/test.txt"})

# 作为服务器提供工具
from miniclaw.mcp import MCPServerStdio

server = MCPServerStdio(name="my-server")

@server.tool()
def hello(name: str) -> str:
    return f"Hello, {name}!"

await server.run()
```
"""

# 协议层
from miniclaw.mcp.protocol import (
    # 消息类型
    JSONRPCRequest,
    JSONRPCResponse,
    JSONRPCError,
    JSONRPCNotification,
    # MCP 类型
    MCPTool,
    MCPResource,
    MCPPrompt,
    ServerCapabilities,
    ClientCapabilities,
    # 工具
    MCPMessageBuilder,
    parse_jsonrpc_message,
    MCPErrorCode,
    MCP_PROTOCOL_VERSION,
)

# 客户端
from miniclaw.mcp.client import (
    MCPClient,
    MCPServerConfig,
    MCPTransportType,
    MCPClientError,
    MCPConnectionError,
    MCPTimeoutError,
)

# 服务器
from miniclaw.mcp.server import (
    MCPServer,
    MCPServerStdio,
    MCPServerSse,
    MCPServerError,
)

# 管理器
from miniclaw.mcp.manager import (
    MCPManager,
    mcp_manager,
    load_mcp_config,
    init_mcp,
    close_mcp,
)

__all__ = [
    # 协议
    "JSONRPCRequest",
    "JSONRPCResponse",
    "JSONRPCError",
    "JSONRPCNotification",
    "MCPTool",
    "MCPResource",
    "MCPPrompt",
    "ServerCapabilities",
    "ClientCapabilities",
    "MCPMessageBuilder",
    "parse_jsonrpc_message",
    "MCPErrorCode",
    "MCP_PROTOCOL_VERSION",
    # 客户端
    "MCPClient",
    "MCPServerConfig",
    "MCPTransportType",
    "MCPClientError",
    "MCPConnectionError",
    "MCPTimeoutError",
    # 服务器
    "MCPServer",
    "MCPServerStdio",
    "MCPServerSse",
    "MCPServerError",
    # 管理器
    "MCPManager",
    "mcp_manager",
    "load_mcp_config",
    "init_mcp",
    "close_mcp",
]
