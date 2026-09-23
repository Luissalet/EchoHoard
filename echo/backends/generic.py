"""Cross-platform clipboard backend (Linux dev, and macOS): pyperclip, polling
text every `poll_interval` by comparing sha256 of the pasted string. No images,
no source app/window (pyperclip has no such API on any platform).
"""

from __future__ import annotations

import hashlib
import logging

from .base import ClipboardBackend, ClipboardContent

log = logging.getLogger("echo.backend.generic")


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "surrogatepass")).hexdigest()


class GenericBackend(ClipboardBackend):
    name = "generic"
    poll_interval = 0.5

    def __init__(self):
        import pyperclip

        self._pyperclip = pyperclip
        self._last_hash: str | None = None
        try:
            current = pyperclip.paste() or ""
            self._last_hash = _digest(current)  # prime so the pre-existing clipboard isn't captured as "new"
        except Exception as error:
            log.warning("could not read the initial clipboard: %s", error)

    def read(self) -> ClipboardContent | None:
        try:
            text = self._pyperclip.paste()
        except Exception as error:
            log.debug("clipboard read failed: %s", error)
            return None
        if not text:
            return None
        digest = _digest(text)
        if digest == self._last_hash:
            return None
        self._last_hash = digest
        return ClipboardContent(kind="text", text=text)

    def write(self, text: str) -> None:
        self._pyperclip.copy(text)
        self._last_hash = _digest(text)

    def foreground(self) -> tuple[str, str]:
        return "", ""
