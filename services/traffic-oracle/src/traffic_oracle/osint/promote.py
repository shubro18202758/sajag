"""Promote a reported OSINT situation to a corridor event — HUMAN-GATED (contract C-T, plan §5.1).

``POST /api/v1/osint/events/{osint_event_id}/promote`` {officer?, note?, event_kind?} + ``x-sajag-officer``.
The AI or a rule proposes; a NAMED officer decides.  Order of checks (frozen; LG 25 and OS-6 rely on it):

1. the body's shape → 422 (FastAPI; an ``event_kind`` of ``crime_incident`` or ``vehicle_pursuit`` is a
   shape error: OSINT never emits either);
2. a named officer — the loopback-verified ``x-sajag-officer`` header, else the body ``officer`` —
   otherwise **409 officer-required, before any lookup** (even for an unknown or malformed id);
3. the situation → 404 when unknown;
4. 409 ``not-an-event`` (held or superseded) → 409 ``already-promoted`` (+ ``event_id``) → 409
   ``no-anchor`` (no ``segment_id`` and no segment entering its junction).

Then, with the situation's row locked (concurrent promotions serialise): a ``CorridorEventRequest``
(kind = the situation's ``sajag_event_kind`` or the officer's override; title = its label; ONE route
spine ``[segment_id]``; ``metadata {source: "osint", osint_event_id}``; ``source_kind`` 'osint', its
credibility and verification state KEPT as they are — never upgraded; the C-T provenance; the
representative point as ``geotag``) goes through ``events.create_event`` with
``request.state.osint_promotion`` set (the ONLY way an osint event is created — a direct POST /events
stays a 422), then the lifecycle (C-F) moves it to ``active`` with the same officer — the ledger row
names the officer — and ``promoted_event_id`` is recorded.  A live corridor event already created for
the situation but never recorded (a crash between the steps) is adopted, never duplicated.

:func:`promote_osint_event` is the callable OS-6's decision approve reuses (C-U step 1): it returns
the 201 body and raises :class:`PromoteRefused` for the 409s.  A promotion holds one pooled
connection (the row lock) while ``create_event`` and the lifecycle each take one more from the same
pool, so at most :data:`MAX_CONCURRENT_PROMOTIONS` run at once per app (the oracle process has one) —
promotions can never drain the pool and deadlock on acquire.  A caller must not hold a pooled connection of its own
while it awaits :func:`promote_osint_event`.
"""

from __future__ import annotations

import asyncio
import uuid as _uuid
from typing import Any

import structlog
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from traffic_oracle import events
from traffic_oracle.city.common import (
    SOURCE_LINK_WITHHELD,
    clean_text,
    mask_plates_in_text,
    named_actor,
    osint_provenance,
    osint_store_present,
)
from traffic_oracle.osint import store
from traffic_oracle.units.router import authenticated_officer

logger = structlog.get_logger(__name__)

__all__ = [
    "MAX_CONCURRENT_PROMOTIONS",
    "PROMOTABLE_KINDS",
    "REFUSAL_CODES",
    "PromoteRefused",
    "PromoteRequest",
    "promote_osint_event",
]

#: Promotions in flight per app: each holds a pooled connection and briefly takes a second
#: (create_event, then the lifecycle), so 3 use at most 6 of the oracle's 10 — the rest of the
#: oracle keeps connections, and no promotion waits on one another promotion holds.
MAX_CONCURRENT_PROMOTIONS = 3

#: Where the app keeps its promotion gate (``request.app.state``; one per app, so per loop).
GATE_STATE_ATTR = "osint_promotion_gate"


def _gate(request: Request) -> asyncio.Semaphore:
    """The app's promotion gate, created on first use (no await in between: never two)."""
    state = request.app.state
    gate = getattr(state, GATE_STATE_ATTR, None)
    if gate is None:
        gate = asyncio.Semaphore(MAX_CONCURRENT_PROMOTIONS)
        setattr(state, GATE_STATE_ATTR, gate)
    return gate


#: The kinds a promotion may carry: the sixteen minus the two OSINT never emits.
PROMOTABLE_KINDS: tuple[str, ...] = tuple(
    k for k in events.EVENT_KINDS if k not in ("crime_incident", "vehicle_pursuit")
)

#: The 409 codes (C-T).
REFUSAL_CODES: tuple[str, ...] = ("officer-required", "already-promoted", "no-anchor", "not-an-event")

_REASONS = {
    "officer-required": "a named duty officer promotes a reported situation (x-sajag-officer or officer)",
    "already-promoted": "this situation is already a corridor event",
    "no-anchor": "the situation has no road segment and no segment entering its junction",
    "not-an-event": "the situation is held or superseded: only a surfaced situation can be promoted",
}


class PromoteRefused(Exception):
    """A promotion the gate refuses (409): ``code`` is one of :data:`REFUSAL_CODES`."""

    def __init__(self, code: str, detail: str | None = None, *, event_id: str | None = None) -> None:
        if code not in REFUSAL_CODES:
            raise ValueError(f"unknown refusal code {code!r}")
        super().__init__(code)
        self.code = code
        self.detail = detail or _REASONS[code]
        self.event_id = event_id

    def body(self) -> dict:
        out: dict[str, Any] = {"detail": self.code, "reason": self.detail}
        if self.event_id is not None:
            out["event_id"] = self.event_id
        return out

    def response(self) -> JSONResponse:
        return JSONResponse(status_code=409, content=self.body())


class PromoteRequest(BaseModel):
    """The promote body (C-T).  ``officer`` is optional HERE because the gate checks it next (409
    officer-required, header first); a blank officer reads as none, a malformed one is a 422."""

    model_config = ConfigDict(extra="forbid")

    officer: str | None = Field(default=None, description="2..64 chars, the named duty officer")
    note: str | None = Field(default=None, max_length=500)
    event_kind: str | None = Field(
        default=None, description="override of the situation's kind (never crime_incident or vehicle_pursuit)"
    )

    @field_validator("officer", mode="before")
    @classmethod
    def _officer(cls, v: Any) -> str | None:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return named_actor(str(v))

    @field_validator("note")
    @classmethod
    def _note(cls, v: str | None) -> str | None:
        return clean_text(v, field_name="note")

    @field_validator("event_kind")
    @classmethod
    def _kind(cls, v: str | None) -> str | None:
        if v is not None and v not in PROMOTABLE_KINDS:
            raise ValueError(
                f"event_kind must be one of {list(PROMOTABLE_KINDS)} — OSINT never becomes "
                "crime_incident (ANPR/watchlist origin) or vehicle_pursuit (human-initiated)"
            )
        return v


def _body_officer(officer: str | None) -> str | None:
    try:
        return named_actor(officer) if officer and officer.strip() else None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _provenance(row: Any, primary: Any, osint_event_id: str, dss_id: str | None) -> dict:
    """The C-T provenance of the corridor event: feeds, publishers, the source URL only for an
    official primary source (a news/social link is withheld), the situation id, the geocoder."""
    prov = osint_provenance(row)
    official = primary is not None and primary["source_tier"] == store.OFFICIAL_TIER
    out = {
        "source_feeds": prov["source_feeds"][:16],
        "publishers": prov["publishers"][:16],
        "source_url": (primary["url"] if official else None),
        "osint_event_id": osint_event_id,
        "fused_event_id": str(row["fused_event_id"]),
        "geocoder": prov["geocoder"],
        "geocode_confidence": prov["geocode_confidence"],
        "dss_id": dss_id,
    }
    if primary is not None and not official:
        out["source_url_note"] = SOURCE_LINK_WITHHELD
    return out


def _geotag(row: Any) -> dict | None:
    lon, lat = row["rep_lon"], row["rep_lat"]
    box = events.GEOTAG_BBOX
    if lon is None or lat is None:
        return None
    if not (box[0] <= float(lon) <= box[2] and box[1] <= float(lat) <= box[3]):
        return None
    return {"lon": float(lon), "lat": float(lat)}


async def promote_osint_event(
    request: Request,
    osint_event_id: str,
    *,
    officer: str | None,
    note: str | None = None,
    event_kind: str | None = None,
    dss_id: str | None = None,
) -> dict:
    """Promote one surfaced situation (see the module docstring); the 201 body.

    Raises :class:`PromoteRefused` (409), ``HTTPException`` 404 (unknown id), 422 (a malformed
    officer, header or kind) or 503 (no pool, OSINT store not migrated)."""
    # (2) a NAMED officer first — before anything is looked up
    header = authenticated_officer(request)
    body_officer = _body_officer(officer)
    if header is None and body_officer is None:
        raise PromoteRefused("officer-required")
    actor, detail = events._human_actor(request, body_officer)
    if event_kind is not None and event_kind not in PROMOTABLE_KINDS:
        raise HTTPException(status_code=422, detail="event_kind is not promotable from OSINT")
    note = clean_text(note, field_name="note") if note is not None else None
    if note is not None and len(note) > 500:
        raise HTTPException(status_code=422, detail="note must be at most 500 characters")

    pool = getattr(request.app.state, "pool", None)
    if pool is None:
        raise HTTPException(status_code=503, detail="database pool unavailable")
    try:
        oid = str(_uuid.UUID(str(osint_event_id)))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=f"osint_event {osint_event_id} not found") from exc

    # at most MAX_CONCURRENT_PROMOTIONS hold a connection while taking another (no pool deadlock)
    async with _gate(request):
        async with pool.acquire() as conn:
            if not await osint_store_present(conn):
                raise HTTPException(status_code=503, detail="osint store not migrated (021)")
            async with conn.transaction():
                row = await store.lock_event_row(conn, oid)
                if row is None:
                    raise HTTPException(status_code=404, detail=f"osint_event {oid} not found")
                surfaced = (
                    row["is_event"]
                    and row["superseded_by"] is None
                    and row["rep_lon"] is not None
                    and row["sajag_event_kind"] is not None
                )
                if not surfaced:
                    raise PromoteRefused("not-an-event")
                if row["promoted_event_id"] is not None:
                    raise PromoteRefused("already-promoted", event_id=str(row["promoted_event_id"]))
                segment_id = row["segment_id"] or await store.junction_adjacent_segment(
                    conn, row["junction_id"]
                )
                if not segment_id:
                    raise PromoteRefused("no-anchor")
                kind = event_kind or row["sajag_event_kind"]
                full = await store.get_row(conn, oid)
                primary = await store.primary_source(conn, oid)
                orphan = await store.orphan_promotion(conn, oid)
                if orphan is not None:
                    event_id, status = str(orphan["event_id"]), str(orphan["status"])
                    logger.warning(
                        "osint.promote.orphan_adopted", osint_event_id=oid, event_id=event_id
                    )
                else:
                    try:
                        req = events.CorridorEventRequest(
                            event_kind=kind,
                            # OSINT text never carries an unmasked registration mark (C6)
                            title=mask_plates_in_text(str(row["label"] or kind))[:200],
                            description=mask_plates_in_text(str(row["summary"] or "")),
                            route_spines=[
                                events.RouteSpineModel(
                                    label="primary", segment_ids=[int(segment_id)]
                                )
                            ],
                            metadata={"source": "osint", "osint_event_id": oid},
                            officer=body_officer,
                            source_kind="osint",
                            credibility=round(float(row["credibility"]), 4),
                            verification_state=row["verification_state"],
                            provenance=_provenance(
                                full if full is not None else row, primary, oid, dss_id
                            ),
                            geotag=_geotag(row),
                        )
                    except ValidationError as exc:
                        raise HTTPException(
                            status_code=422,
                            detail="the situation cannot become a corridor event: "
                            f"{exc.errors()[0]['msg']}",
                        ) from exc
                    request.state.osint_promotion = True
                    try:
                        created = await events.create_event(req, request)
                    finally:
                        request.state.osint_promotion = False
                    event_id, status = str(created["event_id"]), str(created["status"])
                if status != "active":
                    transition_note = f"promoted from a reported OSINT situation ({oid})"
                    if note:
                        transition_note += f" — {note}"
                    moved = await events.transition_event(
                        event_id,
                        events.EventStatusRequest(
                            to_status="active", officer=body_officer, note=transition_note[:500]
                        ),
                        request,
                    )
                    if isinstance(moved, JSONResponse):
                        raise HTTPException(
                            status_code=409, detail="the corridor event could not be activated"
                        )
                await store.set_promoted(conn, oid, event_id)

    logger.info(
        "osint.promoted",
        osint_event_id=oid,
        event_id=event_id,
        event_kind=kind,
        actor=actor,
        actor_source=(detail or {}).get("actor_source", "body"),
        dss_id=dss_id,
    )
    return {
        "osint_event_id": oid,
        "event_id": event_id,
        "event_kind": kind,
        "status": "active",
        "verification_state": row["verification_state"],
        "source_kind": "osint",
        # additive: who promoted it
        "actor": actor,
    }
