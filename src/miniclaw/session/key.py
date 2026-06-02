import re
from typing import Optional

from miniclaw.session.types import SessionScope, DEFAULT_AGENT_ID


def normalize_agent_id(agent_id: str) -> str:
    return agent_id.strip().lower() if agent_id else DEFAULT_AGENT_ID


def normalize_main_key(main_key: str) -> str:
    return main_key.strip() if main_key else "main"


def build_agent_main_session_key(
    agent_id: str = DEFAULT_AGENT_ID,
    main_key: str = "main",
) -> str:
    aid = normalize_agent_id(agent_id)
    mk = normalize_main_key(main_key)
    return f"agent:{aid}:{mk}"


def build_agent_peer_session_key(
    agent_id: str = DEFAULT_AGENT_ID,
    main_key: str = "main",
    peer_id: str = "",
    channel_id: str = "",
    account_id: str = "",
    scope: SessionScope = SessionScope.PER_SENDER,
) -> str:
    base = build_agent_main_session_key(agent_id, main_key)
    if scope == SessionScope.GLOBAL:
        return base
    if peer_id:
        return f"{base}:peer:{peer_id}"
    return base


def resolve_session_key(
    scope: SessionScope = SessionScope.PER_SENDER,
    agent_id: str = DEFAULT_AGENT_ID,
    main_key: str = "main",
    peer_id: str = "",
    explicit_key: Optional[str] = None,
) -> str:
    if explicit_key:
        return explicit_key
    if scope == SessionScope.GLOBAL:
        return build_agent_main_session_key(agent_id, main_key)
    return build_agent_peer_session_key(
        agent_id=agent_id,
        main_key=main_key,
        peer_id=peer_id,
        scope=scope,
    )


def resolve_agent_id_from_session_key(session_key: str) -> str:
    match = re.match(r"^agent:([^:]+):", session_key)
    if match:
        return match.group(1)
    return DEFAULT_AGENT_ID


def classify_session_key_shape(session_key: str) -> str:
    if not session_key:
        return "missing"
    if session_key.startswith("agent:"):
        parts = session_key.split(":")
        if len(parts) >= 3:
            return "agent"
        return "malformed_agent"
    return "legacy_or_alias"
