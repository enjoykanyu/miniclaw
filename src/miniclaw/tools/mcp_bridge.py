"""
MiniClaw MCP Bridge

将 MCP 远程工具桥接到本地 Tool 注册表
借鉴 hermes-agent 的 MCP 工具注册模式

特性:
1. 自动发现 MCP 服务器工具并注册到 registry
2. 工具名前缀 mcp__{server}__{tool} 避免冲突
3. 环境变量安全过滤（防止密钥泄露给子进程）
4. 错误信息凭证脱敏
5. 支持动态工具发现（tools/list_changed 通知）
6. 超时和取消处理
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Any, Optional

from miniclaw.tools.base import MCPToolProxy, ToolResult
from miniclaw.tools.registry import registry

logger = logging.getLogger(__name__)

_CREDENTIAL_PATTERN = re.compile(
    r"(?:ghp_[A-Za-z0-9_]{1,255}|sk-[A-Za-z0-9_]{1,255}|"
    r"Bearer\s+\S+|token_[A-Za-z0-9_]{1,255}|"
    r"AKIA[A-Z0-9]{16}|[A-Za-z0-9]{40}@apps\.googleusercontent\.com)"
)

_SAFE_ENV_KEYS = frozenset({
    "PATH", "HOME", "USER", "LANG", "LC_ALL", "TERM",
    "SHELL", "TMPDIR", "PWD", "LOGNAME",
})


def sanitize_error(text: str) -> str:
    return _CREDENTIAL_PATTERN.sub("[REDACTED]", text)


def build_safe_env(user_env: dict[str, str] | None = None) -> dict[str, str]:
    env = {}
    for key, value in os.environ.items():
        if key in _SAFE_ENV_KEYS or key.startswith("XDG_"):
            env[key] = value
    if user_env:
        env.update(user_env)
    return env


class MCPBridge:
    """
    MCP 桥接器

    连接 MCP 服务器，发现工具，注册到本地 registry
    """

    def __init__(self, tool_timeout: float = 30.0):
        self._tool_timeout = tool_timeout
        self._connected_servers: dict[str, Any] = {}

    async def connect_and_register(
        self,
        server_name: str,
        client: Any,
    ) -> list[MCPToolProxy]:
        """
        连接 MCP 服务器并注册工具

        Args:
            server_name: 服务器名称（用于工具名前缀）
            client: MCPClient 实例（已连接）

        Returns:
            注册的 MCPToolProxy 列表
        """
        try:
            if not client._initialized:
                await client.connect()
                await client.discover_tools()

            self._connected_servers[server_name] = client

            mcp_tools = client.tools
            proxies = []

            for mcp_tool in mcp_tools:
                proxy = MCPToolProxy(
                    server_name=server_name,
                    tool_name=mcp_tool.name,
                    description=mcp_tool.description or mcp_tool.name,
                    input_schema=mcp_tool.inputSchema,
                    call_fn=self._make_call_fn(server_name, client),
                )
                registry.register(proxy)
                proxies.append(proxy)

            logger.info(
                f"Registered {len(proxies)} MCP tools from server '{server_name}'"
            )
            return proxies

        except Exception as e:
            logger.error(
                f"Failed to connect/register MCP server '{server_name}': "
                f"{sanitize_error(str(e))}"
            )
            return []

    async def refresh_server_tools(self, server_name: str) -> list[MCPToolProxy]:
        """
        刷新 MCP 服务器的工具列表（处理 tools/list_changed 通知）

        1. 移除该服务器的旧工具
        2. 重新发现并注册
        """
        client = self._connected_servers.get(server_name)
        if not client:
            logger.warning(f"MCP server '{server_name}' not connected")
            return []

        old_names = [
            t.name for t in registry.get_mcp_tools()
            if t.server_name == server_name
        ]
        for name in old_names:
            registry.unregister(name)

        try:
            await client.discover_tools()
        except Exception as e:
            logger.error(f"Failed to refresh tools from '{server_name}': {sanitize_error(str(e))}")
            return []

        return await self._register_server_tools(server_name, client)

    async def _register_server_tools(
        self, server_name: str, client: Any
    ) -> list[MCPToolProxy]:
        proxies = []
        for mcp_tool in client.tools:
            proxy = MCPToolProxy(
                server_name=server_name,
                tool_name=mcp_tool.name,
                description=mcp_tool.description or mcp_tool.name,
                input_schema=mcp_tool.inputSchema,
                call_fn=self._make_call_fn(server_name, client),
            )
            registry.register(proxy)
            proxies.append(proxy)
        return proxies

    def _make_call_fn(self, server_name: str, client: Any):
        async def call_tool(tool_name: str, args: dict[str, Any]) -> ToolResult:
            try:
                result = await asyncio.wait_for(
                    client.call_tool(tool_name, args),
                    timeout=self._tool_timeout,
                )
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
                            else:
                                texts.append(str(item))
                        else:
                            texts.append(str(item))
                    return ToolResult.ok("\n".join(texts) if texts else "(no output)")
                return ToolResult.ok(str(result))

            except asyncio.TimeoutError:
                return ToolResult.fail(
                    f"MCP tool call timed out after {self._tool_timeout}s"
                )
            except asyncio.CancelledError:
                task = asyncio.current_task()
                if task is not None and task.cancelling() > 0:
                    raise
                return ToolResult.fail("MCP tool call was cancelled")
            except Exception as e:
                return ToolResult.fail(sanitize_error(str(e)))

        return call_tool

    async def disconnect_all(self) -> None:
        for server_name, client in self._connected_servers.items():
            try:
                await client.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting '{server_name}': {e}")
        self._connected_servers.clear()
        registry.clear_mcp_tools()


mcp_bridge = MCPBridge()
