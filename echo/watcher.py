"""The clipboard watch loop: polls the backend, applies exclusions, stores clips.

Runs in its own daemon thread inside the app process and always writes
through the single-writer `ClipStore`; it never blocks the API. `poll_once()`
is the whole read-and-store cycle and is public so tests can drive it
synchronously, and so the thread-based loop and a synchronous test share the
exact same logic.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable

from .backends.base import ClipboardBackend
from .detect import is_excluded_app
from .store import ClipStore

log = logging.getLogger("echo.watcher")


class Watcher:
    def __init__(self, backend: ClipboardBackend, store: ClipStore, exclude_apps: tuple[str, ...] = (),
                 clock: Callable[[], float] | None = None, on_capture: Callable[[dict], None] | None = None):
        self.backend = backend
        self.store = store
        self.exclude_apps = exclude_apps
        self.clock = clock or time.time
        self.on_capture = on_capture
        self._paused = threading.Event()
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None
        self.last_capture_at: float | None = None
        self.last_error: str | None = None
        self.ticks = 0
        self.captured = 0
        self.skipped_excluded = 0

    # ---------- lifecycle ----------
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="echo-watcher", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread:
            self._thread.join(timeout)
        try:
            self.backend.close()
        except Exception:  # pragma: no cover - defensive
            pass

    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def pause(self) -> None:
        self._paused.set()

    def resume(self) -> None:
        self._paused.clear()
        self._wake.set()

    @property
    def paused(self) -> bool:
        return self._paused.is_set()

    def state(self) -> str:
        return "paused" if self.paused else "watching"

    # ---------- loop ----------
    def _run(self) -> None:
        interval = getattr(self.backend, "poll_interval", 0.3)
        while not self._stop.is_set():
            if self.paused:
                self._wake.wait(interval)
                self._wake.clear()
                continue
            self.ticks += 1
            try:
                self.poll_once()
                self.last_error = None
            except Exception as error:  # never kill the loop
                if str(error) != self.last_error:  # log once per distinct failure, not every tick
                    log.warning("clipboard read failed: %s", error)
                self.last_error = str(error)
            self._wake.wait(interval)
            self._wake.clear()

    def poll_once(self) -> dict | None:
        """One read-and-store cycle. Returns the resulting clip, or None when
        there was nothing new, the content was empty, or the app is excluded."""
        content = self.backend.read()
        if content is None:
            return None
        app, title = self.backend.foreground()
        if is_excluded_app(app, self.exclude_apps):
            self.skipped_excluded += 1
            return None
        now = self.clock()
        if content.kind == "image":
            if not content.image_png:
                return None
            clip = self.store.capture_image(
                content.image_png, width=content.width or 0, height=content.height or 0,
                source_app=app, source_title=title, now=now,
            )
        else:
            text = content.text or ""
            if not text.strip():
                return None
            clip = self.store.capture_text(text, source_app=app, source_title=title, now=now)
        self.last_capture_at = now
        self.captured += 1
        if self.on_capture:
            try:
                self.on_capture(clip)
            except Exception:  # pragma: no cover - defensive
                pass
        return clip
