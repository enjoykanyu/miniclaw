import json
import os
import time
import tempfile
from typing import Optional, Dict, Any

from miniclaw.session.types import SessionEntry, merge_session_entry


class SessionStore:
    def __init__(self, store_path: str):
        self.store_path = store_path
        self._cache: Optional[Dict[str, Dict[str, Any]]] = None
        self._cache_mtime: float = 0.0

    def _ensure_dir(self):
        dir_path = os.path.dirname(self.store_path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)

    def load(self, skip_cache: bool = False) -> Dict[str, SessionEntry]:
        if not skip_cache and self._cache is not None:
            try:
                stat = os.stat(self.store_path)
                if stat.st_mtime == self._cache_mtime:
                    return {k: self._dict_to_entry(v) for k, v in self._cache.items()}
            except OSError:
                return {}

        if not os.path.isfile(self.store_path):
            self._cache = {}
            self._cache_mtime = 0.0
            return {}

        try:
            with open(self.store_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            data = {}

        self._cache = data
        try:
            self._cache_mtime = os.stat(self.store_path).st_mtime
        except OSError:
            self._cache_mtime = 0.0

        return {k: self._dict_to_entry(v) for k, v in data.items()}

    def save(self, store: Dict[str, SessionEntry]) -> None:
        self._ensure_dir()
        data = {k: self._entry_to_dict(v) for k, v in store.items()}
        try:
            tmp_fd, tmp_path = tempfile.mkstemp(
                dir=os.path.dirname(self.store_path),
                prefix=".sessions_",
                suffix=".tmp",
            )
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self.store_path)
        except OSError:
            try:
                with open(self.store_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            except OSError:
                pass

        self._cache = data
        try:
            self._cache_mtime = os.stat(self.store_path).st_mtime
        except OSError:
            self._cache_mtime = 0.0

    def update_entry(self, session_key: str, entry: SessionEntry) -> None:
        store = self.load()
        store[session_key] = entry
        self.save(store)

    def patch_entry(self, session_key: str, updates: Dict[str, Any]) -> Optional[SessionEntry]:
        store = self.load()
        existing = store.get(session_key)
        if existing is None:
            return None
        updated = merge_session_entry(existing, updates)
        store[session_key] = updated
        self.save(store)
        return updated

    def get_entry(self, session_key: str) -> Optional[SessionEntry]:
        store = self.load()
        return store.get(session_key)

    def remove_entry(self, session_key: str) -> None:
        store = self.load()
        if session_key in store:
            del store[session_key]
            self.save(store)

    def prune_expired(self, max_age_hours: int = 24) -> int:
        store = self.load()
        now = time.time()
        threshold = now - (max_age_hours * 3600)
        pruned = 0
        for key in list(store.keys()):
            entry = store[key]
            if entry.last_interaction_at > 0 and entry.last_interaction_at < threshold:
                if entry.session_started_at < threshold:
                    del store[key]
                    pruned += 1
        if pruned > 0:
            self.save(store)
        return pruned

    @staticmethod
    def _dict_to_entry(data: Dict[str, Any]) -> SessionEntry:
        return SessionEntry(
            session_id=data.get("sessionId", data.get("session_id", "")),
            updated_at=data.get("updatedAt", data.get("updated_at", 0.0)),
            session_started_at=data.get("sessionStartedAt", data.get("session_started_at", 0.0)),
            last_interaction_at=data.get("lastInteractionAt", data.get("last_interaction_at", 0.0)),
            thinking_level=data.get("thinkingLevel", data.get("thinking_level")),
            verbose_level=data.get("verboseLevel", data.get("verbose_level")),
            model_override=data.get("modelOverride", data.get("model_override")),
            provider_override=data.get("providerOverride", data.get("provider_override")),
            model_override_source=data.get("modelOverrideSource", data.get("model_override_source")),
            route=data.get("route", ""),
            delivery_context=data.get("deliveryContext", data.get("delivery_context", {})),
            last_channel=data.get("lastChannel", data.get("last_channel", "")),
            last_to=data.get("lastTo", data.get("last_to", "")),
            last_account_id=data.get("lastAccountId", data.get("last_account_id", "")),
            last_thread_id=data.get("lastThreadId", data.get("last_thread_id", "")),
            compaction_count=data.get("compactionCount", data.get("compaction_count", 0)),
            spawned_by=data.get("spawnedBy", data.get("spawned_by")),
            parent_session_key=data.get("parentSessionKey", data.get("parent_session_key")),
            spawn_depth=data.get("spawnDepth", data.get("spawn_depth", 0)),
            memory_flush_at=data.get("memoryFlushAt", data.get("memory_flush_at", 0.0)),
            memory_flush_compaction_count=data.get("memoryFlushCompactionCount", data.get("memory_flush_compaction_count", -1)),
            extra=data.get("extra", {}),
        )

    @staticmethod
    def _entry_to_dict(entry: SessionEntry) -> Dict[str, Any]:
        return {
            "sessionId": entry.session_id,
            "updatedAt": entry.updated_at,
            "sessionStartedAt": entry.session_started_at,
            "lastInteractionAt": entry.last_interaction_at,
            "thinkingLevel": entry.thinking_level,
            "verboseLevel": entry.verbose_level,
            "modelOverride": entry.model_override,
            "providerOverride": entry.provider_override,
            "modelOverrideSource": entry.model_override_source,
            "route": entry.route,
            "deliveryContext": entry.delivery_context,
            "lastChannel": entry.last_channel,
            "lastTo": entry.last_to,
            "lastAccountId": entry.last_account_id,
            "lastThreadId": entry.last_thread_id,
            "compactionCount": entry.compaction_count,
            "spawnedBy": entry.spawned_by,
            "parentSessionKey": entry.parent_session_key,
            "spawnDepth": entry.spawn_depth,
            "memoryFlushAt": entry.memory_flush_at,
            "memoryFlushCompactionCount": entry.memory_flush_compaction_count,
            "extra": entry.extra,
        }


def resolve_default_store_path(workspace_dir: str, agent_id: str = "default") -> str:
    sessions_dir = os.path.join(workspace_dir, ".miniclaw", "sessions")
    os.makedirs(sessions_dir, exist_ok=True)
    return os.path.join(sessions_dir, f"{agent_id}.json")
