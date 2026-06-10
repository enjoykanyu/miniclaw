"""
MiniClaw 内置通道

对应 OpenClaw 的 bundled channels，提供：
  - CLI Channel: 终端交互通道
  - Webhook Channel: HTTP Webhook 通道

启动时自动注册为 bundled 通道。
"""

from channel.channel_registry import register_channel
from channels.cli_channel import CliChannel, create_cli_channel_entry
from channels.webhook_channel import WebhookChannel, create_webhook_channel_entry


def register_bundled_channels() -> None:
    """注册所有内置通道为 bundled 通道"""
    cli = CliChannel()
    register_channel(cli, bundled=True)

    webhook = WebhookChannel()
    register_channel(webhook, bundled=True)


__all__ = [
    "CliChannel",
    "WebhookChannel",
    "create_cli_channel_entry",
    "create_webhook_channel_entry",
    "register_bundled_channels",
]
