"""Process-level configuration read from the environment (never from the DB)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .guard import parse_allowed_hosts

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PORT = 5188
DEFAULT_RETENTION_DAYS = 30
DEFAULT_MAX_CLIPS = 5000
DEFAULT_MAX_IMAGE_MB = 200
DEFAULT_EXCLUDE_APPS = "KeePass,1Password,Bitwarden,keepassxc"


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _int_env(name: str, default: int) -> int:
    raw = _env(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def parse_exclude_apps(raw: str) -> tuple[str, ...]:
    return tuple(a.strip() for a in raw.split(",") if a.strip())


@dataclass
class Config:
    """Everything the process needs before the database exists."""

    data_dir: Path = field(default_factory=lambda: REPO_ROOT / "data")
    port: int = DEFAULT_PORT
    port_strict: bool = False
    backend: str = "auto"  # auto | windows | generic | fake
    autostart: bool = True  # start the watcher thread with the app
    retention_days: int = DEFAULT_RETENTION_DAYS
    max_clips: int = DEFAULT_MAX_CLIPS
    max_image_mb: int = DEFAULT_MAX_IMAGE_MB
    exclude_apps: tuple[str, ...] = ()
    allowed_hosts: tuple[str, ...] = ()  # extra Host values (exact or *.suffix) besides localhost
    data_dir_configured: bool = False

    @property
    def db_path(self) -> Path:
        return self.data_dir / "echo-hoard.db"

    @property
    def images_dir(self) -> Path:
        return self.data_dir / "images"

    @property
    def token_path(self) -> Path:
        return self.data_dir / "mcp-token"

    @classmethod
    def from_env(cls) -> "Config":
        raw_dir = _env("ECHO_DATA_DIR")
        port_raw = _env("ECHO_PORT") or _env("PORT") or str(DEFAULT_PORT)
        try:
            port = int(port_raw)
        except ValueError:
            port = DEFAULT_PORT
        if not 1 <= port <= 65535:
            port = DEFAULT_PORT
        return cls(
            data_dir=Path(raw_dir).expanduser() if raw_dir else REPO_ROOT / "data",
            port=port,
            port_strict=_env("PORT_STRICT") == "1",
            backend=_env("ECHO_BACKEND", "auto") or "auto",
            autostart=_env("ECHO_AUTOSTART", "1") != "0",
            retention_days=_int_env("ECHO_RETENTION_DAYS", DEFAULT_RETENTION_DAYS),
            max_clips=_int_env("ECHO_MAX_CLIPS", DEFAULT_MAX_CLIPS),
            max_image_mb=_int_env("ECHO_MAX_IMAGE_MB", DEFAULT_MAX_IMAGE_MB),
            exclude_apps=parse_exclude_apps(_env("ECHO_EXCLUDE_APPS", DEFAULT_EXCLUDE_APPS)),
            allowed_hosts=parse_allowed_hosts(_env("ECHO_ALLOWED_HOSTS")),
            data_dir_configured=bool(raw_dir),
        )
