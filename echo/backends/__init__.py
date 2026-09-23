"""Backend selection by platform and configuration. Never crashes on import."""

from __future__ import annotations

import sys

from .base import ClipboardBackend, ClipboardContent
from .fake import FakeBackend

__all__ = ["ClipboardBackend", "ClipboardContent", "FakeBackend", "select_backend"]


def select_backend(name: str = "auto") -> tuple[ClipboardBackend, list[str]]:
    """`auto` picks Windows on win32 and the generic (pyperclip) backend
    elsewhere; `windows`/`generic`/`fake` force one. Falls back to the fake
    backend, with a note, rather than ever raising out of app startup."""
    notes: list[str] = []
    name = (name or "auto").strip().lower()
    if name == "fake":
        return FakeBackend(), notes
    if name == "windows" or (name == "auto" and sys.platform == "win32"):
        try:
            from .windows import WindowsBackend

            return WindowsBackend(), notes
        except Exception as error:
            notes.append(f"windows backend unavailable: {error}")
            if name == "windows":
                raise
    try:
        from .generic import GenericBackend

        return GenericBackend(), notes
    except Exception as error:
        notes.append(f"generic backend unavailable: {error}")
        return FakeBackend(), notes
