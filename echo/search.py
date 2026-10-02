"""FTS5 search over clips: text, label, tags, source_title. Diacritics-
insensitive, prefix match on every term, filterable by kind/pinned/time/app.

A sensitive clip's `text` column only ever holds a placeholder (see store.py),
so a search can never surface real hidden content.
"""

from __future__ import annotations

import json

from .db import Database
from .hoard_link.docs.textsearch import fts_query


def match_ladder(q: str) -> list[str]:
    """MATCH expressions to try in order until one returns rows: every word as a prefix, AND'ed (what Echo always did,
    now with each word quoted so `AND`, `NEAR`, `-` or `"` in a copied text are plain words), then any of the words."""
    ladder: list[str] = []
    for mode in ("prefix", "or"):
        expr = fts_query(q, mode=mode)
        if expr and expr not in ladder:
            ladder.append(expr)
    return ladder


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
        filters: list = []
        if kind is not None:
            sql += " AND c.kind = ?"
            filters.append(kind)
        if pinned is not None:
            sql += " AND c.pinned = ?"
            filters.append(1 if pinned else 0)
        if since is not None:
            sql += " AND c.last_seen_at >= ?"
            filters.append(since)
        if until is not None:
            sql += " AND c.last_seen_at <= ?"
            filters.append(until)
        if source_app:
            sql += " AND c.source_app = ?"
            filters.append(source_app)
        sql += " ORDER BY rank LIMIT ?"
        filters.append(limit)
        rows: list = []
        with self.db.lock:
            for expression in match_ladder(q):
                try:
                    rows = self.db.conn.execute(sql, [expression, *filters]).fetchall()
                except Exception:
                    rows = []
                if rows:
                    break
        out = []
        for row in rows:
            out.append({
                "id": row["id"], "kind": row["kind"], "preview": row["preview"], "snippet": row["snippet"],
                "chars": row["chars"], "source_app": row["source_app"], "source_title": row["source_title"],
                "last_seen_at": row["last_seen_at"], "times": row["times"], "pinned": bool(row["pinned"]),
                "label": row["label"], "tags": json.loads(row["tags"] or "[]"), "sensitive": bool(row["sensitive"]),
            })
        return out
