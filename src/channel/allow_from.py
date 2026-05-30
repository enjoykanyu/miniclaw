from __future__ import annotations
from enum import Enum
from dataclasses import dataclass

class Admission(str, Enum):
    DISPATCH = "dispatch"
    DROP = "drop"
    SKIP = "skip"
    OBSERVE = "observe"
    PAIRING_REQUIRED = "pairing-required"

@dataclass
class IngressDecision:
    admission: Admission
    reason: str = ""

ACCESS_GROUP_PREFIX = "accessGroup:"

def parse_access_group_entry(entry: str) -> str | None:
    trimmed = entry.strip()
    if not trimmed.startswith(ACCESS_GROUP_PREFIX):
        return None
    name = trimmed[len(ACCESS_GROUP_PREFIX):].strip()
    return name if name else None

def merge_dm_allow_from(
        allow_from: list[str] | None = None,
        store_allow_from: list[str] | None = None,
        dm_policy: str = "allowlist",
) -> list[str]:
    store = [] if dm_policy in ("allowlist", "open")         else (store_allow_from or [])
    merged = list(allow_from or []) + list(store)
    return [e.strip() for e in merged if e.strip()]

def is_sender_allowed(
        entries: list[str],
        sender_id: str | None,
        allow_when_empty: bool = True,
) -> bool:
    if not entries:
        return allow_when_empty
    if "*" in entries:
        return True
    if not sender_id:
        return False
    return sender_id in entries

def decide_channel_ingress(
        *,
        route_blocked: bool = False,
        sender_allowed: bool = True,
        sender_needs_pairing: bool = False,
        has_command: bool = False,
        command_allowed: bool = True,
        auth_mode: str = "inbound",
        is_mentioned: bool = True,
) -> IngressDecision:
    """对应 decideChannelIngress: 5层门控"""
    if route_blocked:
        return IngressDecision(Admission.DROP, "route-blocked")
    if not sender_allowed:
        return IngressDecision(Admission.DROP, "sender-denied")
    if sender_needs_pairing:
        return IngressDecision(
            Admission.PAIRING_REQUIRED, "sender-pairing")
    if has_command and not command_allowed:
        return IngressDecision(Admission.DROP, "command-denied")
    if auth_mode == "none":
        return IngressDecision(Admission.OBSERVE, "auth-none")
    if auth_mode == "route-only":
        return IngressDecision(Admission.SKIP, "route-only")
    if not is_mentioned:
        return IngressDecision(Admission.SKIP, "not-mentioned")
    return IngressDecision(Admission.DISPATCH)