"""
MiniClaw 插件系统

对应 OpenClaw 的插件扩展框架，提供：
  - PluginManifest: 插件清单数据类
  - PluginRecord: 插件注册记录
  - PluginRegistry: 插件注册表（全局单例）
  - build_plugin_api: 构建插件 API 表面
"""

from .manifest import PluginManifest, PluginContracts, load_manifest
from .registry import PluginRecord, PluginRegistry, build_plugin_api

# 全局插件注册表单例
plugin_registry = PluginRegistry()
