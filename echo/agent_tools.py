"""Tools exposed to the assistant. One list drives /api/agent/* and mcp_server.py."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal

from pydantic import BaseModel, Field

from .services import Services

AGENT_INSTRUCTIONS = """Echo's Hoard is the user's own clipboard history, kept only on their PC.
It is the user's own data: quote it only when they ask for something they copied, and describe what you actually found rather than paraphrasing.
A clip flagged sensitive is never returned to you, not even partially; never ask the user to unhide one and never try to guess its content from the preview or surrounding clips.
clip_set changes what the user will paste next: always say plainly what you just put on their clipboard.
Prefer clip_search with a time window (since) over clip_recent with a huge n when the user describes roughly when they copied something.
Never read the data folder or database directly; use these tools only."""


class Empty(BaseModel):
    pass


class RecentArgs(BaseModel):
    n: int = Field(10, ge=1, le=200)
    kind: str | None = Field(None, pattern="^(text|url|email|path|code|number|image)$")


class SearchArgs(BaseModel):
    q: str = Field(..., min_length=1, max_length=500)
    kind: str | None = Field(None, pattern="^(text|url|email|path|code|number|image)$")
    since: float | None = Field(None, description="Unix epoch seconds; only clips last seen at or after this.")
    app: str | None = Field(None, max_length=200, description="Restrict to one source process name.")
    limit: int = Field(20, ge=1, le=100)


class GetArgs(BaseModel):
    id: int = Field(..., ge=1, description="Clip id, as returned by clip_recent or clip_search.")
    max_chars: int = Field(8000, ge=1, le=50_000)
    offset: int = Field(0, ge=0)


class SetArgs(BaseModel):
    text: str = Field(..., min_length=1, max_length=200_000)


class CopyArgs(BaseModel):
    id: int = Field(..., ge=1)
    allow_sensitive: bool = Field(False, description="Must be true to copy back a clip flagged sensitive; the content is still never returned to you.")


class PinArgs(BaseModel):
    id: int = Field(..., ge=1)
    pinned: bool
    label: str | None = Field(None, max_length=300)
    tags: list[str] | None = Field(None, max_length=30)


class DeleteArgs(BaseModel):
    id: int = Field(..., ge=1)


class CaptureArgs(BaseModel):
    action: Literal["pause", "resume"]


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_model: type[BaseModel]
    annotations: dict[str, bool]
    run: Callable[[Services, Any], Any]


PUBLIC_KEYS = ("id", "kind", "preview", "chars", "source_app", "last_seen_at", "times", "pinned", "label", "tags", "sensitive")


def _public(clip: dict) -> dict:
    out = {k: clip[k] for k in PUBLIC_KEYS}
    if clip["sensitive"]:
        out["preview"] = "[oculto]"
    return out


def run_recent(services: Services, args: RecentArgs) -> dict:
    clips = services.clips.list(kind=args.kind, limit=args.n)
    return {"clips": [_public(c) for c in clips], "count": len(clips)}


def run_search(services: Services, args: SearchArgs) -> dict:
    hits = services.search.search(args.q, kind=args.kind, since=args.since, source_app=args.app, limit=args.limit)
    out = []
    for hit in hits:
        item = dict(hit)
        if hit["sensitive"]:
            item["preview"] = "[oculto]"
            item["snippet"] = "[oculto]"
        out.append(item)
    return {"query": args.q, "hits": out, "count": len(out)}


def run_get(services: Services, args: GetArgs) -> dict:
    clip = services.clips.get(args.id)
    if clip is None:
        raise LookupError(f"Clip {args.id} does not exist.")
    if clip["sensitive"]:
        raise PermissionError("This clip is hidden content; it cannot be read.")
    if clip["kind"] == "image":
        return {"id": clip["id"], "kind": "image", "text": clip["text"],
                "image_width": clip["image_width"], "image_height": clip["image_height"]}
    text = clip["text"][args.offset: args.offset + args.max_chars]
    return {"id": clip["id"], "kind": clip["kind"], "text": text, "chars": clip["chars"],
            "truncated": args.offset + args.max_chars < clip["chars"],
            "source_app": clip["source_app"], "last_seen_at": clip["last_seen_at"]}


def run_set(services: Services, args: SetArgs) -> dict:
    clip = services.set_clipboard_text(args.text)
    return {"ok": True, "clip": _public(clip)}


def run_copy(services: Services, args: CopyArgs) -> dict:
    clip = services.copy_clip(args.id, allow_sensitive=args.allow_sensitive)
    return {"ok": True, "id": clip["id"], "kind": clip["kind"]}


def run_pin(services: Services, args: PinArgs) -> dict:
    if services.clips.get(args.id) is None:
        raise LookupError(f"Clip {args.id} does not exist.")
    patch: dict = {"pinned": args.pinned}
    if args.label is not None:
        patch["label"] = args.label
    if args.tags is not None:
        patch["tags"] = args.tags
    return _public(services.clips.update(args.id, patch))


def run_delete(services: Services, args: DeleteArgs) -> dict:
    if not services.clips.soft_delete(args.id, services.now()):
        raise LookupError(f"Clip {args.id} does not exist.")
    return {"ok": True, "id": args.id}


def run_status(services: Services, _: Empty) -> dict:
    s = services.status()
    keep = ("watching", "paused", "backend", "clips_count", "pinned_count", "sensitive_count", "images_bytes",
            "last_capture_at", "retention_days", "max_clips", "max_image_mb", "exclude_apps")
    return {k: s[k] for k in keep}


def run_capture(services: Services, args: CaptureArgs) -> dict:
    s = services.pause() if args.action == "pause" else services.resume()
    return {"ok": True, "watching": s["watching"], "paused": s["paused"]}


def _ann(read_only: bool, destructive: bool = False, idempotent: bool | None = None) -> dict[str, bool]:
    return {"readOnlyHint": read_only, "destructiveHint": destructive, "idempotentHint": read_only if idempotent is None else idempotent, "openWorldHint": False}


TOOLS: list[Tool] = [
    Tool("clip_recent", "The user's most recently copied clips (newest first): kind, preview, source app, when, how many times copied, pinned, label. A sensitive clip comes back with preview `[oculto]`, never the real content.\nSinónimos: portapapeles, últimas copias, qué he copiado, historial del portapapeles, lo último que copié.", RecentArgs, _ann(True), run_recent),
    Tool("clip_search", "Full-text search over the user's clipboard history (text, label, tags, source window title), diacritics-insensitive, optionally since a time and/or from one app. Sensitive clips never surface real content, only `[oculto]`.\nSinónimos: buscar en el portapapeles, qué copié de, busca la url que copié, encuentra lo que copié, hace un rato copié.", SearchArgs, _ann(True), run_search),
    Tool("clip_get", "The full text of one clip (paginated with max_chars/offset for very long clips). Refuses outright when the clip is flagged sensitive.\nSinónimos: dame el texto completo, pégame lo que copié, contenido completo de la copia.", GetArgs, _ann(True), run_get),
    Tool("clip_set", "Put text on the user's clipboard and store it as a clip (write, idempotent by content). Use when the user says 'cópiame esto' or 'ponlo en el portapapeles'; always tell them plainly what you put there.\nSinónimos: cópiame esto, ponlo en el portapapeles, copia esto, pon esto en el portapapeles, pásame esto al portapapeles.", SetArgs, _ann(False, False, True), run_set),
    Tool("clip_copy", "Put an existing clip back on the user's clipboard by id (write). Refuses a sensitive clip unless `allow_sensitive` is true, and even then never returns the content to you.\nSinónimos: pégame el anterior, vuelve a copiar esto, copia ese de nuevo, recupera esa copia, ponlo otra vez en el portapapeles.", CopyArgs, _ann(False, False, True), run_copy),
    Tool("clip_pin", "Pin or unpin a clip and optionally set its label/tags (write). Only when the user asks.\nSinónimos: fija esta copia, guarda esto, marca como favorito, etiqueta esta copia, quita de fijados.", PinArgs, _ann(False, False, True), run_pin),
    Tool("clip_delete", "Forget one clip (write, destructive; soft-deleted with a 24h undo window before it is purged for good).\nSinónimos: borra esta copia, olvida esto, elimina del portapapeles, quita esta copia.", DeleteArgs, _ann(False, True, True), run_delete),
    Tool("clip_status", "Whether Echo is watching the clipboard, counts of clips/pinned/sensitive, image storage used, retention configuration.\nSinónimos: estado del portapapeles, está vigilando, cuántas copias tengo, está en pausa.", Empty, _ann(True), run_status),
    Tool("clip_capture", "Pause or resume clipboard watching (write). Only when the user explicitly asks for it.\nSinónimos: pausa el portapapeles, deja de copiar, reanuda el portapapeles, vuelve a vigilar el portapapeles.", CaptureArgs, _ann(False, False, True), run_capture),
]

TOOLS_BY_NAME = {tool.name: tool for tool in TOOLS}


def tool_catalog() -> list[dict]:
    return [
        {"name": t.name, "description": t.description, "annotations": t.annotations, "inputSchema": t.input_model.model_json_schema(by_alias=True)}
        for t in TOOLS
    ]


def call_tool(services: Services, name: str, arguments: dict | None) -> Any:
    tool = TOOLS_BY_NAME.get(name)
    if tool is None:
        raise KeyError(f"Unknown tool: {name}")
    args = tool.input_model.model_validate(arguments or {})
    return tool.run(services, args)
