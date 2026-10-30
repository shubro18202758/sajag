"""Second-order effects on the live corridor state (OSINT SPEC §1.6 (c)): where OSINT stops being a news feed and
becomes operational intelligence. Read-only; every flag carries a short, neutral note of what the system knows.

For a situation that is located on the road network (not area-level) and still current at the snapshot
(:func:`osint_analysis.attach.is_current`), a flag is raised for each of:

* ``protected_corridor`` — one of its segments is on the route of an ACTIVE ``protected_movement`` event;
* ``convoy`` — a convoy in motion (a live ref whose URN is ``convoy:`` or ``movement:``, status active) has one of
  its segments on its route, or is within :data:`CONVOY_RADIUS_M` of the situation's point;
* ``ambulance_route`` — one of its segments is on an active ambulance (108) dispatch route;
* ``closure`` — one of its segments is already closed by a live corridor event.

A situation's segments are the segments its point members lie on (a road or neighbourhood's own segment, or a
point snapped within 900 m), so a note says "on or near segment N": a snapped landmark may be some way off the
road. A junction-only report has no segment, so it raises only the proximity ``convoy`` flag. Flags are
de-duplicated and ordered (kind, URN, segment), at most :data:`MAX_FLAGS`.

None of these is a corroboration: a report on a protected movement's route, near a convoy or on an ambulance (108)
route is a different situation that affects the live one (:mod:`osint_analysis.attach` never corroborates a
``protected_movement`` or a convoy).
"""

from __future__ import annotations

from typing import Any

from osint_common.types import LiveStateSnapshot, SecondOrderFlag
from osint_analysis.attach import LiveSubject, is_current
from osint_analysis.fusion import haversine_m

__all__ = ["CONVOY_RADIUS_M", "CONVOY_URN_PREFIXES", "MAX_FLAGS", "second_order_flags"]

#: Live refs that are convoys in motion (``convoy.movements``), not corridor events.
CONVOY_URN_PREFIXES: tuple[str, ...] = ("convoy:", "movement:")
#: A convoy this close to a situation's point is flagged even off its route.
CONVOY_RADIUS_M = 900.0
#: ``ResolvedEvent.second_order`` holds at most 32 flags.
MAX_FLAGS = 32
_KIND_ORDER = {"protected_corridor": 0, "convoy": 1, "ambulance_route": 2, "closure": 3}


def second_order_flags(situation: Any, live: LiveStateSnapshot | None) -> list[SecondOrderFlag]:
    """The second-order flags of one situation (see the module docstring); ``[]`` without a live state."""
    if live is None:
        return []
    subject = LiveSubject.of(situation)
    if subject.area_level or subject.rep_lon is None or not is_current(subject, live.as_of):
        return []
    segments = subject.segment_ids
    flags: dict[tuple[str, str, int | None], SecondOrderFlag] = {}

    def add(kind: str, urn: str, segment_id: int | None, note: str) -> None:
        key = (kind, urn, segment_id)
        if key not in flags:
            flags[key] = SecondOrderFlag(kind=kind, urn=urn, segment_id=segment_id, note=note)  # type: ignore[arg-type]

    for ev in live.live_events:
        if ev.status != "active":
            continue
        shared = sorted(segments & set(ev.segment_ids))
        if ev.urn.startswith(CONVOY_URN_PREFIXES):
            for seg in shared:
                add("convoy", ev.urn, seg, f"Reported on or near segment {seg}, on the route of a convoy in motion")
            if not shared and ev.lat is not None and ev.lon is not None and subject.rep_lat is not None:
                d = haversine_m(subject.rep_lat, subject.rep_lon, ev.lat, ev.lon)
                if d <= CONVOY_RADIUS_M:
                    add("convoy", ev.urn, None, f"Reported {round(d)} m from a convoy in motion")
        elif ev.event_kind == "protected_movement":
            for seg in shared:
                add(
                    "protected_corridor",
                    ev.urn,
                    seg,
                    f"Reported on or near segment {seg}, on the route of an active protected movement",
                )
    for route in live.ambulance_routes:
        for seg in sorted(segments & set(route.segment_ids)):
            add(
                "ambulance_route",
                route.dispatch_urn,
                seg,
                f"Reported on or near segment {seg}, on an active ambulance (108) route",
            )
    for closure in live.closures:
        if closure.segment_id in segments:
            add(
                "closure",
                closure.event_urn,
                closure.segment_id,
                f"Segment {closure.segment_id} is already closed by a live corridor event",
            )
    ordered = sorted(flags.values(), key=lambda f: (_KIND_ORDER[f.kind], f.urn, f.segment_id or 0))
    return ordered[:MAX_FLAGS]
