"""The schema migrations; the connection, lock, transactions and migrations runner are the shared `hoard_link.sqlkit`."""

from __future__ import annotations

import sqlite3

from .hoard_link import sqlkit

MIN_SQLITE = (3, 35, 0)

MIGRATIONS: list[str] = [
    # 1: clips (the clipboard history) with FTS over text/label/tags/source_title, plus settings
    """
    CREATE TABLE clips (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      kind TEXT NOT NULL DEFAULT 'text',
      text TEXT NOT NULL DEFAULT '',
      preview TEXT NOT NULL DEFAULT '',
      chars INTEGER NOT NULL DEFAULT 0,
      sha256 TEXT NOT NULL,
      source_app TEXT NOT NULL DEFAULT '',
      source_title TEXT NOT NULL DEFAULT '',
      first_seen_at REAL NOT NULL,
      last_seen_at REAL NOT NULL,
      times INTEGER NOT NULL DEFAULT 1,
      pinned INTEGER NOT NULL DEFAULT 0,
      label TEXT NOT NULL DEFAULT '',
      tags TEXT NOT NULL DEFAULT '[]',
      sensitive INTEGER NOT NULL DEFAULT 0,
      image_width INTEGER,
      image_height INTEGER,
      image_bytes INTEGER NOT NULL DEFAULT 0,
      deleted_at REAL
    );
    CREATE INDEX clips_sha ON clips(sha256);
    CREATE INDEX clips_last_seen ON clips(last_seen_at);
    CREATE INDEX clips_pinned ON clips(pinned);
    CREATE INDEX clips_deleted ON clips(deleted_at);
    CREATE VIRTUAL TABLE clips_fts USING fts5(
      text, label, tags, source_title,
      content='clips', content_rowid='id',
      tokenize = 'unicode61 remove_diacritics 2'
    );
    CREATE TRIGGER clips_ai AFTER INSERT ON clips BEGIN
      INSERT INTO clips_fts(rowid, text, label, tags, source_title) VALUES (new.id, new.text, new.label, new.tags, new.source_title);
    END;
    CREATE TRIGGER clips_ad AFTER DELETE ON clips BEGIN
      INSERT INTO clips_fts(clips_fts, rowid, text, label, tags, source_title) VALUES ('delete', old.id, old.text, old.label, old.tags, old.source_title);
    END;
    CREATE TRIGGER clips_au AFTER UPDATE ON clips BEGIN
      INSERT INTO clips_fts(clips_fts, rowid, text, label, tags, source_title) VALUES ('delete', old.id, old.text, old.label, old.tags, old.source_title);
      INSERT INTO clips_fts(rowid, text, label, tags, source_title) VALUES (new.id, new.text, new.label, new.tags, new.source_title);
    END;
    CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    """,
]


def check_sqlite() -> None:
    version = tuple(int(p) for p in sqlite3.sqlite_version.split("."))
    if version < MIN_SQLITE:
        raise RuntimeError(f"SQLite {sqlite3.sqlite_version} is too old; need {'.'.join(map(str, MIN_SQLITE))}+.")
    probe = sqlite3.connect(":memory:")
    try:
        if not sqlkit.check_fts5(probe):  # pragma: no cover - depends on the build
            raise RuntimeError("This Python's SQLite has no FTS5 support; Echo needs it.")
    finally:
        probe.close()


class Database(sqlkit.Database):
    """One connection shared by every thread behind a re-entrant lock (`hoard_link.sqlkit`); the app is the only
    writer, the MCP bridge never opens this file."""

    def __init__(self, path, **kw):
        check_sqlite()
        super().__init__(path, migrations=MIGRATIONS, **kw)
