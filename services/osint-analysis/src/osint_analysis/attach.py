"""Attach, don't duplicate (OSINT SPEC §1.5): check each situation, READ-ONLY, against the live corridor state.

A situation **corroborates** a live event when it reports the SAME situation, that is when (all of):

* the live ref is a corridor event: an ``event:`` URN (C-T's dossier relation ``corroborates`` points at an
  event). A convoy in motion (``convoy:`` / ``movement:``), a dispatch or any other ref is never corroborated;
* the event is ``active``. An event in planning or approved has not started, and a live ref carries no time
  window that could show an overlap;
* the event's kind is one the situation's classes can be (:data:`CORROBORATING_KINDS`): an accident report
  corroborates a ``road_accident`` event, a crowd report a ``mass_gathering``. Nothing corroborates a
  ``protected_movement`` (an accident on a VVIP route is a second-order effect, flagged by
  :mod:`osint_analysis.second_order`, not the movement itself), a ``vehicle_pursuit`` (human-initiated) or a
  ``crime_incident`` (ANPR/watchlist origin): OSINT never links a report to either;
* they are co-located: the event's point is within :data:`ATTACH_RADIUS_M` (900 m) of the situation's point, or
  the situation lies on a segment of the event's route (``segment_ids``);
* they overlap in time: the situation is still current at the snapshot (``window_end`` + its class window ≥
  ``as_of``). A stale report never corroborates today's event.

Otherwise it is ``novel``. The nearest corroborated event wins (an in-radius event before a route-only match, then
the distance, then the URN). Three kinds of situation are always novel, because they cannot honestly corroborate a
specific live event: an area-level situation (a district or state alert has no precise location), a non-event
class (chatter), and any situation when no live state is given. The pipeline checks SURFACED situations only: a
held one (a single social post, one community's posts, chatter, a state-wide alert) is reported novel unchecked,
so one person's post is never linked to a live event.

Nothing here writes: the snapshot is only read, and the result is a new :class:`AttachResult`.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Any

from osint_common import kinds
from osint_common.types import AttachResult, LiveEventRef, LiveStateSnapshot
from osint_analysis.fusion import best_member, class_window, haversine_m

__all__ = [
    "ATTACH_RADIUS_M",
    "CORROBORATING_KINDS",
    "EVENT_URN_PREFIX",
    "LIVE_STATUSES",
    "LiveSubject",
    "attach",
    "attach_one",
    "corroborable_kinds",
    "is_current",
]

#: Co-location radius between a situation and a live event (the PoC's 900 m).
ATTACH_RADIUS_M = 900.0
#: Live event statuses that can be corroborated: only an event that is happening now.
LIVE_STATUSES: frozenset[str] = frozenset({"active"})
#: The one kind of live ref a situation can corroborate: a corridor event.
EVENT_URN_PREFIX = "event:"
#: The live corridor-event kinds a situation of each class can be the same situation as: a class's own Sajag kind
#: (the lexicon's) and the planned events of the same nature.
#: Never protected_movement, vehicle_pursuit or crime_incident (ANPR/watchlist origin).
CORROBORATING_KINDS: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        "reported_crime": frozenset({"reported_crime"}),
        "public_conflict": frozenset({"public_disorder"}),
        "road_accident": frozenset({"road_accident"}),
        "fire": frozenset({"hazard", "emergency_evacuation"}),
        "urban_flooding": frozenset({"flooding", "emergency_evacuation"}),
        "infra_failure": frozenset({"infra_failure", "emergency_evacuation"}),
        "hazard": frozenset({"hazard", "emergency_evacuation"}),
        "public_gathering": frozenset({"mass_gathering", "procession", "ceremonial", "race", "egress_surge"}),
        "procession": frozenset({"procession", "ceremonial"}),
        "unrest": frozenset({"public_disorder"}),
        "road_closure": frozenset({"work_zone"}),
        "weather_hazard": frozenset({"hazard"}),
    }
)


def corroborable_kinds(classes: Iterable[str]) -> frozenset[str]:
    """The live event kinds a situation of these classes can corroborate (the union over its classes)."""
    out: frozenset[str] = frozenset()
    for c in classes:
        out |= CORROBORATING_KINDS.get(c, frozenset())
    return out


@dataclass(frozen=True, slots=True)
class LiveSubject:
    """What the live checks read of a situation: its classes, point, area level, on-road segments and window."""

    event_class: str
    classes: tuple[str, ...]
    rep_lon: float | None
    rep_lat: float | None
    area_level: bool
    segment_ids: frozenset[int]
    window_start: datetime | None
    window_end: datetime | None

    @classmethod
    def of(cls, situation: Any) -> LiveSubject:
        """From an :class:`osint_analysis.correlate.Situation`, a :class:`~osint_common.types.ResolvedEvent` (or
        any object with ``event_class, rep_lon, rep_lat, area_level, segment_id, window_start, window_end`` and,
        optionally, ``correlated_classes``)."""
        if isinstance(situation, LiveSubject):
            return situation
        members = getattr(situation, "members", None)
        if members is not None and getattr(situation, "classes", None) is not None:
            geo = best_member(members)
            point = geo.scope == "point"
            segments = frozenset(
                m.on_segment for m in members if m.scope == "point" and m.on_segment is not None
            )
            # the point-level members time a point situation: an attached area alert is context, and its validity
            # never keeps a street report current (the pipeline's window, "Area context" in its docstring)
            timed = [m for m in members if m.scope == "point"] or list(members)
            return cls(
                event_class=situation.classes[0],
                classes=tuple(situation.classes),
                rep_lon=geo.lon,  # a district's representative point; None for a state (it has no point)
                rep_lat=geo.lat,
                area_level=not point,
                segment_ids=segments,  # type: ignore[arg-type]
                window_start=min(m.t0 for m in timed),
                window_end=max(m.t1 for m in timed),
            )
        segment = getattr(situation, "segment_id", None)
        explicit = getattr(situation, "segment_ids", None)
        segs = frozenset(explicit) if explicit is not None else frozenset({segment} if segment else set())
        correlated = getattr(situation, "correlated_classes", None) or [situation.event_class]
        return cls(
            event_class=situation.event_class,
            classes=tuple(correlated),
            rep_lon=situation.rep_lon,
            rep_lat=situation.rep_lat,
            area_level=bool(situation.area_level),
            segment_ids=segs,
            window_start=situation.window_start,
            window_end=situation.window_end,
        )


def is_current(subject: LiveSubject, as_of: datetime) -> bool:
    """Whether a situation is still current at the snapshot time (its window end plus its class window)."""
    end = subject.window_end or subject.window_start
    if end is None:
        return False
    return end + class_window(subject.event_class) >= as_of


def _candidates(subject: LiveSubject, events: Iterable[LiveEventRef]) -> list[tuple[int, float, str, float | None]]:
    wanted = corroborable_kinds(subject.classes)
    out: list[tuple[int, float, str, float | None]] = []
    for ev in events:
        if not ev.urn.startswith(EVENT_URN_PREFIX) or ev.status not in LIVE_STATUSES or ev.event_kind not in wanted:
            continue
        distance = None
        if ev.lat is not None and ev.lon is not None and subject.rep_lat is not None and subject.rep_lon is not None:
            distance = haversine_m(subject.rep_lat, subject.rep_lon, ev.lat, ev.lon)
        within = distance is not None and distance <= ATTACH_RADIUS_M
        on_route = bool(subject.segment_ids & set(ev.segment_ids))
        if within or on_route:
            out.append((0 if within else 1, distance if distance is not None else math.inf, ev.urn, distance))
    out.sort()
    return out


def attach_one(situation: Any, live: LiveStateSnapshot | None) -> AttachResult:
    """The read-only attach check of one situation (see the module docstring)."""
    if live is None:
        return AttachResult(novel=True)
    subject = LiveSubject.of(situation)
    if subject.area_level or subject.rep_lon is None or subject.event_class not in kinds.EVENT_CLASSES:
        return AttachResult(novel=True)
    if not is_current(subject, live.as_of):
        return AttachResult(novel=True)
    found = _candidates(subject, live.live_events)
    if not found:
        return AttachResult(novel=True)
    _, _, urn, distance = found[0]
    return AttachResult(
        novel=False,
        corroborates_live_urn=urn,
        distance_m=None if distance is None else round(distance, 1),
    )


def attach(situations: Sequence[Any], live: LiveStateSnapshot | None) -> list[AttachResult]:
    """``attach(situations, live)``: one :class:`AttachResult` per situation, in order. Read-only."""
    return [attach_one(s, live) for s in situations]
