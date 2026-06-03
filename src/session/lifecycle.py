import time
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from session.types import (
    SessionEntry,
    SessionScope,
    SessionType,
    SessionResetMode,
    SessionResetPolicy,
    SessionFreshness,
    SessionInitResult,
    DEFAULT_RESET_TRIGGERS,
    DEFAULT_RESET_AT_HOUR,
)
from session.key import resolve_session_key, normalize_agent_id
from session.store import SessionStore, resolve_default_store_path


def _detect_session_type(
    is_group: bool = False,
    is_thread: bool = False,
    is_cron: bool = False,
    is_subagent: bool = False,
) -> SessionType:
    if is_subagent:
        return SessionType.SUBAGENT
    if is_cron:
        return SessionType.CRON
    if is_thread:
        return SessionType.THREAD
    if is_group:
        return SessionType.GROUP
    return SessionType.DIRECT


def _resolve_reset_policy(
    session_type: SessionType,
    reset_mode: Optional[str] = None,
    at_hour: int = DEFAULT_RESET_AT_HOUR,
    idle_minutes: int = 0,
) -> SessionResetPolicy:
    mode = SessionResetMode(reset_mode) if reset_mode else SessionResetMode.DAILY
    if session_type == SessionType.GROUP:
        if idle_minutes == 0:
            idle_minutes = 240
    elif session_type == SessionType.DIRECT:
        if idle_minutes == 0:
            idle_minutes = 1440
    return SessionResetPolicy(
        mode=mode,
        at_hour=at_hour,
        idle_minutes=idle_minutes,
        configured=reset_mode is not None,
    )


def _evaluate_session_freshness(
    entry: SessionEntry,
    policy: SessionResetPolicy,
) -> SessionFreshness:
    now = time.time()
    if policy.mode == SessionResetMode.DAILY:
        today_reset = datetime.now().replace(
            hour=policy.at_hour, minute=0, second=0, microsecond=0
        )
        if datetime.now() < today_reset:
            today_reset -= timedelta(days=1)
        reset_ts = today_reset.timestamp()
        fresh = entry.session_started_at >= reset_ts
        return SessionFreshness(
            fresh=fresh,
            daily_reset_at=policy.at_hour,
        )
    elif policy.mode == SessionResetMode.IDLE:
        if policy.idle_minutes <= 0:
            return SessionFreshness(fresh=True)
        idle_threshold = policy.idle_minutes * 60
        fresh = (now - entry.last_interaction_at) < idle_threshold
        return SessionFreshness(
            fresh=fresh,
            idle_expires_at=entry.last_interaction_at + idle_threshold if not fresh else None,
        )
    return SessionFreshness(fresh=True)


def _check_reset_trigger(body: str) -> bool:
    normalized = body.strip().lower()
    for trigger in DEFAULT_RESET_TRIGGERS:
        if normalized == trigger:
            return True
    return False


def _create_new_entry(session_key: str) -> SessionEntry:
    now = time.time()
    return SessionEntry(
        session_id=str(uuid.uuid4()),
        updated_at=now,
        session_started_at=now,
        last_interaction_at=now,
    )


def init_session_state(
    workspace_dir: str,
    agent_id: str = "default",
    main_key: str = "main",
    peer_id: str = "",
    scope: SessionScope = SessionScope.PER_SENDER,
    is_group: bool = False,
    is_thread: bool = False,
    is_cron: bool = False,
    is_subagent: bool = False,
    body: str = "",
    reset_mode: Optional[str] = None,
    reset_at_hour: int = DEFAULT_RESET_AT_HOUR,
    idle_minutes: int = 0,
    explicit_session_key: Optional[str] = None,
) -> SessionInitResult:
    aid = normalize_agent_id(agent_id)
    session_key = resolve_session_key(
        scope=scope,
        agent_id=aid,
        main_key=main_key,
        peer_id=peer_id,
        explicit_key=explicit_session_key,
    )

    store_path = resolve_default_store_path(workspace_dir, aid)
    store = SessionStore(store_path)
    store_data = store.load(skip_cache=True)

    session_type = _detect_session_type(is_group, is_thread, is_cron, is_subagent)
    reset_policy = _resolve_reset_policy(session_type, reset_mode, reset_at_hour, idle_minutes)

    reset_triggered = _check_reset_trigger(body) if body else False
    existing_entry = store_data.get(session_key)

    previous_entry = None
    is_new_session = False

    if existing_entry is None:
        entry = _create_new_entry(session_key)
        is_new_session = True
    elif reset_triggered:
        previous_entry = existing_entry
        entry = _create_new_entry(session_key)
        if previous_entry.thinking_level:
            entry.thinking_level = previous_entry.thinking_level
        if previous_entry.verbose_level:
            entry.verbose_level = previous_entry.verbose_level
        if previous_entry.model_override:
            entry.model_override = previous_entry.model_override
        is_new_session = True
    else:
        freshness = _evaluate_session_freshness(existing_entry, reset_policy)
        if not freshness.fresh:
            previous_entry = existing_entry
            entry = _create_new_entry(session_key)
            is_new_session = True
        else:
            entry = existing_entry
            entry.last_interaction_at = time.time()
            entry.updated_at = time.time()

    store_data[session_key] = entry
    store.save(store_data)

    return SessionInitResult(
        session_entry=entry,
        previous_session_entry=previous_entry,
        session_key=session_key,
        session_id=entry.session_id,
        is_new_session=is_new_session,
        reset_triggered=reset_triggered,
        store_path=store_path,
        session_scope=scope,
        session_type=session_type,
        is_group=is_group,
    )
