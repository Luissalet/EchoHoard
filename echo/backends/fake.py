"""Deterministic backend for tests: a queue of contents the test pushes, and a
recorded foreground (process, title) pair the test can change between pushes.
Never touches the real clipboard.
"""

from __future__ import annotations

from collections import deque

from .base import ClipboardBackend, ClipboardContent


class FakeBackend(ClipboardBackend):
    name = "fake"
    poll_interval = 0.01

    def __init__(self):
        self._queue: deque[ClipboardContent] = deque()
        self._foreground = ("notas", "Notas sin título")
        self.written: list[str] = []

    def push_text(self, text: str, app: str | None = None, title: str | None = None) -> None:
        if app is not None or title is not None:
            self.set_foreground(app if app is not None else self._foreground[0], title if title is not None else self._foreground[1])
        self._queue.append(ClipboardContent(kind="text", text=text))

    def push_image(self, png_bytes: bytes, width: int, height: int) -> None:
        self._queue.append(ClipboardContent(kind="image", image_png=png_bytes, width=width, height=height))

    def set_foreground(self, app: str, title: str) -> None:
        self._foreground = (app, title)

    def read(self) -> ClipboardContent | None:
        if not self._queue:
            return None
        return self._queue.popleft()

    def write(self, text: str) -> None:
        self.written.append(text)

    def foreground(self) -> tuple[str, str]:
        return self._foreground
