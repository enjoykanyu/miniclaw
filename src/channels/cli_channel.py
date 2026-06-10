"""
CLI Channel — 终端交互通道

对应 OpenClaw 的 CLI Channel 适配器：
  - 实现 ChannelPlugin Protocol
  - 提供终端交互式对话能力
  - 支持流式输出
  - 将 CLI 输入路由到 agent.run 并返回响应
"""

from __future__ import annotations

import asyncio
import sys
from typing import Optional

from loguru import logger

from channel.channel_plugin import (
    ChannelPlugin,
    ChannelMeta,
    ChannelCapabilities,
    BundledChannelEntry,
)


class CliChannel:
    """CLI 通道适配器

    实现 ChannelPlugin Protocol，提供终端交互式对话。
    支持 DM 和流式输出，不支持群组、@提及等。
    """

    id: str = "cli"
    meta: ChannelMeta = ChannelMeta(
        name="CLI Channel",
        description="Terminal-based channel",
        icon="💻",
        order=10,
    )
    capabilities: ChannelCapabilities = ChannelCapabilities(
        dm=True,
        groups=False,
        mentions=False,
        streaming=True,
    )

    def __init__(self) -> None:
        self._running: bool = False
        self._input_queue: asyncio.Queue[str] = asyncio.Queue()

    async def start(self, account_id: str) -> None:
        """启动 CLI 交互会话"""
        self._running = True
        logger.info(f"CLI channel started for account: {account_id}")

    async def stop(self, account_id: str) -> None:
        """停止 CLI 通道"""
        self._running = False
        logger.info(f"CLI channel stopped for account: {account_id}")

    async def send(self, account_id: str, target: str, text: str) -> None:
        """输出消息到终端

        Args:
            account_id: 账号 ID
            target: 目标（CLI 中忽略）
            text: 要输出的文本
        """
        if not self._running:
            return
        # 流式输出到终端
        print(text, flush=True)

    async def read_input(self) -> Optional[str]:
        """从终端读取一行输入（非阻塞）"""
        try:
            line = await asyncio.wait_for(self._input_queue.get(), timeout=0.1)
            return line.strip() if line else None
        except asyncio.TimeoutError:
            return None

    def submit_input(self, text: str) -> None:
        """提交输入到队列（供外部调用）"""
        self._input_queue.put_nowait(text)

    @property
    def is_running(self) -> bool:
        return self._running


def create_cli_channel_entry() -> BundledChannelEntry:
    """创建 CLI 通道的捆绑入口"""
    return BundledChannelEntry(
        id="cli",
        name="CLI Channel",
        description="Terminal-based channel",
        _plugin_loader=lambda: CliChannel(),
    )
