"""Wiring of database, stores, the clipboard backend, watcher and janitor.
Owns the clock, so every timestamp in the app can be pinned in tests."""

from __future__ import annotations

import logging
import secrets
import threading
import time
from typing import Callable

from . import __version__
from .backends import select_backend
from .backends.base import ClipboardBackend
from .config import Config
from .db import Database
from .janitor import Janitor
from .search import Search
from .store import ClipStore, SettingsStore
from .watcher import Watcher

log = logging.getLogger("echo")

JANITOR_PERIOD_S = 600  # 10 minutes


def write_token(config: Config) -> str:
    config.data_dir.mkdir(parents=True, exist_ok=True)
    token = secrets.token_hex(32)
    config.token_path.write_text(token, encoding="utf-8")
    try:
        config.token_path.chmod(0o600)
    except OSError:
        pass
    return token


class Services:
    """Everything the API and the agent tools call through. `clock` is
    injectable (tests pass a fixed function) and `backend` lets tests hand in
    a `FakeBackend` instead of probing the platform.
    """

    def __init__(self, config: Config, clock: Callable[[], float] | None = None, backend: ClipboardBackend | None = None):
        self.config = config
        self.clock = clock or time.time
        self.started_at = self.clock()
        config.data_dir.mkdir(parents=True, exist_ok=True)
        config.images_dir.mkdir(parents=True, exist_ok=True)
        self.token = write_token(config)
        self.db = Database(config.db_path)
        self.settings = SettingsStore(self.db)
        self.clips = ClipStore(self.db, config.images_dir)
        self.search = Search(self.db)
        self.janitor = Janitor(self.clips, config)
        if backend is not None:
            self.backend, self.backend_notes = backend, []
        else:
            self.backend, self.backend_notes = select_backend(config.backend)
        for note in self.backend_notes:
            log.info("clipboard backend: %s", note)
        self.watcher = Watcher(self.backend, self.clips, config.exclude_apps, clock=self.clock)
        if self.settings.get_paused():
            self.watcher.pause()
        self._janitor_stop = threading.Event()
        self._janitor_thread: threading.Thread | None = None

    def now(self) -> float:
        return self.clock()

    # ---------- lifecycle ----------
    def start(self) -> None:
        if self.config.autostart:
            self.watcher.start()
        try:
            self.janitor.run(self.now())
        except Exception as error:  # pragma: no cover
            log.warning("initial housekeeping failed: %s", error)
        self._janitor_stop.clear()
        self._janitor_thread = threading.Thread(target=self._janitor_loop, name="echo-janitor", daemon=True)
        self._janitor_thread.start()

    def stop(self) -> None:
        self._janitor_stop.set()
        if self._janitor_thread:
            self._janitor_thread.join(2.0)
        self.watcher.stop()
        self.db.close()

    def _janitor_loop(self) -> None:
        while not self._janitor_stop.wait(JANITOR_PERIOD_S):
            try:
                self.janitor.run(self.now())
            except Exception as error:  # pragma: no cover
                log.warning("housekeeping failed: %s", error)

    # ---------- pause / resume ----------
    def pause(self) -> dict:
        self.settings.set_paused(True)
        self.watcher.pause()
        return self.status()

    def resume(self) -> dict:
        self.settings.set_paused(False)
        self.watcher.resume()
        return self.status()

    # ---------- clipboard actions ----------
    def set_clipboard_text(self, text: str) -> dict:
        """Put `text` on the OS clipboard and store it as a clip authored by the assistant."""
        self.backend.write(text)
        return self.clips.capture_text(text, source_app="assistant", source_title="", now=self.now())

    def copy_clip(self, clip_id: int, allow_sensitive: bool = False) -> dict:
        clip = self.clips.get(clip_id)
        if clip is None:
            raise LookupError(f"Clip {clip_id} does not exist.")
        if clip["sensitive"] and not allow_sensitive:
            raise PermissionError("This clip is hidden; it cannot be copied without allow_sensitive.")
        if clip["kind"] == "image":
            raise ValueError("Images cannot be copied back through this tool yet.")
        self.backend.write(clip["text"])
        self.clips.touch(clip_id, self.now())
        return self.clips.get(clip_id)

    # ---------- status ----------
    def status(self) -> dict:
        return {
            "service": "echo-hoard", "version": __version__, "data_dir": str(self.config.data_dir),
            "watching": self.watcher.running() and not self.watcher.paused,
            "paused": self.watcher.paused,
            "backend": self.backend.name,
            "backend_notes": self.backend_notes,
            "clips_count": self.clips.count(),
            "pinned_count": self.clips.count(pinned=True),
            "sensitive_count": self.clips.count(sensitive=True),
            "images_bytes": self.clips.images_total_bytes(),
            "last_capture_at": self.watcher.last_capture_at,
            "retention_days": self.config.retention_days,
            "max_clips": self.config.max_clips,
            "max_image_mb": self.config.max_image_mb,
            "exclude_apps": list(self.config.exclude_apps),
            "started_at": self.started_at,
            "janitor_last_run": self.janitor.last_run,
        }
