"""Resource feasibility (C-U; plan R22): can the COA be resourced NOW — units free, and how far away?

* ``required_resources`` — units per agency the COA's dispatch actions need;
* ``availability`` — per agency, the units in Valkey (contract C-A ``units:emulated:*``, status ``patrol`` or
  ``available``) MINUS the units committed to open dispatches (``requested``, ``approved``, ``en_route``,
  ``on_scene``) of live events (011) — a decision-support request's proposed units included;
* ``eta_to_scene_sec`` — the nearest free unit's pgRouting travel time to the scene (``pgr_dijkstraCost`` over
  the directed ``corridor.road_graph``, from the segment nearest its last frame), the slowest agency the COA
  needs;
* an infeasible COA keeps its ``shortfalls[]`` (``"police: need 2, 1 free"``, or ``"no road anchor: area-level
  report"``) and is ranked last and labelled, never hidden.

When the unit feed is unavailable nothing is assumed free: a dispatch COA is then infeasible with the shortfall
saying why.  Units are agencies' vehicles, never persons (C6).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import structlog

from traffic_oracle.decision_support.coa import CoaDraft
from traffic_oracle.units.router import LIVE_EVENT_STATUSES, OPEN_DISPATCH_STATUSES, read_patrol_units

logger = structlog.get_logger(__name__)

__all__ = [
    "FREE_STATUSES",
    "AgencyUnits",
    "UnitPlane",
    "availability",
    "committed_units",
    "feasibility",
    "proposed_units",
    "read_unit_plane",
]

#: Patrol frame statuses that count as free (C-A).
FREE_STATUSES: tuple[str, ...] = ("patrol", "available")

#: Units committed to an open dispatch of a live event: the request's own unit, plus — for a decision-support
#: request (``request_payload.source = 'decision_support'``), which may ask for several units of one agency — the
#: units it proposed (``request_payload.proposed_unit_ids``), so an approved 2-unit request commits both.
_SQL_COMMITTED_UNITS = "SELECT d.agency, d.unit_id, CASE WHEN d.request_payload->>'source' = 'decision_support' AND jsonb_typeof(d.request_payload->'proposed_unit_ids') = 'array' THEN ARRAY(SELECT jsonb_array_elements_text(d.request_payload->'proposed_unit_ids')) END AS proposed_unit_ids FROM corridor.dispatches d JOIN events.corridor_events e ON e.event_id = d.event_id WHERE d.status = ANY($1::text[]) AND e.status = ANY($2::text[]) ORDER BY d.agency, d.unit_id"  # noqa: E501

#: What a shortfall says when the unit feed itself is down.
FEED_UNAVAILABLE = "unit feed unavailable"


@dataclass(frozen=True)
class AgencyUnits:
    """One agency's free units: ``unit_ids`` nearest first (when an ETA is known)."""

    free: int
    unit_ids: tuple[str, ...] = ()
    fielded: int = 0
    committed: int = 0
    eta_sec: float | None = None


@dataclass(frozen=True)
class UnitPlane:
    agencies: Mapping[str, AgencyUnits] = field(default_factory=dict)
    #: ``valkey`` (live C-A frames), ``fixture`` (a test or parity input) or ``unavailable``
    source: str = "valkey"

    def free(self, agency: str) -> int:
        a = self.agencies.get(agency)
        return a.free if a else 0

    def eta(self, agency: str) -> float | None:
        a = self.agencies.get(agency)
        return a.eta_sec if a else None

    def unit_ids(self, agency: str) -> tuple[str, ...]:
        a = self.agencies.get(agency)
        return a.unit_ids if a else ()

    def summary(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "agencies": {
                k: {"free": v.free, "fielded": v.fielded, "committed": v.committed, "eta_sec": v.eta_sec}
                for k, v in sorted(self.agencies.items())
            },
        }

    @classmethod
    def from_fixture(cls, doc: Mapping[str, Mapping[str, Any]]) -> UnitPlane:
        """``{agency: {free, eta_sec, unit_ids?}}`` (the PoC's ``UNITS`` table, Sajag agency codes)."""
        return cls(
            {
                str(k): AgencyUnits(
                    free=int(v["free"]),
                    unit_ids=tuple(v.get("unit_ids") or ()),
                    fielded=int(v.get("fielded", v["free"])),
                    committed=int(v.get("committed", 0)),
                    eta_sec=float(v["eta_sec"]) if v.get("eta_sec") is not None else None,
                )
                for k, v in doc.items()
            },
            source="fixture",
        )


def committed_units(rows: Iterable[Mapping[str, Any]]) -> list[tuple[str, str]]:
    """``(agency, unit_id)`` per committed unit: each open request's unit, and every unit a decision-support
    request proposed (pure; the rows of :data:`_SQL_COMMITTED_UNITS`)."""
    out: list[tuple[str, str]] = []
    for r in rows:
        agency = str(r["agency"])
        out.append((agency, str(r["unit_id"])))
        out.extend((agency, str(u)) for u in (r.get("proposed_unit_ids") or [])[:8] if u)
    return out


def availability(
    patrols: Iterable[Mapping[str, Any]], committed: Iterable[tuple[str, str]]
) -> dict[str, tuple[list[Mapping[str, Any]], int, int]]:
    """Per agency: ``(free patrol rows, fielded, committed)`` — the free rows are the patrol frames with a free
    status whose unit is not committed to an open dispatch of a live event (pure)."""
    busy: dict[str, set[str]] = {}
    for agency, unit_id in committed:
        busy.setdefault(str(agency), set()).add(str(unit_id))
    out: dict[str, tuple[list[Mapping[str, Any]], int, int]] = {}
    for p in patrols:
        if p.get("status") not in FREE_STATUSES:
            continue
        agency = str(p.get("agency"))
        free, fielded, n_busy = out.get(agency, ([], 0, 0))
        fielded += 1
        if str(p.get("unit_id")) in busy.get(agency, set()):
            n_busy += 1
        else:
            free = [*free, p]
        out[agency] = (free, fielded, n_busy)
    return out


async def read_unit_plane(
    conn: Any,
    valkey: Any,
    *,
    now: datetime,
    graph: Any = None,
    scene_segment: int | None = None,
) -> UnitPlane:
    """The live unit plane: C-A patrol frames minus committed units, with pgRouting ETAs when a graph and a
    scene are known.  Never raises: a missing feed is ``source='unavailable'`` (nothing assumed free)."""
    patrols, meta = await read_patrol_units(valkey, now)
    if meta.get("status") != "ok":
        return UnitPlane({}, source="unavailable")
    try:
        rows = await conn.fetch(_SQL_COMMITTED_UNITS, list(OPEN_DISPATCH_STATUSES), list(LIVE_EVENT_STATUSES))
        committed = committed_units(rows)
    except Exception as exc:  # noqa: BLE001 — a failed read assumes nothing free rather than everything
        logger.warning("dss.committed_units_unavailable", error_type=type(exc).__name__)
        return UnitPlane({}, source="unavailable")
    by_agency = availability(patrols, committed)
    etas: dict[str, dict[str, float]] = {}
    if graph is not None and scene_segment is not None:
        try:
            etas = await _etas(graph, by_agency, int(scene_segment))
        except Exception as exc:  # noqa: BLE001 — an ETA is garnish: feasibility stands without it
            logger.warning("dss.unit_eta_unavailable", error_type=type(exc).__name__)
            etas = {}
    agencies: dict[str, AgencyUnits] = {}
    for agency, (free, fielded, n_busy) in sorted(by_agency.items()):
        unit_eta = etas.get(agency, {})
        ids = sorted((str(p["unit_id"]) for p in free), key=lambda u: (unit_eta.get(u, float("inf")), u))
        best = min(unit_eta.values()) if unit_eta else None
        agencies[agency] = AgencyUnits(
            free=len(free), unit_ids=tuple(ids), fielded=fielded, committed=n_busy,
            eta_sec=round(best, 1) if best is not None else None,
        )
    return UnitPlane(agencies, source="valkey")


async def _etas(
    graph: Any, by_agency: Mapping[str, tuple[list[Mapping[str, Any]], int, int]], scene: int
) -> dict[str, dict[str, float]]:
    units = [(a, p) for a, (free, _, _) in by_agency.items() for p in free if p.get("position")]
    if not units:
        return {}
    segs = await graph.nearest_segments([(float(p["position"][0]), float(p["position"][1])) for _, p in units])
    costs = await graph.path_costs([s for s in segs if s is not None], scene)
    out: dict[str, dict[str, float]] = {}
    for (agency, p), seg in zip(units, segs, strict=True):
        if seg is None or seg not in costs:
            continue
        out.setdefault(agency, {})[str(p["unit_id"])] = float(costs[seg])
    return out


def feasibility(draft: CoaDraft, plane: UnitPlane) -> dict[str, Any]:
    """The C-U ``resource_feasibility`` block of one COA."""
    need = draft.required_resources()
    shortfalls: list[str] = []
    if draft.anchor_shortfall:
        shortfalls.append(draft.anchor_shortfall)
    for agency in sorted(need):
        qty = need[agency]
        free = plane.free(agency)
        if qty > free:
            text = f"{agency}: need {qty}, {free} free"
            if plane.source == "unavailable":
                text += f" ({FEED_UNAVAILABLE})"
            shortfalls.append(text)
    etas = [e for a in need if (e := plane.eta(a)) is not None]
    return {
        "required_resources": {a: need[a] for a in sorted(need)},
        "availability": {a: plane.free(a) for a in sorted(need)},
        "eta_to_scene_sec": max(etas) if etas else None,
        "feasible": not shortfalls,
        "shortfalls": shortfalls,
    }


def proposed_units(draft: CoaDraft, plane: UnitPlane) -> None:
    """Name the free units each dispatch action would request (nearest first), in its params: the approval's
    dispatch REQUESTS use them, and an officer decides each request on its own."""
    taken: dict[str, int] = {}
    for a in draft.dispatches():
        p = a.setdefault("params", {})
        agency = str(p.get("agency") or "police")
        n = int(p.get("count", 1))
        ids = plane.unit_ids(agency)
        start = taken.get(agency, 0)
        chosen = list(ids[start:start + n])
        taken[agency] = start + n
        if chosen:
            p["unit_ids"] = chosen
