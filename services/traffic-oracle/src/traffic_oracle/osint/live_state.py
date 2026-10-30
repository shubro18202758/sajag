"""The live corridor state the OSINT pipeline attaches to — READ-ONLY (contract C-T, X18; OSINT SPEC
§1.6 (c)).

``snapshot(conn, *, now=None, valkey=None) -> LiveStateSnapshot`` feeds ``run_pipeline(...,
live=...)``: the attach check ("attach, don't duplicate": a co-located live event is corroborated,
never duplicated) and the second-order flags (a reported situation on an active protected corridor,
a live convoy's route, a 108 route or a closed segment — ``osint_analysis.second_order``).  Reads
only, no write, no lock; the oracle's own stores and query shapes, no new table:

* **live events** — corridor events in planning, approved or active (``events.corridor_events``),
  ACTIVE ones first (then approved, then planning, newest first), so a long tail of stale plans can
  never push a running event out of the bound.  ``segment_ids`` is the route the event RUNS: its
  CURRENT rank-1 spine (``events.event_routes``, the snapshot's ``load_event_spines``; a re-routed
  event's new primary).  The alternates a protected movement carries (the brain's ``alt-1`` …
  ``alt-4``) are contingencies the convoy is not on: a report there is never "on the route of an
  active protected movement".  An event with no spine of its own but a linked legacy movement
  (``movement_id``) takes that movement's rank-1 planned route (``convoy.planned_routes``, the
  adaptive loop's query).  Its point: the 021 geotag, else the point of the rank-1 spine nearest its
  centroid (the snapshot's marker rule), else the zone centroid.  The pipeline reads only ACTIVE
  events (attach and second order alike): planning and approved ones are listed and never flagged;
* **convoys in motion** — ``LiveEventRef(urn="convoy:<movement_id>",
  event_kind="protected_movement", status=..., lon/lat = the live position, segment_ids = the
  route)`` for every active legacy movement (``convoy.movements``) and every live C-B position frame
  (Valkey ``convoy:position:{movement_id}``, EX 30 s, validated by the city snapshot's
  ``convoy_entity``).  The route is the linked corridor event's rank-1 spine, else the movement's
  rank-1 planned route, else the frame's own segment.  The position is the frame's; a convoy without
  a frame has no point (its route still flags).  The status is ``active`` when its movement or its
  event is active (a frame linked to nothing in the store is a convoy in motion: C-B frames exist
  only while one moves); a frame of a planning or approved movement or event carries that status
  (never flagged); one of a completed or cancelled movement or event is dropped;
* **108 / ambulance routes** — approved or en-route ambulance dispatches (``corridor.dispatches``)
  of live events: the route a producer stored with the dispatch
  (``request_payload.route_segment_ids`` or ``segment_ids``), else the path the dispatched unit
  drives (the units module's C-N rule and queries, ``units.router._resolve_path``: from its
  staging segment — the first segment of the event's OWN current spine, or, for a pursuit event
  with a spine, the segment nearest the agency's post closest to the waypoint — over
  ``corridor.road_graph`` to the nearest approach segment of its waypoint junction).  An on-scene
  unit has arrived (its onward route is unknown); a dispatch without a waypoint, an event without
  a spine of its own (a linked movement's planned route is not where a unit stages) and a post
  with no road segment all leave the unit waiting where it stages: none has a route, and none is
  invented.  Paths are cached per (dispatch, waypoint,
  start) for :data:`ROUTE_CACHE_TTL_SEC`; at most :data:`MAX_ROUTE_SEARCHES` new searches run per
  snapshot;
* **closures** — the current rank-1 spine segments of ACTIVE events whose phase covering now carries
  a closure policy (``full_closure`` / ``partial_closure``, the simulator's and emulator's
  vocabulary; ``full`` / ``partial``, the brain's protocol phases for Z+ / Z movements).  A signal
  hold, a speed restriction or a managed phase closes nothing; an approved event's phase is not in
  force yet.

Bounded by the LiveStateSnapshot limits (2 000 live refs — events and convoys — and routes, 5 000
closures). A source that cannot be read (no Valkey, a frame that fails validation, a graph search
that fails) is skipped and logged, never fatal: the snapshot is the best honest picture, and the
ingest it feeds never fails on it.

A corridor event PROMOTED from an OSINT situation stays in the live state on purpose: a different,
independent situation reporting the same incident must still attach to it ("attach, don't
duplicate"), so it is not promoted twice.  The situation the event was promoted from never
corroborates it — the store records that attach as novel (``store._SQL_CLEAR_SELF_ATTACH``, which
also covers a situation that absorbed the promoted one).
"""

from __future__ import annotations

import time
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

import structlog

from osint_common.types import (
    LiveAmbulanceRoute,
    LiveClosure,
    LiveEventRef,
    LiveStateSnapshot,
)
from traffic_oracle.adaptive.engine_loop import _MOVEMENT_ROUTES_SQL
from traffic_oracle.city.common import (
    as_dict,
    as_uuid,
    event_provenance_supported,
    finite,
    json_doc,
    scan_mget,
    subject_key,
    valid_lonlat,
)
from traffic_oracle.city.entities import (
    CONVOY_POSITION_PREFIX,
    MAX_CONVOY_KEYS,
    convoy_entity,
    load_event_spines,
    spine_doc,
)
from traffic_oracle.units import router as units_router

logger = structlog.get_logger(__name__)

__all__ = [
    "AMBULANCE_AGENCY",
    "CLOSURE_TYPES",
    "MAX_CLOSURES",
    "MAX_CONVOYS",
    "MAX_EVENTS",
    "MAX_LIVE",
    "MAX_ROUTE_SEARCHES",
    "ROUTE_CACHE_TTL_SEC",
    "ROUTE_DISPATCH_STATUSES",
    "reset_route_cache",
    "snapshot",
]

#: Live refs per snapshot (``LiveStateSnapshot.live_events``): corridor events and convoys together.
MAX_LIVE = 2000
#: Convoys in motion per snapshot (the city snapshot's convoy-frame bound).
MAX_CONVOYS = MAX_CONVOY_KEYS
#: Corridor events per snapshot: the rest of the live-ref bound.
MAX_EVENTS = MAX_LIVE - MAX_CONVOYS
MAX_CLOSURES = 5000
#: Segment ids per route (``LiveEventRef`` / ``LiveAmbulanceRoute``).
MAX_ROUTE_SEGMENTS = 512

#: The 108 agency (``units.agencies``).
AMBULANCE_AGENCY = "ambulance"
#: Dispatch statuses whose unit is on (or about to take) its route; an on-scene unit has arrived.
ROUTE_DISPATCH_STATUSES: tuple[str, ...] = ("approved", "en_route")
#: Phase closure types that close a road (the simulator / emulator vocabulary, and the brain's
#: protocol phases).
CLOSURE_TYPES: tuple[str, ...] = ("full_closure", "partial_closure", "full", "partial")

#: New graph searches per snapshot (a cached path costs none); the ingest transaction stays short.
MAX_ROUTE_SEARCHES = 50
#: How long a dispatch's searched path is reused (a re-routed event restages when it expires).
ROUTE_CACHE_TTL_SEC = 300.0
_ROUTE_CACHE_MAX = 512
_ROUTE_CACHE: dict[tuple[str, int, int], tuple[float, tuple[int, ...]]] = {}

_LIVE_ORDER = (
    "ORDER BY CASE e.status WHEN 'active' THEN 0 WHEN 'approved' THEN 1 ELSE 2 END, "
    "e.created_at DESC, e.event_id LIMIT $1"
)

_SQL_LIVE_EVENTS = "SELECT e.event_id, e.event_kind, e.status, e.movement_id, ST_X(ST_Centroid(e.zone_geom)) AS zone_lon, ST_Y(ST_Centroid(e.zone_geom)) AS zone_lat FROM events.corridor_events e WHERE e.status IN ('planning', 'approved', 'active') " + _LIVE_ORDER  # noqa: E501

#: Migration 021 (probed): the same, with the geotag point.
_SQL_LIVE_EVENTS_GEOTAG = "SELECT e.event_id, e.event_kind, e.status, e.movement_id, ST_X(ST_Centroid(e.zone_geom)) AS zone_lon, ST_Y(ST_Centroid(e.zone_geom)) AS zone_lat, ST_X(e.geotag) AS geotag_lon, ST_Y(e.geotag) AS geotag_lat FROM events.corridor_events e WHERE e.status IN ('planning', 'approved', 'active') " + _LIVE_ORDER  # noqa: E501

#: The status of the corridor events convoy frames name (any status: a closed one drops its frame).
_SQL_EVENT_STATUS = "SELECT e.event_id, e.status, e.event_kind, e.movement_id FROM events.corridor_events e WHERE e.event_id = ANY($1::uuid[])"  # noqa: E501

#: Active legacy convoy movements (the VVIP base case still creates them).
_SQL_ACTIVE_MOVEMENTS = "SELECT m.movement_id, m.status FROM convoy.movements m WHERE m.status = 'active' ORDER BY m.planned_start NULLS LAST, m.movement_id LIMIT $1"  # noqa: E501

#: The status of the movements convoy frames name.
_SQL_MOVEMENT_STATUS = "SELECT m.movement_id, m.status FROM convoy.movements m WHERE m.movement_id = ANY($1::uuid[])"  # noqa: E501

#: Approved / en-route 108 dispatches of live events, with what their route is derived from.
_SQL_AMBULANCE_DISPATCHES = "SELECT d.dispatch_id, d.event_id, d.waypoint_junction, d.request_payload, e.event_kind FROM corridor.dispatches d JOIN events.corridor_events e ON e.event_id = d.event_id WHERE d.agency = '" + AMBULANCE_AGENCY + "' AND d.status IN (" + ", ".join(f"'{s}'" for s in ROUTE_DISPATCH_STATUSES) + ") AND e.status IN ('planning', 'approved', 'active') ORDER BY d.created_at, d.dispatch_id LIMIT $1"  # noqa: E501

#: ACTIVE events with a phase covering now whose policy closes the road ($1: the closure types).
_SQL_CLOSING_EVENTS = "SELECT DISTINCT p.event_id FROM events.event_phases p JOIN events.corridor_events e ON e.event_id = p.event_id WHERE e.status = 'active' AND p.window_start <= NOW() AND p.window_end >= NOW() AND p.closure_policy->>'closure_type' = ANY($1::text[])"  # noqa: E501

_ROUTE_KEYS = ("route_segment_ids", "segment_ids")
_STATUS_RANK = {"active": 0, "approved": 1, "planning": 2}


def reset_route_cache() -> None:
    """Forget the cached dispatch paths (tests)."""
    _ROUTE_CACHE.clear()


def _positive_ids(values: Any) -> list[int]:
    out: list[int] = []
    for v in values or []:
        f = finite(v)
        if f is not None and f > 0 and float(f).is_integer() and int(f) not in out:
            out.append(int(f))
    return out


def _primary_route(docs: Sequence[Mapping[str, Any]]) -> list[int]:
    """The rank-1 CURRENT spine's segments (``spine_doc`` order: rank, then newest)."""
    ordered = sorted(docs, key=lambda d: d["rank"])
    return _positive_ids(ordered[0]["segment_ids"])[:MAX_ROUTE_SEGMENTS] if ordered else []


async def _movement_routes(conn: Any, movement_ids: Iterable[str]) -> dict[str, list[int]]:
    """Rank-1 planned route per legacy movement (``convoy.planned_routes``)."""
    ids = sorted({m for m in movement_ids if as_uuid(m) is not None})
    out: dict[str, list[int]] = {}
    if not ids:
        return out
    for r in await conn.fetch(_MOVEMENT_ROUTES_SQL, ids):
        key = subject_key(r["movement_id"])
        if key not in out:
            out[key] = _positive_ids(r["segment_ids"])[:MAX_ROUTE_SEGMENTS]
    return out


async def _convoy_frames(valkey: Any) -> list[dict]:
    """The C-B frames in Valkey as validated convoy entities ([] without a client; never raises)."""
    if valkey is None:
        return []
    try:
        pairs, _ = await scan_mget(valkey, CONVOY_POSITION_PREFIX, max_keys=MAX_CONVOY_KEYS)
    except Exception as exc:  # noqa: BLE001 — frames are optional: route-only convoys still flag
        logger.warning("osint.live_state.convoy_frames_unreadable", error_type=type(exc).__name__)
        return []
    out: list[dict] = []
    now = datetime.now(UTC)
    for key, raw in pairs:
        doc = json_doc(raw)
        ent = convoy_entity(key, doc, now) if doc else None
        if ent is not None:
            out.append(ent)
    return out


def _convoy_status(links: Iterable[str | None]) -> str | None:
    """A convoy's status from its known links: active wins; a planning / approved link is carried;
    only closed links → "closed"; none known → None (the caller decides)."""
    known = [s for s in links if s]
    open_ = [s for s in known if s in _STATUS_RANK]
    if open_:
        return min(open_, key=lambda s: _STATUS_RANK[s])
    return "closed" if known else None


async def _ambulance_route(
    conn: Any,
    row: Mapping[str, Any],
    spine: Sequence[int] | None,
    budget: list[int],
) -> list[int]:
    """One 108 dispatch's route (see the module docstring); [] when it has none.

    ``spine`` is the event's OWN current rank-1 spine, None when the event has no spine row: the
    units module stages from that alone (``units.router._resolve_path``), never from a linked
    movement's planned route, and only an event with a spine is staged as a pursuit.  A pursuit
    unit starts at its agency's post; a post with no road segment draws no path (the unit waits
    there), so neither does this."""
    payload = as_dict(row.get("request_payload"))
    stored = next((_positive_ids(payload.get(k)) for k in _ROUTE_KEYS if payload.get(k)), [])
    if stored:
        return stored[:MAX_ROUTE_SEGMENTS]
    waypoint = finite(row.get("waypoint_junction"))
    if waypoint is None or waypoint <= 0:
        return []
    junction = int(waypoint)
    start: int | None = next(iter(spine or []), None)
    if spine is not None and row.get("event_kind") == units_router.PURSUIT_EVENT_KIND:
        station = await units_router._nearest_station(conn, AMBULANCE_AGENCY, junction)
        if station is not None:  # staged at the post, never on the suspect's spine
            seg = finite(station.get("segment_id"))
            start = int(seg) if seg is not None and seg > 0 else None
    if start is None:
        return []
    key = (str(row["dispatch_id"]), junction, int(start))
    hit = _ROUTE_CACHE.get(key)
    now = time.monotonic()
    if hit is not None and hit[0] > now:
        return list(hit[1])
    approaches = _positive_ids(
        r["segment_id"]
        for r in await conn.fetch(units_router._SQL_JUNCTION_ADJACENT_SEGMENT, junction)
    )
    if not approaches:
        return []
    if start in approaches:
        path = [int(start)]  # already on an approach: it drives straight to the junction
    else:
        if budget[0] <= 0:
            return []  # searched next time (bounded per snapshot)
        budget[0] -= 1
        try:
            searched = {
                t: await units_router._shortest_path_on(conn, int(start), t) for t in approaches
            }
            path = _positive_ids(units_router.cheapest_path(searched))
        except Exception as exc:  # noqa: BLE001 — a failed search: no route for this dispatch
            logger.warning(
                "osint.live_state.route_search_failed",
                dispatch_id=str(row["dispatch_id"]),
                error_type=type(exc).__name__,
            )
            return []
    if len(_ROUTE_CACHE) >= _ROUTE_CACHE_MAX:
        _ROUTE_CACHE.clear()
    _ROUTE_CACHE[key] = (now + ROUTE_CACHE_TTL_SEC, tuple(path))
    return path[:MAX_ROUTE_SEGMENTS]


async def snapshot(
    conn: Any, *, now: datetime | None = None, valkey: Any = None
) -> LiveStateSnapshot:
    """The live corridor state at ``now`` (read-only; see the module docstring).  ``valkey`` is the
    app's Valkey client (``app.state.adaptive_valkey``) for the convoy position frames; without one,
    convoys come from the store alone (a route, no point)."""
    when = now or datetime.now(UTC)
    sql = _SQL_LIVE_EVENTS_GEOTAG if await event_provenance_supported(conn) else _SQL_LIVE_EVENTS
    rows = list(await conn.fetch(sql, MAX_EVENTS))
    dispatches = list(await conn.fetch(_SQL_AMBULANCE_DISPATCHES, MAX_LIVE))
    frames = await _convoy_frames(valkey)
    active_movements = {
        subject_key(r["movement_id"]): r["status"]
        for r in await conn.fetch(_SQL_ACTIVE_MOVEMENTS, MAX_CONVOYS)
    }

    # the events convoy frames name that the live read did not return (a closed one drops its frame)
    events_by_id: dict[str, Mapping[str, Any]] = {str(r["event_id"]): r for r in rows}
    framed_events = {
        e for e in (f["props"].get("event_id") for f in frames) if e and e not in events_by_id
    }
    extra_events: dict[str, Mapping[str, Any]] = {}
    if framed_events:
        for r in await conn.fetch(_SQL_EVENT_STATUS, sorted(framed_events)):
            extra_events[str(r["event_id"])] = r

    # spines: every live event's, plus the dispatch and frame events read beyond the live bound
    spine_ids = list(events_by_id)
    spine_ids += [
        str(d["event_id"]) for d in dispatches if str(d["event_id"]) not in events_by_id
    ]
    spine_ids += [e for e, r in extra_events.items() if r["status"] in _STATUS_RANK]
    spine_ids = list(dict.fromkeys(spine_ids))
    spines: dict[str, list[Any]] = {}
    if spine_ids:
        spines, _ = await load_event_spines(conn, spine_ids)
    docs_by_event = {eid: spine_doc(rs) for eid, rs in spines.items()}
    #: each event's OWN current rank-1 spine (only events with a spine row)
    own_spine = {eid: _primary_route(docs) for eid, docs in docs_by_event.items() if docs}
    route_of = dict(own_spine)

    # legacy movement routes: for movement-linked events without a spine, and for convoys
    event_of_movement: dict[str, str] = {}
    for r in [*rows, *extra_events.values()]:
        if r.get("movement_id") is not None:
            event_of_movement.setdefault(subject_key(r["movement_id"]), str(r["event_id"]))
    frame_movements = {subject_key(f["props"]["movement_id"]) for f in frames}
    movement_status: dict[str, str] = dict(active_movements)
    unknown = sorted(m for m in frame_movements - set(movement_status) if as_uuid(m) is not None)
    if unknown:
        for r in await conn.fetch(_SQL_MOVEMENT_STATUS, unknown):
            movement_status[subject_key(r["movement_id"])] = r["status"]
    planned = await _movement_routes(
        conn, {*event_of_movement, *movement_status, *frame_movements}
    )
    # an event without a spine of its own runs its linked legacy movement's planned route
    for r in [*rows, *extra_events.values()]:
        eid = str(r["event_id"])
        if not route_of.get(eid) and r.get("movement_id") is not None:
            route_of[eid] = planned.get(subject_key(r["movement_id"]), [])

    live: list[LiveEventRef] = []
    for r in rows:
        eid = str(r["event_id"])
        docs = docs_by_event.get(eid, [])
        segments = route_of.get(eid) or []
        point = valid_lonlat(r.get("geotag_lon"), r.get("geotag_lat"))
        if point is None:
            point = next(
                (valid_lonlat(d["lon"], d["lat"]) for d in sorted(docs, key=lambda d: d["rank"])
                 if d["lon"] is not None),
                None,
            )
        if point is None:
            point = valid_lonlat(r.get("zone_lon"), r.get("zone_lat"))
        try:
            live.append(
                LiveEventRef(
                    urn=f"event:{eid}",
                    event_kind=r["event_kind"],
                    status=r["status"],
                    lon=point[0] if point else None,
                    lat=point[1] if point else None,
                    segment_ids=segments,
                )
            )
        except ValueError:
            logger.warning("osint.live_state.event_skipped", event_id=eid)

    # convoys in motion: active movements and live frames, one ref per movement
    event_status = {
        eid: str(r["status"]) for eid, r in [*events_by_id.items(), *extra_events.items()]
    }
    frame_of: dict[str, dict] = {}
    for f in frames:
        frame_of.setdefault(subject_key(f["props"]["movement_id"]), f)
    convoys: list[LiveEventRef] = []
    for mid in list(dict.fromkeys([*active_movements, *sorted(frame_of)])):
        if len(convoys) >= MAX_CONVOYS:
            break
        frame = frame_of.get(mid)
        framed = frame["props"].get("event_id") if frame else None
        linked_event = framed or event_of_movement.get(mid)
        status = _convoy_status([movement_status.get(mid), event_status.get(linked_event or "")])
        if status == "closed":
            continue  # the movement or its event is over: not a convoy in motion
        status = status or "active"  # an unlinked frame: C-B frames exist only while a convoy moves
        segments = (route_of.get(linked_event or "") or planned.get(mid) or [])
        if not segments and frame is not None and frame["props"].get("segment_id"):
            segments = _positive_ids([frame["props"]["segment_id"]])
        point = valid_lonlat(frame.get("lon"), frame.get("lat")) if frame else None
        try:
            convoys.append(
                LiveEventRef(
                    urn=f"convoy:{mid}",
                    event_kind="protected_movement",
                    status=status,
                    lon=point[0] if point else None,
                    lat=point[1] if point else None,
                    segment_ids=segments[:MAX_ROUTE_SEGMENTS],
                )
            )
        except ValueError:
            logger.warning("osint.live_state.convoy_skipped", movement_id=str(mid)[:64])
    live.extend(convoys)

    # 108 / ambulance routes
    routes: list[LiveAmbulanceRoute] = []
    budget = [MAX_ROUTE_SEARCHES]
    for d in dispatches:
        # staged from the event's own spine only: a planned-route fallback is not where it stages
        segments = await _ambulance_route(conn, d, own_spine.get(str(d["event_id"])), budget)
        if segments:
            routes.append(
                LiveAmbulanceRoute(
                    dispatch_urn=f"dispatch:{d['dispatch_id']}", segment_ids=segments
                )
            )

    # closures: active events' phases in force now
    closures: list[LiveClosure] = []
    seen: set[tuple[int, str]] = set()
    for c in await conn.fetch(_SQL_CLOSING_EVENTS, list(CLOSURE_TYPES)):
        eid = str(c["event_id"])
        for seg in route_of.get(eid, []):
            key = (seg, eid)
            if key not in seen and len(closures) < MAX_CLOSURES:
                seen.add(key)
                closures.append(LiveClosure(segment_id=seg, event_urn=f"event:{eid}"))

    return LiveStateSnapshot(
        as_of=when, live_events=live, ambulance_routes=routes, closures=closures
    )
