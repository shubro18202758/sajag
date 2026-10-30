"""Decision-support store — every read and write of the 022 ``decision`` schema, the subject framing reads and the
dispatch REQUESTS an approval creates (contract C-U).

Writes, and only these (a test pins them with a recording connection):

* ``decision.decision_support`` — a new proposal (``proposed``), the previous proposal's ``superseded`` /
  ``superseded_by``, the lazy ``expired`` (written by the GET and the decision, never by the snapshot), and an
  officer's ``approved`` / ``rejected`` / ``deferred`` with ``decided_by``, ``decided_at``, ``chosen_coa_id``,
  ``decision_note``;
* ``decision.coa`` and ``decision.coa_sim_runs`` — one row per COA, one per COA and wargame method;
* ``decision.dss_decision_log`` — append-only by convention: one row per officer decision, in the decision's
  own transaction;
* ``corridor.dispatches`` — one dispatch REQUEST (status ``requested``) per dispatch action of an approved COA,
  through :data:`DSS_DISPATCH_INSERT`, a byte-identical copy of the units module's function-local
  ``dispatch_insert`` literal (``units/router.py`` ``create_dispatch``; ``tests/test_dss_store_pins.py`` fails
  if the two ever differ), with its audit row through the units module's own ``_audit`` (imported, never a new
  SQL).  Each request is then decided on its own by a duty officer (``POST /dispatches/{id}/decision``).

The promotion of an OSINT report (``osint.promote.promote_osint_event``) writes through the events module.

The event row a dispatch request attaches to is checked exactly as ``create_dispatch`` does, with its own
``_SQL_EVENT_CHECK`` (``FOR SHARE``), imported.  Generation is serialised per subject by a transaction-level
advisory lock, and the partial unique index of 022 guarantees one proposed DSS per subject.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from fastapi import HTTPException
from pydantic import ValidationError

from osint_common.types import DecisionSupport, effective_dss_state
from traffic_oracle.city.common import (
    as_list,
    finite,
    mark_demo_fir,
    mask_plates_in_text,
    routes_supersede_supported,
    verification_state_of,
)
from traffic_oracle.decision_support.engine import (
    Frame,
    _injuries,
    area_reason,
    context_notes,
    drop_anchor,
    member_sources,
    redact_text,
)
from traffic_oracle.osint import store as osint_store
from traffic_oracle.units.router import (
    _SQL_EVENT_CHECK,
    _SQL_EVENT_SPINE_START,
    _SQL_EVENT_SPINE_START_CURRENT,
    LIVE_EVENT_STATUSES,
    _audit,
)

logger = structlog.get_logger(__name__)

__all__ = [
    "DSS_DISPATCH_INSERT",
    "IDEMPOTENCY_WINDOW",
    "Persisted",
    "Refused",
    "decide",
    "expire_if_due",
    "get_row",
    "load_coas",
    "load_frame",
    "parse_subject",
    "persist",
    "read_doc",
    "reusable",
]

#: The same subject + fingerprint within this window returns the existing proposal (200).
IDEMPOTENCY_WINDOW = timedelta(minutes=10)

#: The units module keeps its dispatch INSERT as a function-local literal (``create_dispatch``), so it cannot be
#: imported: this is a byte-identical copy, pinned to the original by ``tests/test_dss_store_pins.py``.
DSS_DISPATCH_INSERT = "INSERT INTO corridor.dispatches (event_id, agency, unit_id, waypoint_junction, status, requested_by, request_payload) VALUES ($1, $2, $3, $4, 'requested', $5, $6::jsonb) RETURNING dispatch_id, created_at"  # noqa: E501

# -- decision.* -------------------------------------------------------------------------------------------------

_SQL_LOCK_SUBJECT = "SELECT pg_advisory_xact_lock(hashtext('sajag.dss:' || $1::text))"

_SQL_PROPOSED_FOR_UPDATE = "SELECT d.dss_id, d.state, d.generated_at, d.horizon_min, d.input_fingerprint FROM decision.decision_support d WHERE d.event_urn = $1 AND d.state = 'proposed' ORDER BY d.generated_at DESC FOR UPDATE"  # noqa: E501

_SQL_REUSABLE = "SELECT d.dss_id, d.generated_at, d.horizon_min FROM decision.decision_support d WHERE d.event_urn = $1 AND d.state = 'proposed' AND d.input_fingerprint = $2 AND d.generated_at > $3::timestamptz ORDER BY d.generated_at DESC LIMIT 1"  # noqa: E501

_SQL_EXPIRE = "UPDATE decision.decision_support SET state = 'expired', updated_at = NOW() WHERE dss_id = $1::uuid AND state = 'proposed' RETURNING dss_id"  # noqa: E501

_SQL_SUPERSEDE = "UPDATE decision.decision_support SET state = 'superseded', superseded_by = $2::uuid, updated_at = NOW() WHERE dss_id = $1::uuid AND state = 'proposed' RETURNING dss_id"  # noqa: E501

_SQL_INSERT_DSS = "INSERT INTO decision.decision_support (dss_id, event_urn, state, generated_at, horizon_min, seed, input_fingerprint, situation, criteria, ahp, recommendation, provenance, scoring_note, labels, strategy_prior, requested_by) VALUES ($1::uuid, $2, 'proposed', $3::timestamptz, $4, $5, $6, $7::jsonb, $8::jsonb, $9::jsonb, $10::jsonb, $11::jsonb, $12, $13::text[], $14::jsonb, $15)"  # noqa: E501

_SQL_INSERT_COA = "INSERT INTO decision.coa (dss_id, coa_id, kind, label, actions, predicted_outcome, resource_feasibility, attributes, score, ethics) VALUES ($1::uuid, $2, $3, $4, $5::jsonb, $6::jsonb, $7::jsonb, $8::jsonb, $9::jsonb, $10::jsonb)"  # noqa: E501

_SQL_INSERT_SIM_RUN = "INSERT INTO decision.coa_sim_runs (dss_id, coa_id, sim_run_id, method, seed, metrics) VALUES ($1::uuid, $2, $3, $4, $5, $6::jsonb)"  # noqa: E501

_SQL_DSS_ROW = "SELECT d.dss_id, d.event_urn, d.state, d.generated_at, d.horizon_min, d.seed, d.input_fingerprint, d.situation, d.criteria, d.ahp, d.recommendation, d.provenance, d.scoring_note, d.labels, d.strategy_prior, d.requested_by, d.decided_by, d.decided_at, d.decision_note, d.chosen_coa_id, d.superseded_by FROM decision.decision_support d WHERE d.dss_id = $1::uuid"  # noqa: E501

_SQL_DSS_ROW_FOR_UPDATE = _SQL_DSS_ROW + " FOR UPDATE"

_SQL_COAS = "SELECT c.coa_id, c.kind, c.label, c.actions, c.predicted_outcome, c.resource_feasibility, c.attributes, c.score, c.ethics FROM decision.coa c WHERE c.dss_id = $1::uuid ORDER BY c.coa_id"  # noqa: E501

_SQL_LATEST_LOG = "SELECT l.log_id FROM decision.dss_decision_log l WHERE l.dss_id = $1::uuid ORDER BY l.at DESC, l.log_id DESC LIMIT 1"  # noqa: E501

_SQL_DECIDE = "UPDATE decision.decision_support SET state = $2, decided_by = $3, decided_at = $4::timestamptz, chosen_coa_id = $5, decision_note = $6, updated_at = NOW() WHERE dss_id = $1::uuid AND state = 'proposed' RETURNING dss_id"  # noqa: E501

_SQL_INSERT_LOG = "INSERT INTO decision.dss_decision_log (dss_id, decision, coa_id, officer, note, at, promoted_event_id, dispatch_ids, next_steps) VALUES ($1::uuid, $2, $3, $4, $5, $6::timestamptz, $7::uuid, $8::uuid[], $9::jsonb) RETURNING log_id"  # noqa: E501

# -- the subject ------------------------------------------------------------------------------------------------

_SQL_EVENT_SUBJECT = "SELECT e.event_id, e.event_kind, e.title, e.description, e.status, e.metadata, e.source_kind, e.credibility, e.verification_state, e.provenance, ST_X(e.geotag) AS geotag_lon, ST_Y(e.geotag) AS geotag_lat FROM events.corridor_events e WHERE e.event_id = $1::uuid"  # noqa: E501

_SQL_EVENT_STATUS = "SELECT e.status FROM events.corridor_events e WHERE e.event_id = $1::uuid"

_SQL_SEGMENT_POINT = "SELECT rs.road_name, ST_X(ST_PointOnSurface(rs.geom)) AS lon, ST_Y(ST_PointOnSurface(rs.geom)) AS lat FROM corridor.road_segments rs WHERE rs.segment_id = $1"  # noqa: E501

_CLOSED_EVENT_STATUSES = ("completed", "cancelled")

#: The order coa_set is published in (generation order).
_KIND_RANK = {"baseline": 0, "minimal": 1, "standard": 2, "aggressive": 3, "information": 4}


def _js(value: Any) -> Any:
    if isinstance(value, (bytes, bytearray)):
        value = value.decode()
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return None
    return value


def _utc(value: Any) -> datetime:
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _iso(value: datetime) -> str:
    return _utc(value).isoformat().replace("+00:00", "Z")


def parse_subject(event_urn: str) -> tuple[str, str] | None:
    """``("osint_event" | "event", uuid)`` for a decision-support subject URN, else None."""
    kind, _, ident = str(event_urn).strip().partition(":")
    if kind not in ("osint_event", "event"):
        return None
    try:
        return kind, str(uuid.UUID(ident))
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Framing (C-U situation): 404 unknown or held, 409 event-closed
# ---------------------------------------------------------------------------


async def _event_status(conn: Any, event_id: str) -> str | None:
    row = await conn.fetchrow(_SQL_EVENT_STATUS, event_id)
    return str(row["status"]) if row else None


async def _spine(conn: Any, event_id: str) -> list[int]:
    sql = _SQL_EVENT_SPINE_START_CURRENT if await routes_supersede_supported(conn) else _SQL_EVENT_SPINE_START
    row = await conn.fetchrow(sql, event_id)
    return [int(s) for s in (row["segment_ids"] if row else None) or []]


async def load_frame(conn: Any, kind: str, subject_id: str, *, now: datetime) -> Frame:
    """The framed subject, or HTTPException 404 (unknown, held, superseded) / 409 ``event-closed``."""
    if kind == "osint_event":
        return await _osint_frame(conn, subject_id, now=now)
    return await _event_frame(conn, subject_id)


async def _osint_frame(conn: Any, oid: str, *, now: datetime) -> Frame:
    event = await osint_store.get_event(conn, oid, now=now)
    if event is None:
        raise HTTPException(status_code=404, detail=f"osint_event {oid} not found")
    ev = event.model_dump(mode="json")
    promoted = ev.get("promoted_event_id")
    status = None
    if promoted:
        status = await _event_status(conn, promoted)
        if status in _CLOSED_EVENT_STATUSES:
            raise HTTPException(status_code=409, detail="event-closed")
    refs = await osint_store.get_sources(conn, oid)
    # every source stays in provenance.sources (a context member's role says 'context'); the feeds, the
    # publishers and the injury cue come from the situation's own members only (FIX-B-ORACLE): a district alert
    # attached to a street report is context, never corroboration
    sources = [r.model_dump(mode="json") for r in refs][:200]
    members = member_sources(sources)
    attach = ev.get("attach") or {}
    situation = {
        # redacted at ingest; registration marks masked here too (C6: OSINT text never carries one)
        "summary": mask_plates_in_text(str(ev["summary"] or ev["label"]))[:2000],
        "event_class": ev["event_class"],
        "correlated_classes": list(ev.get("correlated_classes") or []),
        "subtype": ev.get("subtype"),
        "sajag_event_kind": ev.get("sajag_event_kind"),
        "toponym": ev.get("toponym"),
        "segment_id": ev.get("segment_id"),
        "junction_id": ev.get("junction_id"),
        "rep_lonlat": [ev["rep_lon"], ev["rep_lat"]] if ev.get("rep_lon") is not None else None,
        "credibility": round(float(ev["credibility"]), 4),
        "independent_publishers": int(ev.get("independent_publishers") or 0),
        "source_tiers": list(ev.get("source_tiers") or []),
        "cross_type_corroborated": bool(ev.get("cross_type_corroborated")),
        "attach": {
            "novel": bool(attach.get("novel", True)),
            "corroborates_live_urn": attach.get("corroborates_live_urn"),
            "distance_m": attach.get("distance_m"),
        },
        "verification_state": ev["verification_state"],
        "geocode_confidence": ev.get("geocode_confidence"),
    }
    seg = ev.get("segment_id")
    # OSINT-3: a neighbourhood (or a place snapped farther than a point lies from its segment) is an AREA — its
    # nearest road is a guess, so the DSS drops the anchor: road-anchored COAs infeasible up front, no closure
    # or dispatch on that road, the wargame on a notional arterial, and the dissent says why
    area_note = None
    if seg is not None or ev.get("junction_id") is not None:
        area_note = area_reason(
            area_level=bool(ev.get("area_level")), segment_id=seg, junction_id=ev.get("junction_id"),
            geocodes=await osint_store.get_geocodes(conn, oid),
        )
    if area_note is not None:
        area_note = drop_anchor(situation, area_note)
        seg = None
    route: tuple[int, ...] = (int(seg),) if seg else ()
    if not route and situation.get("junction_id"):
        adj = await osint_store.junction_adjacent_segment(conn, situation["junction_id"])
        route = (int(adj),) if adj else ()
    live_108 = tuple(
        int(f["segment_id"]) for f in ev.get("second_order") or []
        if f.get("kind") == "ambulance_route" and f.get("segment_id")
    )
    titles = " ".join(s.get("title") or "" for s in members)
    return Frame(
        event_urn=f"osint_event:{oid}",
        subject_kind="osint_event",
        subject_id=oid,
        situation=situation,
        route_segment_ids=route,
        area_level=area_note is not None or bool(ev.get("area_level")) or not (seg or ev.get("junction_id")),
        area_note=area_note,
        injuries=_injuries(ev.get("summary"), titles),
        sources=sources,
        feeds=sorted({s["source"] for s in members}),
        publishers=sorted({s["publisher"] for s in members if s.get("publisher")}),
        context=context_notes(sources),
        event_id=promoted,
        event_status=status,
        promoted_event_id=promoted,
        live_108_segments=live_108,
        second_order=tuple(
            {k: f.get(k) for k in ("kind", "urn", "segment_id", "note")} for f in ev.get("second_order") or []
        )[:16],
        basis={
            "credibility": situation["credibility"],
            "verification_state": situation["verification_state"],
            "segment_id": seg,
            "junction_id": ev.get("junction_id"),
            "area_level": bool(ev.get("area_level")),
            "signals": sorted(s["signal_id"] for s in sources),
            "promoted_event_id": promoted,
            "second_order": sorted(f"{f.get('kind')}:{f.get('urn')}" for f in ev.get("second_order") or []),
        },
    )


@dataclass(frozen=True)
class _Origin:
    """The reported situation a corridor event was promoted from, as the DSS provenance shows it."""

    urn: str
    readable: bool
    sources: tuple[dict[str, Any], ...] = ()
    feeds: tuple[str, ...] = ()
    publishers: tuple[str, ...] = ()
    context: tuple[dict[str, Any], ...] = ()
    independent_publishers: int = 0
    source_tiers: tuple[str, ...] = ()
    cross_type_corroborated: bool = False
    correlated_classes: tuple[str, ...] = ()
    geocode_confidence: float | None = None
    titles: str = ""


def _origin_osint_id(meta: Mapping[str, Any], provenance: Any) -> str | None:
    """The situation an OSINT-sourced corridor event was promoted from: ``metadata.osint_event_id`` (promote
    writes it), else the event's provenance ``osint_event_id``."""
    from_provenance = provenance.get("osint_event_id") if isinstance(provenance, Mapping) else None
    for value in (meta.get("osint_event_id"), from_provenance):
        if value:
            try:
                return str(uuid.UUID(str(value)))
            except ValueError:
                continue
    return None


def _valid_feeds(values: Any) -> tuple[str, ...]:
    from osint_common import kinds  # noqa: PLC0415

    return tuple(sorted({str(v) for v in as_list(values) if str(v) in kinds.SOURCE_PRIORS}))[:16]


def _valid_publishers(values: Any) -> tuple[str, ...]:
    from pydantic import TypeAdapter  # noqa: PLC0415

    from osint_common.types import Publisher  # noqa: PLC0415

    check = TypeAdapter(Publisher)
    out: set[str] = set()
    for v in as_list(values):
        try:
            out.add(check.validate_python(str(v)))
        except ValidationError:
            continue
    return tuple(sorted(out))[:64]


async def _osint_origin(conn: Any, oid: str | None, provenance: Any) -> _Origin | None:
    """The originating situation of an OSINT-sourced corridor event (any state: a promoted report may since have
    been superseded — its sources are still the ones the event was promoted on).  When the situation row is gone,
    only the event's own provenance (feeds, publishers) is shown, and no corroboration count is claimed."""
    if oid is None:
        return None
    row = await osint_store.get_row(conn, oid)
    urn = f"osint_event:{oid}"
    if row is None:
        prov = provenance if isinstance(provenance, Mapping) else {}
        return _Origin(urn=urn, readable=False, feeds=_valid_feeds(prov.get("source_feeds")),
                       publishers=_valid_publishers(prov.get("publishers")))
    from traffic_oracle.city.entities import osint_event_props  # noqa: PLC0415

    props = osint_event_props(row)
    sources = [r.model_dump(mode="json") for r in await osint_store.get_sources(conn, oid)][:200]
    members = member_sources(sources)
    return _Origin(
        urn=urn,
        readable=True,
        sources=tuple(sources),
        feeds=tuple(sorted({s["source"] for s in members})),
        publishers=tuple(sorted({s["publisher"] for s in members if s.get("publisher")})),
        context=context_notes(sources),
        independent_publishers=int(props.get("independent_publishers") or 0),
        source_tiers=tuple(props.get("source_tiers") or ()),
        cross_type_corroborated=bool(props.get("cross_type_corroborated")),
        correlated_classes=tuple(props.get("correlated_classes") or ()),
        geocode_confidence=props.get("geocode_confidence"),
        titles=" ".join([str(props.get("summary") or "")] + [str(s.get("title") or "") for s in members]),
    )


def _opened_by(meta: Mapping[str, Any], source_kind: Any) -> str:
    """Who opened a live corridor event, in words (``source_kind`` and the metadata's ``source`` tag)."""
    tag = " ".join(str(x or "") for x in (source_kind, meta.get("source"), meta.get("opened_by"))).lower()
    if "brain" in tag:
        return "the brain (a movement plan it registered)"
    return "an operator"


async def _event_frame(conn: Any, event_id: str) -> Frame:
    """A corridor event as the subject.  Its label: the stored verification state when there is one (the 021
    vocabulary, CONFIRMED included); else EMULATED for an emulator event; else OFFICIAL-VERIFIED for a live event —
    the city's own record on its own channel (opened by an operator or by the brain's plan registration, never a
    third-party report: the OSINT tiers grade third-party reports), which the dissent says in so many words,
    naming who opened it and that the state was derived.  An event a named officer promoted from a reported OSINT
    situation keeps its stored state (promotion never upgrades it) and carries that report's provenance: feeds,
    publishers, sources (context members with role ``context``), independent publishers, tiers and
    cross-type corroboration."""
    row = await conn.fetchrow(_SQL_EVENT_SUBJECT, event_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"event {event_id} not found")
    status = str(row["status"])
    if status in _CLOSED_EVENT_STATUSES:
        raise HTTPException(status_code=409, detail="event-closed")
    from traffic_oracle.city.common import event_source  # noqa: PLC0415

    meta = _js(row["metadata"]) or {}
    meta = meta if isinstance(meta, dict) else {}
    source = event_source(meta, row["source_kind"])
    provenance = _js(row["provenance"])
    origin = await _osint_origin(conn, _origin_osint_id(meta, provenance), provenance) if source == "osint" else None
    route = await _spine(conn, event_id)
    seg = route[0] if route else None
    toponym = None
    rep = None
    if row["geotag_lon"] is not None and row["geotag_lat"] is not None:
        rep = [float(row["geotag_lon"]), float(row["geotag_lat"])]
    if seg is not None:
        pt = await conn.fetchrow(_SQL_SEGMENT_POINT, seg)
        if pt is not None:
            toponym = pt["road_name"]
            if rep is None and finite(pt["lon"]) is not None and finite(pt["lat"]) is not None:
                rep = [float(pt["lon"]), float(pt["lat"])]
    stored_state = verification_state_of(row["verification_state"])  # the 021 vocabulary, CONFIRMED included
    derived = stored_state is None
    if stored_state is not None:
        state = stored_state
    elif source == "emulated":
        state = "EMULATED"
    elif source == "osint":
        state = "UNVERIFIED-OSINT"  # never reached: a promotion always stores the report's state
    else:
        state = "OFFICIAL-VERIFIED"  # the city's own record (see the docstring); the dissent says it was derived
    cred = finite(row["credibility"])
    if cred is None or not 0.0 <= cred <= 1.0:
        cred = 1.0 if state == "EMULATED" else (0.5 if source == "osint" else 0.95)
    text = redact_text(mask_plates_in_text(" — ".join(x for x in (row["title"], row["description"]) if x)))
    if source == "emulated":
        text = mark_demo_fir(text)  # HON-4: an emulated event's FIR is a demo reference
    o = origin or _Origin(urn="", readable=False)
    situation = {
        "summary": (text or str(row["event_kind"]))[:2000],
        "event_class": row["event_kind"],
        "correlated_classes": list(o.correlated_classes)[:16],
        "subtype": None,
        "sajag_event_kind": row["event_kind"],
        "toponym": toponym,
        "segment_id": seg,
        "junction_id": None,
        "rep_lonlat": rep,
        "credibility": round(float(cred), 4),
        # an OSINT-promoted event: its report's corroboration (0 / [] / False for any other event)
        "independent_publishers": o.independent_publishers,
        "source_tiers": list(o.source_tiers)[:6],
        "cross_type_corroborated": o.cross_type_corroborated,
        "attach": None,
        "verification_state": state,
        # the event's location is its report's geocode
        "geocode_confidence": o.geocode_confidence,
    }
    basis: dict[str, Any] = {"status": status, "route": route, "credibility": situation["credibility"],
                             "verification_state": state, "event_kind": row["event_kind"]}
    if source == "osint":
        basis["origin"] = o.urn or None
        basis["signals"] = sorted(str(s.get("signal_id")) for s in o.sources)
    return Frame(
        event_urn=f"event:{event_id}",
        subject_kind="event",
        subject_id=event_id,
        situation=situation,
        route_segment_ids=tuple(route),
        area_level=not route,
        injuries=_injuries(row["title"], row["description"], o.titles),
        sources=list(o.sources),
        feeds=list(o.feeds),
        publishers=list(o.publishers),
        context=o.context,
        event_id=event_id,
        event_status=status,
        emulated=source == "emulated",
        basis=basis,
        origin=source,
        origin_urn=o.urn or None,
        origin_detail=o.readable,
        opened_by=_opened_by(meta, row["source_kind"]) if source == "live" else None,
        derived_state=derived and source == "live",
    )


# ---------------------------------------------------------------------------
# Generation: idempotency, supersede, persist
# ---------------------------------------------------------------------------


async def reusable(conn: Any, event_urn: str, fp: str, *, now: datetime) -> str | None:
    """The proposed DSS of the same subject and fingerprint younger than 10 minutes and not expired."""
    row = await conn.fetchrow(_SQL_REUSABLE, event_urn, fp, now - IDEMPOTENCY_WINDOW)
    if row is None:
        return None
    expires = _utc(row["generated_at"]) + timedelta(minutes=int(row["horizon_min"]))
    if now >= expires:
        return None
    return str(row["dss_id"])


@dataclass(frozen=True)
class Persisted:
    dss_id: str
    created: bool


async def persist(
    conn: Any,
    doc: Mapping[str, Any],
    *,
    fingerprint: str,
    sim_runs: Sequence[Mapping[str, Any]],
    requested_by: str,
    now: datetime,
) -> Persisted:
    """Store a new proposal (one transaction, serialised per subject): an expired predecessor reads
    ``expired``, a younger identical one is reused (no new row), any other proposed one is superseded."""
    urn = doc["event_urn"]
    new_id = doc["dss_id"]
    async with conn.transaction():
        await conn.execute(_SQL_LOCK_SUBJECT, urn)
        for prev in await conn.fetch(_SQL_PROPOSED_FOR_UPDATE, urn):
            pid = str(prev["dss_id"])
            expires = _utc(prev["generated_at"]) + timedelta(minutes=int(prev["horizon_min"]))
            if now >= expires:
                await conn.fetchrow(_SQL_EXPIRE, pid)
                continue
            if prev["input_fingerprint"] == fingerprint and _utc(prev["generated_at"]) > now - IDEMPOTENCY_WINDOW:
                return Persisted(pid, False)
            await conn.fetchrow(_SQL_SUPERSEDE, pid, new_id)
        rec = doc["recommendation"]
        await conn.execute(
            _SQL_INSERT_DSS,
            new_id,
            urn,
            _utc(doc["generated_at"]),
            int(doc["horizon_min"]),
            int(doc["seed"]),
            fingerprint,
            json.dumps(doc["situation"]),
            json.dumps(doc["criteria"]),
            json.dumps(doc["ahp"]),
            json.dumps(rec),
            json.dumps(doc["provenance"]),
            doc.get("scoring_note"),
            list(doc["labels"]),
            json.dumps(rec.get("strategy_prior")) if rec.get("strategy_prior") else None,
            requested_by,
        )
        for c in doc["coa_set"]:
            await conn.execute(
                _SQL_INSERT_COA,
                new_id,
                c["coa_id"],
                c["kind"],
                c["label"],
                json.dumps(c["actions"]),
                json.dumps(c["predicted_outcome"]),
                json.dumps(c["resource_feasibility"]),
                json.dumps(c["attributes"]),
                json.dumps(c["score"]),
                json.dumps(c["ethics"]),
            )
        for r in sim_runs:
            await conn.execute(
                _SQL_INSERT_SIM_RUN,
                new_id,
                r["coa_id"],
                r.get("sim_run_id"),
                r["method"],
                r.get("seed"),
                json.dumps(r.get("metrics") or {}),
            )
    return Persisted(new_id, True)


# ---------------------------------------------------------------------------
# Reads (lazy expiry written here, never by the snapshot)
# ---------------------------------------------------------------------------


async def get_row(conn: Any, dss_id: str, *, for_update: bool = False) -> Any | None:
    return await conn.fetchrow(_SQL_DSS_ROW_FOR_UPDATE if for_update else _SQL_DSS_ROW, dss_id)


async def expire_if_due(conn: Any, row: Any, *, now: datetime) -> str:
    """The row's state after C-U's lazy expiry, writing ``expired`` when a proposal's horizon has passed."""
    expires = _utc(row["generated_at"]) + timedelta(minutes=int(row["horizon_min"]))
    state = effective_dss_state(str(row["state"]), expires, now)
    if state == "expired" and row["state"] == "proposed":
        await conn.fetchrow(_SQL_EXPIRE, str(row["dss_id"]))
    return state


async def load_coas(conn: Any, dss_id: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for r in await conn.fetch(_SQL_COAS, dss_id):
        out.append({
            "coa_id": r["coa_id"],
            "kind": r["kind"],
            "label": r["label"],
            "actions": as_list(_js(r["actions"])),
            "predicted_outcome": _js(r["predicted_outcome"]) or {},
            "resource_feasibility": _js(r["resource_feasibility"]) or {},
            "attributes": _js(r["attributes"]) or {},
            "score": _js(r["score"]) or {},
            "ethics": _js(r["ethics"]) or {},
        })
    out.sort(key=lambda c: (_KIND_RANK.get(c["kind"], 9), c["coa_id"]))
    return out


async def read_doc(conn: Any, dss_id: str, *, now: datetime) -> dict[str, Any] | None:
    """The validated DecisionSupport document (lazy expiry applied and written), or None when unknown."""
    row = await get_row(conn, dss_id)
    if row is None:
        return None
    state = await expire_if_due(conn, row, now=now)
    coas = await load_coas(conn, dss_id)
    audit_ref = None
    if state in ("approved", "rejected", "deferred"):
        log = await conn.fetchrow(_SQL_LATEST_LOG, dss_id)
        audit_ref = f"dss_decision_log:{log['log_id']}" if log else None
    decided = state in ("approved", "rejected", "deferred")
    doc = {
        "dss_id": str(row["dss_id"]),
        "event_urn": row["event_urn"],
        "state": state,
        "generated_at": _iso(row["generated_at"]),
        "horizon_min": int(row["horizon_min"]),
        "seed": int(row["seed"]),
        "situation": _js(row["situation"]),
        "criteria": _js(row["criteria"]),
        "ahp": _js(row["ahp"]),
        "scoring_note": row["scoring_note"],
        "coa_set": coas,
        "recommendation": _js(row["recommendation"]),
        "provenance": _js(row["provenance"]),
        "human_gate": {
            "state": state,
            "required_role": "duty_officer",
            "officer": row["decided_by"] if decided else None,
            "decided_at": _iso(row["decided_at"]) if decided and row["decided_at"] else None,
            "audit_ref": audit_ref,
        },
        "labels": list(row["labels"] or []),
    }
    try:
        return DecisionSupport.model_validate(doc).model_dump(mode="json")
    except ValidationError as exc:
        logger.warning("dss.row_refused", dss_id=str(dss_id)[:64], errors=len(exc.errors()))
        raise HTTPException(status_code=500, detail="decision support row failed validation") from exc


# ---------------------------------------------------------------------------
# Decisions
# ---------------------------------------------------------------------------


def _dispatch_payload(action: Mapping[str, Any], *, dss_id: str, coa_id: str, note: str) -> dict[str, Any]:
    p = action.get("params") or {}
    out: dict[str, Any] = {
        "note": note,
        "source": "decision_support",
        "dss_id": dss_id,
        "coa_id": coa_id,
        "count": int(p.get("count", 1)),
    }
    if p.get("role"):
        out["role"] = str(p["role"])[:32]
    if p.get("unit_ids"):
        out["proposed_unit_ids"] = [str(u)[:64] for u in p["unit_ids"]][:8]
    return out


#: The emulated unit an agency's dispatch request names when the unit plane proposed none (the deck's defaults).
FALLBACK_UNIT_ID = {
    "jan_rakshak": "CV-EM-01",
    "police": "PCR-EM-01",
    "traffic": "TP-EM-01",
    "ambulance": "108-EM-01",
    "fire": "FIRE-EM-01",
}


async def decide(
    conn: Any,
    dss_id: str,
    *,
    decision: str,
    actor: str,
    detail: Mapping[str, Any] | None,
    note: str | None,
    coa: Mapping[str, Any] | None,
    event_id: str | None,
    waypoint_junction: int | None,
    promoted_event_id: str | None,
    next_steps: Sequence[Mapping[str, Any]],
    now: datetime,
) -> dict[str, Any]:
    """Step (2) of an approval, or a reject / defer, in ONE transaction holding the DSS row lock: the dispatch
    requests (approve), the DSS state and the decision log row.  Any failure rolls the whole step back, so the
    DSS stays proposed and a retry duplicates nothing.  A lazy expiry found under the lock is committed (the
    transaction ends normally) before the 409 ``not-proposed`` is raised."""
    to_state = {"approve": "approved", "reject": "rejected", "defer": "deferred"}[decision]
    state = "proposed"
    async with conn.transaction():
        row = await get_row(conn, dss_id, for_update=True)
        if row is None:
            raise HTTPException(status_code=404, detail=f"decision support {dss_id} not found")
        state = await expire_if_due(conn, row, now=now)
        if state == "proposed":
            out = await _decide_locked(
                conn, dss_id, decision=decision, to_state=to_state, actor=actor, detail=detail, note=note,
                coa=coa, event_id=event_id, waypoint_junction=waypoint_junction,
                promoted_event_id=promoted_event_id, next_steps=next_steps, now=now,
            )
    if state != "proposed":
        raise Refused("not-proposed")
    return out


async def _decide_locked(
    conn: Any,
    dss_id: str,
    *,
    decision: str,
    to_state: str,
    actor: str,
    detail: Mapping[str, Any] | None,
    note: str | None,
    coa: Mapping[str, Any] | None,
    event_id: str | None,
    waypoint_junction: int | None,
    promoted_event_id: str | None,
    next_steps: Sequence[Mapping[str, Any]],
    now: datetime,
) -> dict[str, Any]:
    """The writes of one decision, inside :func:`decide`'s transaction with the DSS row locked and proposed."""
    dispatch_ids: list[str] = []
    dispatches = [a for a in (coa or {}).get("actions", []) if a.get("verb") == "dispatch"]
    if decision == "approve" and dispatches:
        if event_id is None:
            raise Refused("no-anchor")
        event = await conn.fetchrow(_SQL_EVENT_CHECK, event_id)
        if event is None:
            raise HTTPException(status_code=404, detail="event not found")
        if event["status"] not in LIVE_EVENT_STATUSES:
            raise HTTPException(
                status_code=409, detail="event is not active (status=" + str(event["status"]) + ")"
            )
        for a in dispatches:
            p = a.get("params") or {}
            agency = str(p.get("agency") or "police")
            count = int(p.get("count", 1))
            units = [str(u) for u in p.get("unit_ids") or []]
            unit_id = units[0] if units else FALLBACK_UNIT_ID.get(agency, "CV-EM-01")
            text = (
                f"Decision support {dss_id} · {coa['coa_id']} ({coa['label']}): {agency} × {count} — a dispatch "
                "REQUEST, decided on its own by a duty officer"
            )[:500]
            payload = _dispatch_payload(a, dss_id=dss_id, coa_id=str(coa["coa_id"]), note=text)
            created = await conn.fetchrow(
                DSS_DISPATCH_INSERT,
                event_id,
                agency,
                unit_id,
                waypoint_junction,
                actor,
                json.dumps(payload),
            )
            did = str(created["dispatch_id"])
            await _audit(conn, did, None, "requested", actor, text, detail)
            dispatch_ids.append(did)
    moved = await conn.fetchrow(
        _SQL_DECIDE, dss_id, to_state, actor, now, (coa or {}).get("coa_id"), note
    )
    if moved is None:
        raise Refused("not-proposed")
    log = await conn.fetchrow(
        _SQL_INSERT_LOG,
        dss_id,
        decision,
        (coa or {}).get("coa_id"),
        actor,
        note,
        now,
        promoted_event_id,
        dispatch_ids,
        json.dumps(list(next_steps)),
    )
    return {"state": to_state, "dispatch_ids": dispatch_ids, "log_id": log["log_id"] if log else None}


class Refused(Exception):
    """A 409 the decision returns with its C-U code."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code
