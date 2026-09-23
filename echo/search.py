"""FTS5 search over clips: text, label, tags, source_title. Diacritics-
insensitive, prefix match on every term, filterable by kind/pinned/time/app.

A sensitive clip's `text` column only ever holds a placeholder (see store.py),
so a search can never surface real hidden content.
"""

from __future__ import annotations

import json
import re

from .db import Database

TOKEN_RE = re.compile(r"[\w]+", re.UNICODE)


def _fts_query(q: str) -> str:
    """Turn free text into an FTS5 MATCH expression: every term is a prefix match, AND'ed."""
    terms = TOKEN_RE.findall(q)
    if not terms:
        return '""'
    return " AND ".join(f"{t}*" for t in terms)


class Search:
    def __init__(self, db: Database):
        self.db = db

    def search(self, q: str, *, kind: str | None = None, pinned: bool | None = None, since: float | None = None,
               until: float | None = None, source_app: str | None = None, limit: int = 20) -> list[dict]:
        q = (q or "").strip()
        if not q:
            return []
        sql = """
            SELECT c.*, snippet(clips_fts, 0, '<mark>', '</mark>', '…', 10) AS snippet, bm25(clips_fts) AS rank
            FROM clips_fts JOIN clips c ON c.id = clips_fts.rowid
            WHERE clips_fts MATCH ? AND c.deleted_at IS NULL
        """
        params: list = [_fts_query(q)]
        if kind is not None:
            sql += " AND c.kind = ?"
            params.append(kind)
        if pinned is not None:
            sql += " AND c.pinned = ?"
            params.append(1 if pinned else 0)
        if since is not None:
            sql += " AND c.last_seen_at >= ?"
            params.append(since)
        if until is not None:
            sql += " AND c.last_seen_at <= ?"
            params.append(until)
        if source_app:
            sql += " AND c.source_app = ?"
            params.append(source_app)
        sql += " ORDER BY rank LIMIT ?"
        params.append(limit)
        with self.db.lock:
            try:
                rows = self.db.conn.execute(sql, params).fetchall()
            except Exception:
                return []
        out = []
        for row in rows:
            out.append({
                "id": row["id"], "kind": row["kind"], "preview": row["preview"], "snippet": row["snippet"],
                "chars": row["chars"], "source_app": row["source_app"], "source_title": row["source_title"],
                "last_seen_at": row["last_seen_at"], "times": row["times"], "pinned": bool(row["pinned"]),
                "label": row["label"], "tags": json.loads(row["tags"] or "[]"), "sensitive": bool(row["sensitive"]),
            })
        return out
