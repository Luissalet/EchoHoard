"""Clips: recent/filtered list, add (+ set clipboard), get, patch, soft delete,
restore, copy back to the clipboard, image bytes, and the bulk irreversible purge."""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .deps import services

router = APIRouter(prefix="/api/clips")

KIND_PATTERN = "^(text|url|email|path|code|number|image)$"


class ClipCreate(BaseModel):
    text: str = Field(..., min_length=1, max_length=200_000)


class ClipPatch(BaseModel):
    label: str | None = Field(None, max_length=300)
    tags: list[str] | None = Field(None, max_length=30)
    pinned: bool | None = None


@router.get("")
def list_clips(
    request: Request,
    kind: str | None = Query(None, pattern=KIND_PATTERN),
    pinned: int | None = Query(None),
    since: float | None = Query(None),
    until: float | None = Query(None),
    app: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    svc = services(request)
    clips = svc.clips.list(
        kind=kind, pinned=(bool(pinned) if pinned is not None else None), since=since, until=until,
        source_app=app, limit=limit, offset=offset,
    )
    return {"clips": clips, "count": len(clips)}


@router.post("", status_code=201)
def add_clip(request: Request, body: ClipCreate):
    """What the assistant (and the UI) use to put text on the clipboard: sets
    the OS clipboard and records the clip in the same call."""
    return services(request).set_clipboard_text(body.text)


@router.delete("")
def bulk_purge(request: Request, before: str = Query(..., description="ISO datetime; unpinned clips last seen before this are purged.")):
    try:
        cutoff = dt.datetime.fromisoformat(before).timestamp()
    except ValueError as error:
        raise HTTPException(400, "Invalid `before` datetime.") from error
    deleted = services(request).clips.purge_before(cutoff)
    return {"ok": True, "deleted": deleted}


@router.get("/{clip_id}")
def get_clip(request: Request, clip_id: int):
    clip = services(request).clips.get(clip_id)
    if clip is None:
        raise HTTPException(404, "Clip not found.")
    return clip


@router.patch("/{clip_id}")
def patch_clip(request: Request, clip_id: int, body: ClipPatch):
    svc = services(request)
    if svc.clips.get(clip_id) is None:
        raise HTTPException(404, "Clip not found.")
    return svc.clips.update(clip_id, body.model_dump(exclude_unset=True))


@router.delete("/{clip_id}")
def delete_clip(request: Request, clip_id: int):
    svc = services(request)
    if not svc.clips.soft_delete(clip_id, svc.now()):
        raise HTTPException(404, "Clip not found.")
    return {"ok": True}


@router.post("/{clip_id}/restore")
def restore_clip(request: Request, clip_id: int):
    if not services(request).clips.restore(clip_id):
        raise HTTPException(404, "Clip not found or not deleted.")
    return {"ok": True}


@router.post("/{clip_id}/copy")
def copy_clip(request: Request, clip_id: int):
    svc = services(request)
    try:
        return svc.copy_clip(clip_id)
    except LookupError as error:
        raise HTTPException(404, str(error)) from error
    except PermissionError as error:
        raise HTTPException(403, str(error)) from error
    except ValueError as error:
        raise HTTPException(400, str(error)) from error


@router.get("/{clip_id}/image")
def clip_image(request: Request, clip_id: int):
    path = services(request).clips.image_path(clip_id)
    if path is None:
        raise HTTPException(404, "Image not found.")
    return FileResponse(path, media_type="image/png")
