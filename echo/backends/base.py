"""Clipboard capture backend interface, shared by every platform implementation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ClipboardContent:
    """What one clipboard read produced: text, or a PNG image with its pixel size."""

    kind: str  # "text" | "image"
    text: str | None = None
    image_png: bytes | None = None
    width: int | None = None
    height: int | None = None


class ClipboardBackend:
    name = "base"
    poll_interval = 0.3  # seconds between watcher reads; each backend tunes this

    def read(self) -> ClipboardContent | None:  # pragma: no cover - interface
        """The current clipboard content, or None when it has not changed since
        the last call (backends decide this cheaply, e.g. a change counter)."""
        raise NotImplementedError

    def write(self, text: str) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def foreground(self) -> tuple[str, str]:
        """(process_name, window_title) at the moment of the last read; ("", "") when unknown."""
        return "", ""

    def close(self) -> None:
        return None
