"""Persistence for clips (capture, dedupe, filters, soft delete) and the tiny
paused/resumed setting. Dedupe is on sha256: capturing the same content again
bumps `last_seen_at`/`times` instead of inserting a new row.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .db import Database
from .detect import detect_kind, detect_sensitive

PREVIEW_LEN = 200


def make_preview(text: str) -> str:
    single_line = " ".join((text or "").split())
    return single_line[:PREVIEW_LEN]


def clean_tags(tags: list[str] | None) -> list[str]:
    if not tags:
        return []
    seen: list[str] = []
    for tag in tags:
        t = str(tag).strip().lower()
        if t and t not in seen:
            seen.append(t)
    return seen


def clip_to_dict(row) -> dict:
    return {
        "id": row["id"], "kind": row["kind"], "text": row["text"], "preview": row["preview"],
        "chars": row["chars"], "sha256": row["sha256"], "source_app": row["source_app"],
        "source_title": row["source_title"], "first_seen_at": row["first_seen_at"],
        "last_seen_at": row["last_seen_at"], "times": row["times"], "pinned": bool(row["pinned"]),
        "label": row["label"], "tags": json.loads(row["tags"] or "[]"), "sensitive": bool(row["sensitive"]),
        "image_width": row["image_width"], "image_height": row["image_height"],
        "image_bytes": row["image_bytes"], "deleted_at": row["deleted_at"],
    }


class ClipStore:
    def __init__(self, db: Database, images_dir: Path):
        self.db = db
        self.images_dir = images_dir

    # ---------- reads ----------
    def get(self, clip_id: int, include_deleted: bool = False) -> dict | None:
        sql = "SELECT * FROM clips WHERE id = ?"
        if not include_deleted:
            sql += " AND deleted_at IS NULL"
        with self.db.lock:
            row = self.db.conn.execute(sql, (clip_id,)).fetchone()
        return clip_to_dict(row) if row else None

    def list(self, *, kind: str | None = None, pinned: bool | None = None, since: float | None = None,
              until: float | None = None, source_app: str | None = None, include_deleted: bool = False,
              limit: int = 50, offset: int = 0) -> list[dict]:
        sql = "SELECT * FROM clips WHERE 1=1"
        params: list = []
        if not include_deleted:
            sql += " AND deleted_at IS NULL"
        if kind is not None:
            sql += " AND kind = ?"
            params.append(kind)
        if pinned is not None:
            sql += " AND pinned = ?"
            params.append(1 if pinned else 0)
        if since is not None:
            sql += " AND last_seen_at >= ?"
            params.append(since)
        if until is not None:
            sql += " AND last_seen_at <= ?"
            params.append(until)
        if source_app:
            sql += " AND source_app = ?"
            params.append(source_app)
        sql += " ORDER BY last_seen_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        with self.db.lock:
            rows = self.db.conn.execute(sql, params).fetchall()
        return [clip_to_dict(r) for r in rows]

    def count(self, *, pinned: bool | None = None, sensitive: bool | None = None, include_deleted: bool = False) -> int:
        sql = "SELECT COUNT(*) FROM clips WHERE 1=1"
        params: list = []
        if not include_deleted:
            sql += " AND deleted_at IS NULL"
        if pinned is not None:
            sql += " AND pinned = ?"
            params.append(1 if pinned else 0)
        if sensitive is not None:
            sql += " AND sensitive = ?"
            params.append(1 if sensitive else 0)
        with self.db.lock:
            return self.db.conn.execute(sql, params).fetchone()[0]

    def images_total_bytes(self) -> int:
        with self.db.lock:
            row = self.db.conn.execute("SELECT COALESCE(SUM(image_bytes), 0) AS total FROM clips WHERE deleted_at IS NULL").fetchone()
        return int(row["total"])

    # ---------- capture (watcher / assistant) ----------
    def capture_text(self, text: str, *, source_app: str, source_title: str, now: float) -> dict:
        """Insert or bump a text clip. Detects kind and sensitivity; a sensitive
        clip's real content is replaced by a placeholder BEFORE it ever reaches SQLite."""
        text = text if text is not None else ""
        sha = hashlib.sha256(text.encode("utf-8", "surrogatepass")).hexdigest()
        with self.db.transaction() as conn:
            existing = conn.execute(
                "SELECT id FROM clips WHERE sha256 = ? AND kind != 'image' AND deleted_at IS NULL", (sha,)
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE clips SET last_seen_at = ?, times = times + 1, source_app = ?, source_title = ? WHERE id = ?",
                    (now, source_app, source_title, existing["id"]),
                )
                new_id = existing["id"]
            else:
                sensitive_label = detect_sensitive(text, source_title)
                sensitive = sensitive_label is not None
                stored_text = f"[oculto: {sensitive_label}]" if sensitive else text
                kind = detect_kind(text)
                preview = make_preview(stored_text)
                cursor = conn.execute(
                    """INSERT INTO clips(kind, text, preview, chars, sha256, source_app, source_title, first_seen_at,
                       last_seen_at, times, sensitive) VALUES (?,?,?,?,?,?,?,?,?,1,?)""",
                    (kind, stored_text, preview, len(text), sha, source_app, source_title, now, now, int(sensitive)),
                )
                new_id = cursor.lastrowid
        return self.get(new_id)

    def capture_image(self, png_bytes: bytes, *, width: int, height: int, source_app: str, source_title: str,
                       now: float) -> dict:
        sha = hashlib.sha256(png_bytes).hexdigest()
        with self.db.transaction() as conn:
            existing = conn.execute(
                "SELECT id FROM clips WHERE sha256 = ? AND kind = 'image' AND deleted_at IS NULL", (sha,)
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE clips SET last_seen_at = ?, times = times + 1, source_app = ?, source_title = ? WHERE id = ?",
                    (now, source_app, source_title, existing["id"]),
                )
                return self.get(existing["id"])
            placeholder = f"[imagen {width}×{height}]"
            cursor = conn.execute(
                """INSERT INTO clips(kind, text, preview, chars, sha256, source_app, source_title, first_seen_at,
                   last_seen_at, times, image_width, image_height, image_bytes)
                   VALUES ('image', ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)""",
                (placeholder, placeholder, len(placeholder), sha, source_app, source_title, now, now, width, height,
                 len(png_bytes)),
            )
            new_id = cursor.lastrowid
        self.images_dir.mkdir(parents=True, exist_ok=True)
        (self.images_dir / f"{new_id}.png").write_bytes(png_bytes)
        return self.get(new_id)

    def image_path(self, clip_id: int) -> Path | None:
        clip = self.get(clip_id, include_deleted=True)
        if not clip or clip["kind"] != "image":
            return None
        path = self.images_dir / f"{clip_id}.png"
        return path if path.exists() else None

    def touch(self, clip_id: int, now: float) -> None:
        with self.db.transaction() as conn:
            conn.execute("UPDATE clips SET last_seen_at = ? WHERE id = ?", (now, clip_id))

    # ---------- writes ----------
    def update(self, clip_id: int, patch: dict) -> dict | None:
        allowed = {"label", "tags", "pinned"}
        fields = {k: v for k, v in patch.items() if k in allowed and v is not None}
        if "tags" in fields:
            fields["tags"] = json.dumps(clean_tags(fields["tags"]))
        if "pinned" in fields:
            fields["pinned"] = int(bool(fields["pinned"]))
        if not fields:
            return self.get(clip_id)
        sets = ", ".join(f"{k} = ?" for k in fields)
        with self.db.transaction() as conn:
            conn.execute(f"UPDATE clips SET {sets} WHERE id = ?", (*fields.values(), clip_id))
        return self.get(clip_id)

    def soft_delete(self, clip_id: int, now: float) -> bool:
        with self.db.transaction() as conn:
            return conn.execute("UPDATE clips SET deleted_at = ? WHERE id = ? AND deleted_at IS NULL", (now, clip_id)).rowcount > 0

    def restore(self, clip_id: int) -> bool:
        with self.db.transaction() as conn:
            return conn.execute("UPDATE clips SET deleted_at = NULL WHERE id = ? AND deleted_at IS NOT NULL", (clip_id,)).rowcount > 0

    def purge_deleted_older_than(self, cutoff: float) -> int:
        with self.db.lock:
            rows = self.db.conn.execute("SELECT id FROM clips WHERE deleted_at IS NOT NULL AND deleted_at < ?", (cutoff,)).fetchall()
        return self._hard_delete([r["id"] for r in rows])

    def purge_before(self, cutoff: float) -> int:
        """Bulk, irreversible purge: every non-pinned clip last seen before `cutoff`."""
        with self.db.lock:
            rows = self.db.conn.execute("SELECT id FROM clips WHERE pinned = 0 AND last_seen_at < ?", (cutoff,)).fetchall()
        return self._hard_delete([r["id"] for r in rows])

    def _hard_delete(self, ids: list[int]) -> int:
        if not ids:
            return 0
        with self.db.transaction() as conn:
            marks = ",".join("?" * len(ids))
            conn.execute(f"DELETE FROM clips WHERE id IN ({marks})", ids)
        for clip_id in ids:
            try:
                (self.images_dir / f"{clip_id}.png").unlink()
            except FileNotFoundError:
                pass
        return len(ids)

    def apply_retention(self, now: float, retention_days: int, max_clips: int, max_image_mb: int) -> dict:
        """Age out unpinned clips past `retention_days`, cap total unpinned clips at
        `max_clips` (oldest first), cap total image bytes at `max_image_mb` (oldest
        images first), and purge soft-deleted clips past the 24h undo window."""
        deleted_age = deleted_cap = deleted_images = 0
        if retention_days > 0:
            cutoff = now - retention_days * 86400
            with self.db.lock:
                rows = self.db.conn.execute(
                    "SELECT id FROM clips WHERE pinned = 0 AND last_seen_at < ? AND deleted_at IS NULL", (cutoff,)
                ).fetchall()
            deleted_age = self._hard_delete([r["id"] for r in rows])
        with self.db.lock:
            total = self.db.conn.execute("SELECT COUNT(*) FROM clips WHERE pinned = 0 AND deleted_at IS NULL").fetchone()[0]
        if total > max_clips:
            excess = total - max_clips
            with self.db.lock:
                rows = self.db.conn.execute(
                    "SELECT id FROM clips WHERE pinned = 0 AND deleted_at IS NULL ORDER BY last_seen_at ASC LIMIT ?", (excess,)
                ).fetchall()
            deleted_cap = self._hard_delete([r["id"] for r in rows])
        cap_bytes = max_image_mb * 1024 * 1024
        total_bytes = self.images_total_bytes()
        if total_bytes > cap_bytes:
            excess_bytes = total_bytes - cap_bytes
            with self.db.lock:
                rows = self.db.conn.execute(
                    "SELECT id, image_bytes FROM clips WHERE kind = 'image' AND pinned = 0 AND deleted_at IS NULL ORDER BY last_seen_at ASC"
                ).fetchall()
            ids, freed = [], 0
            for row in rows:
                if freed >= excess_bytes:
                    break
                ids.append(row["id"])
                freed += row["image_bytes"]
            deleted_images = self._hard_delete(ids)
        deleted_purge = self.purge_deleted_older_than(now - 86400)
        return {"deleted_age": deleted_age, "deleted_cap": deleted_cap, "deleted_images": deleted_images,
                "deleted_purge": deleted_purge}


class SettingsStore:
    """Just the one persisted switch: whether capture is paused."""

    def __init__(self, db: Database):
        self.db = db

    def get_paused(self) -> bool:
        with self.db.lock:
            row = self.db.conn.execute("SELECT value FROM settings WHERE key = 'paused'").fetchone()
        return bool(row and row["value"] == "1")

    def set_paused(self, paused: bool) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO settings(key, value) VALUES ('paused', ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                ("1" if paused else "0",),
            )
