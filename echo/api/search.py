"""Full-text search over clips."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from .deps import services

router = APIRouter(prefix="/api")


@router.get("/search")
def search(
    request: Request,
    q: str = Query(..., min_length=1, max_length=500),
    kind: str | None = Query(None),
    pinned: int | None = Query(None),
    since: float | None = Query(None),
    until: float | None = Query(None),
    app: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
):
    hits = services(request).search.search(
        q, kind=kind, pinned=(bool(pinned) if pinned is not None else None), since=since, until=until,
        source_app=app, limit=limit,
    )
    return {"query": q, "hits": hits, "count": len(hits)}
