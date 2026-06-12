"""
插件清单加载与校验

对应 OpenClaw 的插件清单（manifest）机制：
  - 从 miniclaw.plugin.json 文件加载插件元数据
  - JSON Schema 校验确保清单格式正确
  - 支持的 kind: channel / provider / tool / hook
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger

# ── miniclaw.plugin.json 的 JSON Schema ──

MANIFEST_SCHEMA: dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "MiniClaw Plugin Manifest",
    "type": "object",
    "required": ["id", "version", "kind"],
    "properties": {
        "id": {
            "type": "string",
            "pattern": "^[a-zA-Z0-9_-]+$",
            "description": "插件唯一标识",
        },
        "version": {
            "type": "string",
            "pattern": r"^\d+\.\d+\.\d+",
            "description": "语义化版本号",
        },
        "description": {
            "type": "string",
            "description": "插件描述",
        },
        "kind": {
            "type": "string",
            "enum": ["channel", "provider", "tool", "hook"],
            "description": "插件类型",
        },
        "configSchema": {
            "type": "object",
            "description": "插件配置的 JSON Schema",
        },
        "channels": {
            "type": "array",
            "items": {"type": "string"},
            "description": "提供的通道 ID 列表",
        },
        "providers": {
            "type": "array",
            "items": {"type": "string"},
            "description": "提供的 Provider ID 列表",
        },
        "contracts": {
            "type": "object",
            "properties": {
                "tools": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "gatewayMethods": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "httpRoutes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["method", "path"],
                        "properties": {
                            "method": {"type": "string"},
                            "path": {"type": "string"},
                        },
                    },
                },
                "hooks": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "services": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "commands": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "description": "插件提供的契约（工具、方法、路由、钩子等）",
        },
    },
    "additionalProperties": True,
}

MANIFEST_FILENAME = "miniclaw.plugin.json"


def _validate_manifest(data: dict[str, Any]) -> list[str]:
    """校验清单数据是否符合 Schema，返回错误列表"""
    errors: list[str] = []

    # 必填字段检查
    for key in ("id", "version", "kind"):
        if key not in data:
            errors.append(f"missing required field: {key}")

    if errors:
        return errors

    # kind 枚举检查
    if data.get("kind") not in ("channel", "provider", "tool", "hook"):
        errors.append(f"invalid kind: {data.get('kind')!r}")

    # id 格式检查
    import re
    if not re.match(r"^[a-zA-Z0-9_-]+$", str(data.get("id", ""))):
        errors.append(f"invalid id format: {data.get('id')!r}")

    # version 格式检查
    if not re.match(r"^\d+\.\d+\.\d+", str(data.get("version", ""))):
        errors.append(f"invalid version format: {data.get('version')!r}")

    return errors


@dataclass
class PluginContracts:
    """插件提供的契约"""
    tools: list[str] = field(default_factory=list)
    gateway_methods: list[str] = field(default_factory=list)
    http_routes: list[dict[str, str]] = field(default_factory=list)
    hooks: list[str] = field(default_factory=list)
    services: list[str] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)


@dataclass
class PluginManifest:
    """对应 OpenClaw 的插件清单

    从 miniclaw.plugin.json 加载的插件元数据，
    描述插件的 ID、版本、类型和提供的契约。
    """
    id: str
    version: str
    kind: str  # channel / provider / tool / hook
    description: str = ""
    config_schema: dict[str, Any] = field(default_factory=dict)
    channels: list[str] = field(default_factory=list)
    providers: list[str] = field(default_factory=list)
    contracts: PluginContracts = field(default_factory=PluginContracts)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PluginManifest:
        """从字典构建 PluginManifest"""
        contracts_data = data.get("contracts", {})
        contracts = PluginContracts(
            tools=contracts_data.get("tools", []),
            gateway_methods=contracts_data.get("gatewayMethods", []),
            http_routes=contracts_data.get("httpRoutes", []),
            hooks=contracts_data.get("hooks", []),
            services=contracts_data.get("services", []),
            commands=contracts_data.get("commands", []),
        )
        return cls(
            id=data["id"],
            version=data["version"],
            kind=data["kind"],
            description=data.get("description", ""),
            config_schema=data.get("configSchema", {}),
            channels=data.get("channels", []),
            providers=data.get("providers", []),
            contracts=contracts,
        )


def load_manifest(plugin_dir: str | Path) -> PluginManifest:
    """从插件目录加载 miniclaw.plugin.json 清单文件

    Args:
        plugin_dir: 插件目录路径

    Returns:
        PluginManifest 实例

    Raises:
        FileNotFoundError: 清单文件不存在
        ValueError: 清单格式校验失败
    """
    plugin_dir = Path(plugin_dir)
    manifest_path = plugin_dir / MANIFEST_FILENAME

    if not manifest_path.exists():
        raise FileNotFoundError(
            f"Plugin manifest not found: {manifest_path}"
        )

    raw = manifest_path.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {manifest_path}: {e}") from e

    errors = _validate_manifest(data)
    if errors:
        raise ValueError(
            f"Manifest validation failed for {manifest_path}: "
            + "; ".join(errors)
        )

    manifest = PluginManifest.from_dict(data)
    logger.info(f"Loaded plugin manifest: {manifest.id} v{manifest.version} ({manifest.kind})")
    return manifest
