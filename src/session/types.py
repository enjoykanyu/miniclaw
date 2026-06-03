from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, List


DEFAULT_AGENT_ID = "default"
DEFAULT_RESET_TRIGGER = "/new"
DEFAULT_RESET_TRIGGERS = ["/new", "/reset"]
DEFAULT_IDLE_MINUTES = 0
DEFAULT_RESET_AT_HOUR = 4


class SessionScope(str, Enum):
    PER_SENDER = "per-sender"
    GLOBAL = "global"


class SessionResetMode(str, Enum):
    DAILY = "daily"
    IDLE = "idle"


class SessionType(str, Enum):
    DIRECT = "direct"
    GROUP = "group"
    CHANNEL = "channel"
    CRON = "cron"
    SUBAGENT = "subagent"
    THREAD = "thread"


@dataclass
class SessionEntry:
    session_id: str = ""
    updated_at: float = 0.0
    session_started_at: float = 0.0
    last_interaction_at: float = 0.0
    thinking_level: Optional[str] = None
    verbose_level: Optional[str] = None
    model_override: Optional[str] = None
    provider_override: Optional[str] = None
    model_override_source: Optional[str] = None
    route: str = ""
    delivery_context: Dict[str, Any] = field(default_factory=dict)
    last_channel: str = ""
    last_to: str = ""
    last_account_id: str = ""
    last_thread_id: str = ""
    compaction_count: int = 0
    spawned_by: Optional[str] = None
    parent_session_key: Optional[str] = None
    spawn_depth: int = 0
    memory_flush_at: float = 0.0
    memory_flush_compaction_count: int = -1
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionResetPolicy:
    mode: SessionResetMode = SessionResetMode.DAILY
    at_hour: int = DEFAULT_RESET_AT_HOUR
    idle_minutes: int = DEFAULT_IDLE_MINUTES
    configured: bool = False


@dataclass
class SessionFreshness:
    fresh: bool = True
    daily_reset_at: Optional[int] = None
    idle_expires_at: Optional[float] = None


@dataclass
class SessionInitResult:
    session_entry: SessionEntry = field(default_factory=SessionEntry)
    previous_session_entry: Optional[SessionEntry] = None
    session_key: str = ""
    session_id: str = ""
    is_new_session: bool = False
    reset_triggered: bool = False
    store_path: str = ""
    session_scope: SessionScope = SessionScope.PER_SENDER
    session_type: SessionType = SessionType.DIRECT
    is_group: bool = False


def merge_session_entry(existing: SessionEntry, updates: Dict[str, Any]) -> SessionEntry:
    result = SessionEntry(
        session_id=updates.get("session_id", existing.session_id),
        updated_at=updates.get("updated_at", 0.0),
        session_started_at=updates.get("session_started_at", existing.session_started_at),
        last_interaction_at=updates.get("last_interaction_at", existing.last_interaction_at),
        thinking_level=updates.get("thinking_level", existing.thinking_level),
        verbose_level=updates.get("verbose_level", existing.verbose_level),
        model_override=updates.get("model_override", existing.model_override),
        provider_override=updates.get("provider_override", existing.provider_override),
        model_override_source=updates.get("model_override_source", existing.model_override_source),
        route=updates.get("route", existing.route),
        delivery_context=updates.get("delivery_context", existing.delivery_context),
        last_channel=updates.get("last_channel", existing.last_channel),
        last_to=updates.get("last_to", existing.last_to),
        last_account_id=updates.get("last_account_id", existing.last_account_id),
        last_thread_id=updates.get("last_thread_id", existing.last_thread_id),
        compaction_count=updates.get("compaction_count", existing.compaction_count),
        spawned_by=updates.get("spawned_by", existing.spawned_by),
        parent_session_key=updates.get("parent_session_key", existing.parent_session_key),
        spawn_depth=updates.get("spawn_depth", existing.spawn_depth),
        memory_flush_at=updates.get("memory_flush_at", existing.memory_flush_at),
        memory_flush_compaction_count=updates.get("memory_flush_compaction_count", existing.memory_flush_compaction_count),
        extra=updates.get("extra", existing.extra),
    )
    if result.updated_at == 0.0:
        import time
        result.updated_at = time.time()
    return result
