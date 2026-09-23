"""Retention, cap and 24h soft-delete purge housekeeping, run at startup and
every ten minutes by Services."""

from __future__ import annotations

import logging

from .config import Config
from .store import ClipStore

log = logging.getLogger("echo.janitor")


class Janitor:
    def __init__(self, clips: ClipStore, config: Config):
        self.clips = clips
        self.config = config
        self.last_run: float | None = None
        self.last_result: dict = {}

    def run(self, now: float) -> dict:
        result = self.clips.apply_retention(now, self.config.retention_days, self.config.max_clips, self.config.max_image_mb)
        self.last_run = now
        self.last_result = result
        total = sum(result.values())
        if total:
            log.info("janitor removed %s clips: %s", total, result)
        return result
