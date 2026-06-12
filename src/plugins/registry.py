"""
插件注册表 — 动态扩展框架

对应 OpenClaw 的插件系统：
  - 管理插件的注册、注销和查询
  - 桥接插件与 Gateway 的工具、钩子、通道、方法、HTTP 路由
  - build_plugin_api 为插件构建标准化的 API 表面

设计原则：
  1. 插件通过 miniclaw.plugin.json 声明元数据和契约
  2. 注册表负责生命周期管理和资源分配
  3. 插件卸载时自动清理所有注册的资源
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from loguru import logger

from .manifest import PluginManifest, load_manifest


@dataclass
class PluginRecord:
    """插件注册记录

    对应 OpenClaw 的 PluginRecord，跟踪插件的加载状态和错误信息。
    """
    manifest: PluginManifest
    plugin_dir: str
    loaded: bool = False
    enabled: bool = True
    error: Optional[str] = None


class PluginRegistry:
    """插件注册表

    对应 OpenClaw 的 PluginRegistry，提供插件的注册、查询和资源管理。
    每个插件可以注册工具、钩子、通道、Gateway 方法和 HTTP 路由。
    """

    def __init__(self) -> None:
        self._plugins: dict[str, PluginRecord] = {}
        self._tools: dict[str, dict[str, Any]] = {}       # plugin_id -> {tool_name: tool}
        self._hooks: dict[str, dict[str, Callable]] = {}   # plugin_id -> {hook_name: handler}
        self._channels: dict[str, dict[str, Any]] = {}     # plugin_id -> {channel_id: channel}
        self._gateway_methods: dict[str, dict[str, Callable]] = {}  # plugin_id -> {method_name: handler}
        self._http_routes: dict[str, list[dict[str, Any]]] = {}     # plugin_id -> [{method, path, handler}]

    # ── 清单加载 ──

    def load_manifest(self, plugin_dir: str | Path) -> PluginManifest:
        """从插件目录加载并校验 miniclaw.plugin.json 清单"""
        return load_manifest(plugin_dir)

    # ── 插件注册 / 注销 ──

    def register(self, record: PluginRecord) -> None:
        """注册一个插件"""
        if record.manifest.id in self._plugins:
            logger.warning(f"Plugin already registered, overwriting: {record.manifest.id}")
        self._plugins[record.manifest.id] = record
        # 初始化资源容器
        self._tools.setdefault(record.manifest.id, {})
        self._hooks.setdefault(record.manifest.id, {})
        self._channels.setdefault(record.manifest.id, {})
        self._gateway_methods.setdefault(record.manifest.id, {})
        self._http_routes.setdefault(record.manifest.id, [])
        record.loaded = True
        logger.info(f"Plugin registered: {record.manifest.id} v{record.manifest.version}")

    def unregister(self, plugin_id: str) -> None:
        """注销一个插件，清理所有注册的资源"""
        if plugin_id not in self._plugins:
            logger.warning(f"Plugin not found for unregister: {plugin_id}")
            return

        # 清理注册的资源
        self._tools.pop(plugin_id, None)
        self._hooks.pop(plugin_id, None)
        self._channels.pop(plugin_id, None)
        self._gateway_methods.pop(plugin_id, None)
        self._http_routes.pop(plugin_id, None)

        del self._plugins[plugin_id]
        logger.info(f"Plugin unregistered: {plugin_id}")

    # ── 查询 ──

    def get_plugin(self, plugin_id: str) -> Optional[PluginRecord]:
        """获取指定插件"""
        return self._plugins.get(plugin_id)

    def list_plugins(self) -> list[PluginRecord]:
        """列出所有已注册插件"""
        return list(self._plugins.values())

    # ── 资源注册 ──

    def register_tool(self, plugin_id: str, tool: Any) -> None:
        """注册一个工具到插件"""
        if plugin_id not in self._plugins:
            raise KeyError(f"Plugin not registered: {plugin_id}")
        tool_name = getattr(tool, "name", str(tool))
        self._tools[plugin_id][tool_name] = tool
        logger.debug(f"Tool registered: {plugin_id}/{tool_name}")

    def register_hook(self, plugin_id: str, hook_name: str, handler: Callable) -> None:
        """注册一个钩子到插件"""
        if plugin_id not in self._plugins:
            raise KeyError(f"Plugin not registered: {plugin_id}")
        self._hooks[plugin_id][hook_name] = handler
        logger.debug(f"Hook registered: {plugin_id}/{hook_name}")

    def register_channel(self, plugin_id: str, channel: Any) -> None:
        """注册一个通道到插件"""
        if plugin_id not in self._plugins:
            raise KeyError(f"Plugin not registered: {plugin_id}")
        channel_id = getattr(channel, "id", str(channel))
        self._channels[plugin_id][channel_id] = channel
        logger.debug(f"Channel registered: {plugin_id}/{channel_id}")

    def register_gateway_method(self, plugin_id: str, method_name: str, handler: Callable) -> None:
        """注册一个 Gateway 方法到插件"""
        if plugin_id not in self._plugins:
            raise KeyError(f"Plugin not registered: {plugin_id}")
        self._gateway_methods[plugin_id][method_name] = handler
        logger.debug(f"Gateway method registered: {plugin_id}/{method_name}")

    def register_http_route(self, plugin_id: str, method: str, path: str, handler: Callable) -> None:
        """注册一个 HTTP 路由到插件"""
        if plugin_id not in self._plugins:
            raise KeyError(f"Plugin not registered: {plugin_id}")
        self._http_routes[plugin_id].append({
            "method": method.upper(),
            "path": path,
            "handler": handler,
        })
        logger.debug(f"HTTP route registered: {plugin_id} {method.upper()} {path}")

    # ── 资源查询 ──

    def get_all_tools(self) -> dict[str, Any]:
        """获取所有插件注册的工具"""
        result: dict[str, Any] = {}
        for plugin_tools in self._tools.values():
            result.update(plugin_tools)
        return result

    def get_all_hooks(self) -> dict[str, dict[str, Callable]]:
        """获取所有插件注册的钩子"""
        return dict(self._hooks)

    def get_all_channels(self) -> dict[str, Any]:
        """获取所有插件注册的通道"""
        result: dict[str, Any] = {}
        for plugin_channels in self._channels.values():
            result.update(plugin_channels)
        return result

    def get_all_gateway_methods(self) -> dict[str, Callable]:
        """获取所有插件注册的 Gateway 方法"""
        result: dict[str, Callable] = {}
        for plugin_methods in self._gateway_methods.values():
            result.update(plugin_methods)
        return result

    def get_all_http_routes(self) -> list[dict[str, Any]]:
        """获取所有插件注册的 HTTP 路由"""
        result: list[dict[str, Any]] = []
        for routes in self._http_routes.values():
            result.extend(routes)
        return result


def build_plugin_api(record: PluginRecord, registry: PluginRegistry) -> dict[str, Any]:
    """为插件构建标准化的 API 表面

    对应 OpenClaw 的 buildPluginApi，插件通过返回的 API 对象
    与 Gateway 交互（注册工具、钩子、通道等）。

    Args:
        record: 插件注册记录
        registry: 插件注册表

    Returns:
        包含注册方法的 API 对象
    """
    plugin_id = record.manifest.id

    return {
        "registerTool": lambda tool: registry.register_tool(plugin_id, tool),
        "registerHook": lambda hook_name, handler: registry.register_hook(plugin_id, hook_name, handler),
        "registerChannel": lambda channel: registry.register_channel(plugin_id, channel),
        "registerGatewayMethod": lambda method_name, handler: registry.register_gateway_method(plugin_id, method_name, handler),
        "registerHttpRoute": lambda method, path, handler: registry.register_http_route(plugin_id, method, path, handler),
        "manifest": record.manifest,
    }
