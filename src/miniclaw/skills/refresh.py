import os
import time
from typing import Optional, Callable, List, Set

from miniclaw.skills.types import SkillEntry
from miniclaw.skills.workspace import load_skill_entries


_skills_version = 0
_listeners: Set[Callable] = set()


def get_skills_snapshot_version() -> int:
    return _skills_version


def bump_skills_snapshot_version() -> int:
    global _skills_version
    now = int(time.time())
    _skills_version = now if now > _skills_version else _skills_version + 1
    for listener in _listeners:
        try:
            listener(_skills_version)
        except Exception:
            pass
    return _skills_version


def add_skills_change_listener(listener: Callable):
    _listeners.add(listener)


def remove_skills_change_listener(listener: Callable):
    _listeners.discard(listener)


def should_refresh_snapshot(cached_version: Optional[int] = None) -> bool:
    if cached_version is None:
        return _skills_version > 0
    return cached_version < _skills_version


class SkillsWatcher:
    def __init__(
        self,
        workspace_dir: str,
        config_dir: Optional[str] = None,
        debounce_ms: int = 250,
    ):
        self.workspace_dir = workspace_dir
        self.config_dir = config_dir
        self.debounce_ms = debounce_ms
        self._observer = None
        self._watched_dirs: Set[str] = set()

    def _resolve_watch_paths(self) -> List[str]:
        paths = []
        home_dir = os.path.expanduser("~")
        cfg_dir = self.config_dir or os.path.join(home_dir, ".miniclaw")

        workspace_skills = os.path.join(self.workspace_dir, "skills")
        workspace_agents_skills = os.path.join(self.workspace_dir, ".agents", "skills")
        managed_skills = os.path.join(cfg_dir, "skills")
        personal_skills = os.path.join(home_dir, ".agents", "skills")

        for p in [workspace_skills, workspace_agents_skills, managed_skills, personal_skills]:
            if os.path.isdir(p):
                paths.append(p)

        return paths

    def start(self):
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler
        except ImportError:
            return

        class SkillFileHandler(FileSystemEventHandler):
            def __init__(self, watcher: SkillsWatcher):
                self.watcher = watcher
                self._timer = None

            def on_any_event(self, event):
                if event.is_directory:
                    return
                src_path = event.src_path
                if not src_path.endswith("SKILL.md"):
                    return
                bump_skills_snapshot_version()

        paths = self._resolve_watch_paths()
        if not paths:
            return

        self._observer = Observer()
        handler = SkillFileHandler(self)
        for p in paths:
            self._observer.schedule(handler, p, recursive=True)
            self._watched_dirs.add(p)

        self._observer.daemon = True
        self._observer.start()

    def stop(self):
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None
            self._watched_dirs.clear()
