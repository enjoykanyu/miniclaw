from __future__ import annotations
from typing import Optional
from .channel_plugin import ChannelPlugin

_LOADED: dict[str, ChannelPlugin] = {}
_BUNDLED: dict[str, ChannelPlugin] = {}

_ALIASES: dict[str, str] = {
    "tg": "telegram", "dc": "discord",
    "wa": "whatsapp", "sl": "slack",
}

def _normalize_id(raw: str) -> str:
    """对应 normalizeChatChannelId"""
    lower = raw.strip().lower()
    return _ALIASES.get(lower, lower)

def register_channel(
        plugin: ChannelPlugin, *, bundled: bool = False,
) -> None:
    """注册通道插件到注册表"""
    target = _BUNDLED if bundled else _LOADED
    target[plugin.id] = plugin

def get_channel_plugin(
        channel_id: str,
) -> Optional[ChannelPlugin]:
    """对应 getChannelPlugin: 三级查找"""
    nid = _normalize_id(channel_id)
    return _LOADED.get(nid) or _BUNDLED.get(nid)

def list_channel_plugins() -> list[ChannelPlugin]:
    """对应 listLoadedChannelPlugins + dedupeChannels"""
    seen: set[str] = set()
    result: list[ChannelPlugin] = []
    for p in list(_LOADED.values()) + list(_BUNDLED.values()):
        if p.id not in seen:
            seen.add(p.id)
            result.append(p)
    result.sort(key=lambda p: p.meta.order)
    return result