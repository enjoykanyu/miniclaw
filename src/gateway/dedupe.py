"""
Gateway Dedupe Cache — 幂等性去重 + runId

对标 OpenClaw 的 DedupeCache：
  - TTL 过期淘汰：超过 TTL 的缓存条目自动失效
  - 最大容量裁剪：超过 max_size 时按 LRU 淘汰最旧条目
  - touch() 更新访问时间（LRU 行为：delete + set on OrderedDict）
  - 空键忽略：空字符串 key 不做任何操作
  - 全局单例：resolve_global_dedupe_cache()

映射关系：
  OpenClaw DedupeCache             → DedupeCache
  OpenClaw dedupeCache.check()     → check()
  OpenClaw dedupeCache.peek()      → peek()
  OpenClaw dedupeCache.delete()    → delete()
  OpenClaw dedupeCache.clear()     → clear()
  OpenClaw dedupeCache.size()      → size()
  OpenClaw resolveGlobalDedupeCache → resolve_global_dedupe_cache()

集成方式：
  - agent.run 处理器在执行前检查 runId 去重
  - AgentRunRequest 模型新增 run_id 字段
"""

import time
from collections import OrderedDict
from typing import Optional, Any

from loguru import logger


class DedupeCache:
    """
    幂等性去重缓存 — 对标 OpenClaw DedupeCache

    基于 OrderedDict 实现 LRU 淘汰：
    - 每次访问时 delete + set，将条目移到末尾（最新）
    - 淘汰时从头部移除（最旧）

    每个条目格式:
    {
        "value": Any,           # 缓存的值（如 agent.run 的结果）
        "created_at": float,    # 创建时间
        "accessed_at": float,   # 最后访问时间
    }
    """

    def __init__(
        self,
        ttl_seconds: float = 300.0,   # 默认 5 分钟 TTL
        max_size: int = 10000,
    ):
        self._ttl = ttl_seconds
        self._max_size = max_size
        self._store: OrderedDict[str, dict] = OrderedDict()

    def check(self, key: str, now: float, value: Any = None) -> Optional[Any]:
        """
        检查 key 是否存在且未过期

        如果 key 存在且未过期，返回缓存的值（命中）。
        如果 key 不存在或已过期，返回 None（未命中），并将 value 写入缓存。

        Args:
            key: 缓存键
            now: 当前时间戳
            value: 如果未命中，要写入的值

        Returns:
            命中时返回缓存值，未命中时返回 None
        """
        if not key:
            return None

        # 先清理过期条目
        self._evict_expired(now)

        if key in self._store:
            entry = self._store[key]
            if entry["created_at"] + self._ttl > now:
                # 命中：更新访问时间（LRU 行为）
                self._touch(key, now)
                return entry["value"]
            else:
                # 已过期，删除
                del self._store[key]

        # 未命中：写入新值
        if value is not None:
            self._set(key, value, now)

        return None

    def peek(self, key: str, now: float) -> Optional[Any]:
        """
        查看缓存值但不更新访问时间

        Args:
            key: 缓存键
            now: 当前时间戳

        Returns:
            命中时返回缓存值，未命中或已过期时返回 None
        """
        if not key:
            return None

        entry = self._store.get(key)
        if entry is None:
            return None

        if entry["created_at"] + self._ttl <= now:
            # 已过期
            del self._store[key]
            return None

        return entry["value"]

    def delete(self, key: str) -> bool:
        """
        删除缓存条目

        Args:
            key: 缓存键

        Returns:
            是否成功删除
        """
        if not key:
            return False
        if key in self._store:
            del self._store[key]
            return True
        return False

    def clear(self) -> None:
        """清空所有缓存条目"""
        self._store.clear()

    def size(self) -> int:
        """返回当前缓存条目数量"""
        return len(self._store)

    def touch(self, key: str, now: float) -> bool:
        """
        更新访问时间（LRU 行为）

        Args:
            key: 缓存键
            now: 当前时间戳

        Returns:
            key 是否存在
        """
        if not key:
            return False
        return self._touch(key, now)

    def _touch(self, key: str, now: float) -> bool:
        """内部 touch 实现：delete + set 实现 LRU"""
        if key not in self._store:
            return False
        entry = self._store.pop(key)
        entry["accessed_at"] = now
        self._store[key] = entry
        return True

    def _set(self, key: str, value: Any, now: float) -> None:
        """写入缓存条目，如果超过 max_size 则淘汰最旧条目"""
        # 如果 key 已存在，先删除（保证移到末尾）
        if key in self._store:
            del self._store[key]

        # 容量检查
        while len(self._store) >= self._max_size:
            self._store.popitem(last=False)  # 移除最旧（头部）

        self._store[key] = {
            "value": value,
            "created_at": now,
            "accessed_at": now,
        }

    def _evict_expired(self, now: float) -> None:
        """清理所有过期条目"""
        expired_keys = []
        for key, entry in self._store.items():
            if entry["created_at"] + self._ttl <= now:
                expired_keys.append(key)
            else:
                # OrderedDict 是按插入顺序排列的，
                # 一旦遇到未过期的条目，后面的也不会过期
                break
        for key in expired_keys:
            del self._store[key]


# ──────────────────────────────────────────────────────────
# 全局单例
# ──────────────────────────────────────────────────────────

_global_dedupe_cache: Optional[DedupeCache] = None


def resolve_global_dedupe_cache(
    ttl_seconds: float = 300.0,
    max_size: int = 10000,
) -> DedupeCache:
    """
    获取全局 DedupeCache 单例

    首次调用时创建，后续调用返回同一实例。
    参数仅在首次调用时生效。
    """
    global _global_dedupe_cache
    if _global_dedupe_cache is None:
        _global_dedupe_cache = DedupeCache(
            ttl_seconds=ttl_seconds,
            max_size=max_size,
        )
        logger.info(f"Global DedupeCache initialized: ttl={ttl_seconds}s, max_size={max_size}")
    return _global_dedupe_cache
