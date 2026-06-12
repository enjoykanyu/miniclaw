"""
Hook Lifecycle — Agent 行为扩展机制

对标 OpenClaw 的 Hook 系统：
  在 Agent 生命周期的关键节点插入自定义逻辑，
  支持三种执行模式：void / modifying / claiming。

Hook 名称（对标 OpenClaw 生命周期）：
  - before_agent_run:    Agent 推理前（入口级）
  - before_agent_start:  Agent 循环开始前
  - before_prompt_build: Prompt 构建前
  - before_agent_finalize: Agent 最终化前
  - agent_end:           Agent 推理完成后
  - before_compaction:   上下文压缩前
  - after_compaction:    上下文压缩后

执行模式：
  - void:      并行执行，不修改上下文，fire-and-forget（超时 30s）
  - modifying: 按优先级顺序执行，合并结果到上下文（超时 15s）
  - claiming:  第一个返回 {handled: True} 的 handler 赢得控制权

失败策略：
  - fail-open（默认）: hook 失败不阻塞主流程
  - fail-closed:       hook 失败则中断主流程
"""

import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Protocol, runtime_checkable

from loguru import logger


# ── 默认超时 ──
DEFAULT_VOID_HOOK_TIMEOUT_S = 30
DEFAULT_MODIFYING_HOOK_TIMEOUT_S = 15


@dataclass
class HookEvent:
    """Hook 事件数据"""
    type: str                          # 事件类型（hook 名称）
    action: str                        # 动作描述
    session_key: str = ""              # 会话键
    context: Dict[str, Any] = field(default_factory=dict)  # 上下文数据


@runtime_checkable
class HookHandler(Protocol):
    """Hook 处理器协议"""
    async def __call__(self, event: HookEvent) -> Optional[Dict[str, Any]]:
        ...


@dataclass
class _HandlerEntry:
    """已注册的 handler 条目"""
    handler: Callable
    priority: int = 0
    name: str = ""


class HookRunner:
    """
    Hook 运行器 — 管理 hook 的注册和执行

    对标 OpenClaw 的 HookRunner：
    - register: 注册 handler，支持优先级
    - run_void_hook: 并行执行，fire-and-forget
    - run_modifying_hook: 顺序执行，合并结果
    - run_claiming_hook: 首个 handled=True 赢得控制权
    """

    def __init__(self):
        # event_name → list[_HandlerEntry]
        self._handlers: Dict[str, List[_HandlerEntry]] = {}
        self._fail_closed: Dict[str, bool] = {}

    def register(
        self,
        event_name: str,
        handler: Callable,
        priority: int = 0,
        name: str = "",
    ) -> None:
        """
        注册 hook handler

        Args:
            event_name: hook 名称
            handler: 异步处理函数，接收 HookEvent，返回 Optional[dict]
            priority: 优先级，数字越小越先执行（默认 0）
            name: handler 名称（用于日志）
        """
        if event_name not in self._handlers:
            self._handlers[event_name] = []

        entry = _HandlerEntry(
            handler=handler,
            priority=priority,
            name=name or getattr(handler, "__name__", "anonymous"),
        )
        self._handlers[event_name].append(entry)
        # 按优先级排序（数字越小越先执行）
        self._handlers[event_name].sort(key=lambda e: e.priority)

        logger.debug(
            f"Hook registered: {event_name} → {entry.name} (priority={priority})"
        )

    def set_fail_closed(self, event_name: str, closed: bool = True) -> None:
        """设置 hook 的失败策略：fail-closed 或 fail-open（默认）"""
        self._fail_closed[event_name] = closed

    async def run_void_hook(
        self,
        event_name: str,
        context: Dict[str, Any],
        *,
        session_key: str = "",
        timeout_s: float = DEFAULT_VOID_HOOK_TIMEOUT_S,
    ) -> None:
        """
        并行执行 void hook（fire-and-forget）

        所有 handler 并行执行，不修改上下文。
        单个 handler 超时或失败不影响其他 handler。
        """
        entries = self._handlers.get(event_name, [])
        if not entries:
            return

        event = HookEvent(
            type=event_name,
            action=f"void:{event_name}",
            session_key=session_key,
            context=context,
        )

        async def _safe_call(entry: _HandlerEntry) -> None:
            try:
                await asyncio.wait_for(
                    entry.handler(event),
                    timeout=timeout_s,
                )
            except asyncio.TimeoutError:
                logger.warning(
                    f"Hook void:{event_name} handler '{entry.name}' timed out ({timeout_s}s)"
                )
                if self._fail_closed.get(event_name, False):
                    raise
            except Exception as e:
                logger.error(
                    f"Hook void:{event_name} handler '{entry.name}' failed: {e}"
                )
                if self._fail_closed.get(event_name, False):
                    raise

        tasks = [_safe_call(entry) for entry in entries]
        await asyncio.gather(*tasks, return_exceptions=not self._fail_closed.get(event_name, False))

    async def run_modifying_hook(
        self,
        event_name: str,
        context: Dict[str, Any],
        *,
        session_key: str = "",
        timeout_s: float = DEFAULT_MODIFYING_HOOK_TIMEOUT_S,
    ) -> Dict[str, Any]:
        """
        顺序执行 modifying hook，合并结果到上下文

        handler 按优先级顺序执行，每个 handler 的返回值
        合并到 context 中，传递给下一个 handler。
        """
        entries = self._handlers.get(event_name, [])
        if not entries:
            return context

        merged = dict(context)

        event = HookEvent(
            type=event_name,
            action=f"modifying:{event_name}",
            session_key=session_key,
            context=merged,
        )

        for entry in entries:
            try:
                result = await asyncio.wait_for(
                    entry.handler(event),
                    timeout=timeout_s,
                )
                if isinstance(result, dict):
                    merged.update(result)
                    event.context = merged
            except asyncio.TimeoutError:
                logger.warning(
                    f"Hook modifying:{event_name} handler '{entry.name}' timed out ({timeout_s}s)"
                )
                if self._fail_closed.get(event_name, False):
                    raise
            except Exception as e:
                logger.error(
                    f"Hook modifying:{event_name} handler '{entry.name}' failed: {e}"
                )
                if self._fail_closed.get(event_name, False):
                    raise

        return merged

    async def run_claiming_hook(
        self,
        event_name: str,
        context: Dict[str, Any],
        *,
        session_key: str = "",
        timeout_s: float = DEFAULT_MODIFYING_HOOK_TIMEOUT_S,
    ) -> Optional[Dict[str, Any]]:
        """
        执行 claiming hook — 首个返回 {handled: True} 的 handler 赢得控制权

        handler 按优先级顺序执行，第一个返回 {"handled": True} 的
        handler 获得控制权，后续 handler 不再执行。
        """
        entries = self._handlers.get(event_name, [])
        if not entries:
            return None

        event = HookEvent(
            type=event_name,
            action=f"claiming:{event_name}",
            session_key=session_key,
            context=context,
        )

        for entry in entries:
            try:
                result = await asyncio.wait_for(
                    entry.handler(event),
                    timeout=timeout_s,
                )
                if isinstance(result, dict) and result.get("handled"):
                    logger.debug(
                        f"Hook claiming:{event_name} claimed by '{entry.name}'"
                    )
                    return result
            except asyncio.TimeoutError:
                logger.warning(
                    f"Hook claiming:{event_name} handler '{entry.name}' timed out ({timeout_s}s)"
                )
                if self._fail_closed.get(event_name, False):
                    raise
            except Exception as e:
                logger.error(
                    f"Hook claiming:{event_name} handler '{entry.name}' failed: {e}"
                )
                if self._fail_closed.get(event_name, False):
                    raise

        return None

    def get_registered_hooks(self) -> Dict[str, List[str]]:
        """获取所有已注册的 hook 及其 handler 名称"""
        return {
            name: [e.name for e in entries]
            for name, entries in self._handlers.items()
        }


# ── 全局单例 ──

hook_runner = HookRunner()
