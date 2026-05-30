from typing import Protocol, Optional, Callable, runtime_checkable
from dataclasses import dataclass, field

@dataclass
class ChannelMeta:
    name: str
    description: str = ""
    icon: str = "📡"
    order: int = 999

@dataclass
class ChannelCapabilities:
    dm: bool = True
    groups: bool = False
    mentions: bool = False
    streaming: bool = False
    threading: bool = False
    pairing: bool = False

@runtime_checkable
class ChannelPlugin(Protocol):
    """对应 OpenClaw ChannelPlugin 类型

    Python 用 Protocol（结构化子类型）替代
    TypeScript 的 type alias。
    @runtime_checkable 允许 isinstance() 检查。
    """
    id: str
    meta: ChannelMeta
    capabilities: ChannelCapabilities

    async def start(self, account_id: str) -> None: ...
    async def stop(self, account_id: str) -> None: ...
    async def send(self, account_id: str,
                   target: str, text: str) -> None: ...

class RegistrationMode:
    FULL = "full"
    DISCOVERY = "discovery"
    CLI_METADATA = "cli-metadata"

@dataclass
class BundledChannelEntry:
    """对应 defineBundledChannelEntry 返回的
    BundledChannelEntryContract

    封装懒加载 + 注册模式分支逻辑。
    """
    id: str
    name: str
    description: str = ""
    _plugin: Optional[ChannelPlugin] = field(
        default=None, repr=False)
    _plugin_loader: Optional[Callable] = field(
        default=None, repr=False)

    def load_plugin(self) -> ChannelPlugin:
        if self._plugin is None:
            if self._plugin_loader is None:
                raise RuntimeError(
                    f"No loader for {self.id}")
            self._plugin = self._plugin_loader()
        return self._plugin

    def register(self, mode: str = "full") -> None:
        if mode == RegistrationMode.CLI_METADATA:
            return
        plugin = self.load_plugin()
        # TODO 未实现 register_channel
        # register_channel(plugin)
        if mode == RegistrationMode.DISCOVERY:
            return
        if mode != RegistrationMode.FULL:
            return