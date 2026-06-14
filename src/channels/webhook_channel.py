"""
Webhook Channel — HTTP Webhook 通道

对应 OpenClaw 的 Webhook Channel 适配器：
  - 实现 ChannelPlugin Protocol
  - 接收外部平台（Slack、Discord 等）的 Webhook 回调
  - 支持回调 URL 推送或轮询获取响应
  - 不支持流式输出（HTTP 请求-响应模式）
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from loguru import logger

from channel.channel_plugin import (
    ChannelPlugin,
    ChannelMeta,
    ChannelCapabilities,
    BundledChannelEntry,
)


@dataclass
class WebhookMessage:
    """Webhook 消息记录"""
    id: str
    source: str  # 来源平台标识（slack / discord / custom）
    text: str
    callback_url: Optional[str] = None
    response: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    responded_at: Optional[float] = None


class WebhookChannel:
    """Webhook 通道适配器

    实现 ChannelPlugin Protocol，提供 HTTP Webhook 接入能力。
    支持 DM 模式，不支持流式输出。
    外部平台通过 POST 请求发送消息，响应通过回调 URL 推送或轮询获取。
    """

    id: str = "webhook"
    meta: ChannelMeta = ChannelMeta(
        name="Webhook Channel",
        description="HTTP Webhook channel",
        icon="🔗",
        order=20,
    )
    capabilities: ChannelCapabilities = ChannelCapabilities(
        dm=True,
        groups=False,
        mentions=False,
        streaming=False,
    )

    def __init__(self) -> None:
        self._running: bool = False
        self._pending: dict[str, WebhookMessage] = {}
        self._routes_registered: bool = False

    async def start(self, account_id: str) -> None:
        """启动 Webhook 通道，注册端点"""
        self._running = True
        self._routes_registered = True
        logger.info(f"Webhook channel started for account: {account_id}")

    async def stop(self, account_id: str) -> None:
        """停止 Webhook 通道，注销端点"""
        self._running = False
        self._routes_registered = False
        logger.info(f"Webhook channel stopped for account: {account_id}")

    async def send(self, account_id: str, target: str, text: str) -> None:
        """发送响应

        如果消息有 callback_url，则 POST 到回调地址；
        否则存储到待轮询列表。

        Args:
            account_id: 账号 ID
            target: 目标消息 ID（用于匹配请求）
            text: 响应文本
        """
        if not self._running:
            return

        msg = self._pending.get(target)
        if msg:
            msg.response = text
            msg.responded_at = time.time()

            if msg.callback_url:
                # 异步推送到回调 URL
                asyncio.create_task(self._post_callback(msg.callback_url, text))
            # 已响应的消息保留一段时间后清理
            logger.debug(f"Webhook response sent for message: {target}")
        else:
            logger.warning(f"Webhook message not found: {target}")

    async def receive(self, source: str, text: str, callback_url: Optional[str] = None) -> str:
        """接收来自外部平台的 Webhook 消息

        Args:
            source: 来源平台标识
            text: 消息文本
            callback_url: 可选的回调 URL

        Returns:
            消息 ID（用于后续匹配响应）
        """
        msg_id = str(uuid.uuid4())
        msg = WebhookMessage(
            id=msg_id,
            source=source,
            text=text,
            callback_url=callback_url,
        )
        self._pending[msg_id] = msg
        logger.info(f"Webhook message received: {msg_id} from {source}")
        return msg_id

    def get_response(self, msg_id: str) -> Optional[str]:
        """轮询获取消息响应"""
        msg = self._pending.get(msg_id)
        if msg and msg.response is not None:
            return msg.response
        return None

    async def _post_callback(self, url: str, text: str) -> None:
        """POST 响应到回调 URL"""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                payload = {"text": text}
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status >= 400:
                        logger.warning(f"Webhook callback failed: {resp.status} for {url}")
        except ImportError:
            logger.warning("aiohttp not installed, webhook callback skipped")
        except Exception as e:
            logger.error(f"Webhook callback error: {e}")

    @property
    def is_running(self) -> bool:
        return self._running


def create_webhook_channel_entry() -> BundledChannelEntry:
    """创建 Webhook 通道的捆绑入口"""
    return BundledChannelEntry(
        id="webhook",
        name="Webhook Channel",
        description="HTTP Webhook channel",
        _plugin_loader=lambda: WebhookChannel(),
    )
