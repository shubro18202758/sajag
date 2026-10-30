"""The oracle's OSINT surfaces (contract C-T) — mounted by ``coordination.py`` when it imports.

    POST /api/v1/osint/signals                          machine ingest (osint-ingress, loopback)
    GET  /api/v1/osint/events?bbox=&class=&min_credibility=&state=&since=&limit=
                                                        surfaced situations + held COUNTS
    GET  /api/v1/osint/events/{osint_event_id}          one situation's dossier
    POST /api/v1/osint/events/{osint_event_id}/promote  HUMAN-GATED promotion (named officer)
    GET  /api/v1/osint/gazetteer/resolve?q=             free text → place candidates (read-only)

Places and situations, never persons: no route reads or returns a person, author, handle, face or
plate field; every situation carries its honest verification state and credibility, and a held one is
never listed or opened (404) — it exists only as a count.  The path templates are the ones OS-1 froze
for the coordination stubs.  The database comes through ``request.app.state.pool`` (503 "database pool
unavailable" without one; 503 "osint store not migrated (021)" before migration 021).  The pipeline
and the resolver are imported lazily (503 when they are not deployed), so this router imports with
``osint_common`` alone.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from osint_common import ethics, kinds
from traffic_oracle.city.common import (
    EPOCH,
    VERIFICATION_STATES,
    as_uuid,
    clean_text,
    finite,
    iso_z,
    osint_store_present,
    parse_bbox,
    utc,
)
from traffic_oracle.city.entities import load_dss
from traffic_oracle.city.feed import FeedScope, collect_feed
from traffic_oracle.osint import ingest, promote, store

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["osint"])

__all__ = ["RESOLVE_HOOK", "RESOLVER_NOT_DEPLOYED", "router"]

#: The 503 detail of the gazetteer resolve when ``osint_geo`` is not deployed.
RESOLVER_NOT_DEPLOYED = "osint geo resolver not deployed"

#: The candidate fields the resolve route returns (C-T): a place, never anything else.
_CANDIDATE_KEYS = (
    "gaz_id", "canonical_name", "feature_type", "lon", "lat", "segment_id", "junction_id",
    "confidence", "method",
)

#: A test / tooling hook replacing ``osint_geo.resolver.resolve_text``.
RESOLVE_HOOK: Callable[..., list[dict]] | None = None


def _pool(request: Request) -> Any:
    pool = getattr(request.app.state, "pool", None)
    if pool is None:
        raise HTTPException(status_code=503, detail="database pool unavailable")
    return pool


async def _require_store(conn: Any) -> None:
    if not await osint_store_present(conn):
        raise HTTPException(status_code=503, detail="osint store not migrated (021)")


def _now() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# POST /api/v1/osint/signals
# ---------------------------------------------------------------------------


@router.post("/api/v1/osint/signals")
async def post_signals(
    body: ingest.IngestRequest,
    request: Request,
    pipeline: Annotated[ingest.Pipeline, Depends(ingest.get_pipeline)],
) -> dict:
    """Accept a batch of redacted signals (C-T): screen, store, re-fuse server-side."""
    pool = _pool(request)
    await store.ensure_gazetteer(pool)
    async with pool.acquire() as conn:
        await _require_store(conn)
        return await ingest.ingest_signals(
            conn,
            pipeline,
            body.signals,
            run_id=body.run_id,
            valkey=getattr(request.app.state, "adaptive_valkey", None),
        )


# ---------------------------------------------------------------------------
# GET /api/v1/osint/events
# ---------------------------------------------------------------------------


@router.get("/api/v1/osint/events")
async def list_osint_events(
    request: Request,
    bbox: str | None = Query(default=None, max_length=128, description="minLon,minLat,maxLon,maxLat"),
    event_class: str | None = Query(default=None, alias="class", max_length=32),
    min_credibility: float | None = Query(default=None, ge=0.0, le=1.0),
    state: str | None = Query(default=None, max_length=32, description="a verification state"),
    since: Annotated[
        datetime | None,
        Query(
            description=(
                "touched (re-fused) or reported since; omitted: every surfaced situation, "
                "highest credibility first — pollers pass since"
            )
        ),
    ] = None,
    limit: int = Query(default=100, ge=1, le=200),
) -> dict:
    """Surfaced situations (OsintEventRow[]) and the held ones as counts only (C-T).

    Ordered by credibility, then recency (like the city snapshot).  Without ``since`` the list is
    NOT windowed: it is the ``limit`` most credible surfaced situations of all time, so an old
    official alert ranks above today's news report — a poller passes ``since`` (its last
    ``as_of``), and the city picture (``/city/entities``) is the 24-hour view.  ``held`` counts
    honour ``since`` the same way."""
    try:
        box = parse_bbox(bbox)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if event_class is not None and event_class not in kinds.EVENT_CLASS_NAMES:
        raise HTTPException(status_code=422, detail=f"class must be one of {list(kinds.EVENT_CLASS_NAMES)}")
    if state is not None and state not in VERIFICATION_STATES:
        raise HTTPException(status_code=422, detail=f"state must be one of {list(VERIFICATION_STATES)}")
    if min_credibility is not None and finite(min_credibility) is None:
        raise HTTPException(status_code=422, detail="min_credibility must be a finite number")
    now = _now()
    since_dt = utc(since) if since is not None else None
    pool = _pool(request)
    async with pool.acquire() as conn:
        await _require_store(conn)
        events = await store.list_events(
            conn,
            now=now,
            bbox=box,
            event_class=event_class,
            min_credibility=min_credibility,
            state=state,
            since=since_dt,
            limit=limit,
        )
        held = await store.held_counts(conn, since=since_dt)
    return {"as_of": iso_z(now), "events": events, "held": held}


# ---------------------------------------------------------------------------
# GET /api/v1/osint/events/{osint_event_id}
# ---------------------------------------------------------------------------


@router.get("/api/v1/osint/events/{osint_event_id}")
async def osint_event_dossier(
    osint_event_id: str,
    request: Request,
    audit_limit: int = Query(default=50, ge=1, le=200),
) -> dict:
    """One SURFACED situation: the row, its sources (publisher; a news/social link withheld), its
    geocodes and its audit (FeedItems).  404 when unknown, held or superseded.

    A district-level member attached to a point situation is CONTEXT, never corroboration
    (orchestrator decision; ``SourceRole`` 'context', migration 023): ``sources`` lists the
    reports the situation stands on, and ``context_sources`` — beside it, with ``context_notes``
    ("District warning in effect") — the area alerts in effect there.  Neither the credibility,
    the verification state nor the provenance counts them."""
    oid = as_uuid(osint_event_id.strip())
    if oid is None:
        raise HTTPException(status_code=422, detail="invalid osint_event uuid")
    now = _now()
    pool = _pool(request)
    async with pool.acquire() as conn:
        await _require_store(conn)
        row = await store.get_row(conn, str(oid))
        if row is None or not row["is_event"] or row["superseded_by"] is not None:
            raise HTTPException(status_code=404, detail=f"osint_event {oid} not found")
        urn = f"osint_event:{oid}"
        event = store.event_row(row, dss=(await load_dss(conn, [urn], now)).get(urn))
        if event is None:  # not a surfaced situation after all (unlocated, single social...)
            raise HTTPException(status_code=404, detail=f"osint_event {oid} not found")
        refs = await store.get_sources(conn, str(oid))
        reporting = [r for r in refs if r.role != store.CONTEXT_ROLE]
        context = [r for r in refs if r.role == store.CONTEXT_ROLE]
        geocodes = [g.model_dump(mode="json") for g in await store.get_geocodes(conn, str(oid))]
        promoted = event.get("promoted_event_id")
        audit, _ = await collect_feed(
            conn,
            since=EPOCH,
            limit=audit_limit,
            scope=FeedScope(osint_event_ids=[str(oid)], event_ids=[promoted] if promoted else []),
            valkey=getattr(request.app.state, "adaptive_valkey", None),
        )
        provenance = store.provenance_of(row)
    return {
        "event": event,
        # exactly SourceRef[] (C-T): a typed consumer validates them as they are — the reports the
        # situation stands on (primary, corroborating); never a context member
        "sources": [r.model_dump(mode="json") for r in reporting],
        "geocodes": geocodes,
        "audit": audit,
        # additive (C-Q): what the situation stands on
        "provenance": provenance,
        # additive: per source, in the same order — its tier and, for a news or social source,
        # the honest note that its link is withheld (its URL may name a person)
        "source_notes": store.source_notes(reporting),
        # additive: the area alerts in effect at the situation (role 'context'), listed apart —
        # context, never corroboration — each with its note ("District warning in effect")
        "context_sources": [r.model_dump(mode="json") for r in context],
        "context_notes": store.context_notes(context),
    }


# ---------------------------------------------------------------------------
# POST /api/v1/osint/events/{osint_event_id}/promote
# ---------------------------------------------------------------------------


@router.post("/api/v1/osint/events/{osint_event_id}/promote", status_code=201)
async def promote_osint_event(
    osint_event_id: str,
    request: Request,
    body: promote.PromoteRequest | None = None,
) -> Any:
    """HUMAN-GATED: a named officer promotes a surfaced situation to a corridor event (C-T)."""
    req = body or promote.PromoteRequest()
    try:
        return await promote.promote_osint_event(
            request,
            osint_event_id,
            officer=req.officer,
            note=req.note,
            event_kind=req.event_kind,
        )
    except promote.PromoteRefused as exc:
        return exc.response()


# ---------------------------------------------------------------------------
# GET /api/v1/osint/gazetteer/resolve
# ---------------------------------------------------------------------------


def _resolve_text() -> Callable[..., list[dict]]:
    if RESOLVE_HOOK is not None:
        return RESOLVE_HOOK
    try:
        from osint_geo import resolver as geo_resolver  # noqa: PLC0415 — lazy by design (X20)
    except ImportError as exc:
        raise HTTPException(status_code=503, detail=RESOLVER_NOT_DEPLOYED) from exc
    fn = getattr(geo_resolver, "resolve_text", None)
    if fn is None:
        try:
            import osint_geo  # noqa: PLC0415

            fn = getattr(osint_geo, "resolve_text", None)
        except ImportError:  # pragma: no cover — imported just above
            fn = None
    if fn is None:
        raise HTTPException(status_code=503, detail=RESOLVER_NOT_DEPLOYED)
    return fn


def _candidate(raw: Any) -> dict | None:
    if not isinstance(raw, dict):
        return None
    try:
        ethics.assert_no_person_keys(raw)
    except ValueError:
        return None
    return {k: raw.get(k) for k in _CANDIDATE_KEYS}


@router.get("/api/v1/osint/gazetteer/resolve")
async def resolve_gazetteer(
    q: str = Query(min_length=1, max_length=200, description="free text naming a place"),
    limit: int = Query(default=5, ge=1, le=20),
) -> Any:
    """Free text → ranked place candidates (C-T), through the offline resolver. Read-only."""
    try:
        text = clean_text(q, field_name="q")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    resolve_text = _resolve_text()
    try:
        raw = await asyncio.to_thread(resolve_text, text, limit=limit)
    except Exception as exc:  # noqa: BLE001 — the resolver never takes the oracle down
        logger.warning("osint.resolve_failed", error_type=type(exc).__name__)
        return JSONResponse(status_code=503, content={"detail": RESOLVER_NOT_DEPLOYED})
    candidates = [c for c in (_candidate(x) for x in (raw or [])) if c is not None][:limit]
    return {"q": text, "candidates": candidates}
