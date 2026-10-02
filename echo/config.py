"""Process-level configuration read from the environment (never from the DB)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .hoard_link.appconfig import env_flag, env_int, env_str
from .hoard_link.guard import parse_allowed_hosts

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PORT = 5188
DEFAULT_RETENTION_DAYS = 30
DEFAULT_MAX_CLIPS = 5000
DEFAULT_MAX_IMAGE_MB = 200
DEFAULT_EXCLUDE_APPS = "KeePass,1Password,Bitwarden,keepassxc"


def _exclude_raw() -> str:
    """The exclusion list; set to an empty value it means "exclude nothing" (blank is not "unset" here)."""
    raw = os.environ.get("ECHO_EXCLUDE_APPS")
    return DEFAULT_EXCLUDE_APPS if raw is None else raw.strip()


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
    ocr_enabled: bool = False
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
        raw_dir = env_str("ECHO_DATA_DIR")
        port = env_int("ECHO_PORT", "PORT", default=DEFAULT_PORT)
        if not 1 <= port <= 65535:
            port = DEFAULT_PORT
        return cls(
            data_dir=Path(raw_dir).expanduser() if raw_dir else REPO_ROOT / "data",
            port=port,
            port_strict=env_flag("PORT_STRICT"),
            backend=env_str("ECHO_BACKEND", default="auto"),
            autostart=env_flag("ECHO_AUTOSTART", True),
            retention_days=env_int("ECHO_RETENTION_DAYS", default=DEFAULT_RETENTION_DAYS),
            max_clips=env_int("ECHO_MAX_CLIPS", default=DEFAULT_MAX_CLIPS),
            max_image_mb=env_int("ECHO_MAX_IMAGE_MB", default=DEFAULT_MAX_IMAGE_MB),
            ocr_enabled=env_flag("ECHO_OCR_ENABLED"),
            exclude_apps=parse_exclude_apps(_exclude_raw()),
            allowed_hosts=parse_allowed_hosts(env_str("ECHO_ALLOWED_HOSTS")),
            data_dir_configured=bool(raw_dir),
        )
