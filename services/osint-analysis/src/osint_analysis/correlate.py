"""Stage 2 of the two-stage fusion: correlate co-located, time-overlapping base clusters of RELATED classes into
one situation (OSINT SPEC §1.5). This is the composite a single-class deduper misses: the Western Express Highway
``road_accident`` reports near Andheri and the co-located "beaten by mob" ``public_conflict`` report become one
``affray+collision`` situation.

Two base clusters join when (all of):

* their classes form a :data:`osint_common.kinds.RELATED_CLASSES` pair, and their realms match;
* they are **co-located at the same level**: two point clusters whose representatives (the highest-confidence
  point members) are within :data:`CORRELATE_RADIUS_M` (the PoC's 1 200 m) or on one segment with a line geocode;
  two district clusters of the same district; two state clusters of the same state. A state-level cluster never
  joins a district or point situation (plan R28), and an area-wide alert does not locate a point situation by
  containment alone: a district alert and a point report join only through Stage 1's text evidence. Otherwise
  a district-wide warning would label a street report "Official, verified" and absorb unrelated points;
* they **overlap in time**: the gap between their windows is at most the wider of the two class windows (state
  aggregates have no window).

**One cluster per class.** A situation never holds two base clusters of the same class: Stage 1 kept them apart
because they are two incidents, and a report between them must not chain them back together (a clash report
1.1 km from two accidents 2.2 km apart joins ONE of them). The candidate joins are taken nearest first (the
distance between the representatives to the metre, 0 for two areas; ties by the earlier clusters), and a join is
refused when the two groups already share a class. So each situation has at most one base cluster of each class,
and the outcome does not depend on the input order.

The situation's primary class follows :data:`osint_common.kinds.RESPONSE_PRIORITY`, ties broken deterministically:
more member reports first, then the earliest report, then the class order of
:data:`osint_common.kinds.EVENT_CLASS_NAMES` (so a ``road_accident`` cluster of three reports leads a one-report
``public_conflict``, both priority 8).
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

import numpy as np

from osint_common import kinds
from osint_analysis.fusion import (
    BaseCluster,
    Member,
    UnionFind,
    class_window,
    colocated,
    haversine_m,
    haversine_many,
    interval_gap,
)

__all__ = ["CORRELATE_RADIUS_M", "Situation", "clusters_colocated", "clusters_overlap", "correlate", "rank_classes",
           "related", "separation_m"]

#: The PoC's Stage-2 co-location radius between cluster representatives.
CORRELATE_RADIUS_M = 1_200.0

_CLASS_ORDER = {c: i for i, c in enumerate(kinds.EVENT_CLASS_NAMES)}


def related(a: str, b: str) -> bool:
    """Whether two different classes form a related pair."""
    return a != b and frozenset({a, b}) in kinds.RELATED_CLASSES


def clusters_colocated(a: BaseCluster, b: BaseCluster) -> bool:
    """Same-level co-location of two base clusters (see the module docstring)."""
    if a.realm != b.realm or a.scope != b.scope:
        return False
    if a.scope != "point":
        return a.area_key == b.area_key
    return colocated(a.rep, b.rep, radius_m=CORRELATE_RADIUS_M)


def separation_m(a: BaseCluster, b: BaseCluster) -> float:
    """How far apart two co-located clusters are: the distance between their representatives; 0 for two areas
    (co-located only when they are the same district or state)."""
    ra, rb = a.rep, b.rep
    if a.scope != "point" or ra.lat is None or ra.lon is None or rb.lat is None or rb.lon is None:
        return 0.0
    return haversine_m(ra.lat, ra.lon, rb.lat, rb.lon)


def clusters_overlap(a: BaseCluster, b: BaseCluster) -> bool:
    """Time overlap within the wider class window (state aggregates are timeless)."""
    if a.scope == "state" and b.scope == "state":
        return True
    window = max(class_window(a.event_class), class_window(b.event_class))
    return interval_gap(a.t0, a.t1, b.t0, b.t1) <= window


def rank_classes(members: Sequence[Member]) -> list[str]:
    """The classes of a situation, primary first: response priority, then member count, then the earliest report,
    then the canonical class order (a total, deterministic order)."""
    counts = Counter(m.event_class for m in members)
    first: dict[str, tuple[datetime, str]] = {}
    for m in sorted(members, key=lambda m: m.sort_key):
        first.setdefault(m.event_class, m.sort_key)
    last = len(_CLASS_ORDER)
    return sorted(
        counts,
        key=lambda c: (-kinds.RESPONSE_PRIORITY.get(c, 0), -counts[c], first[c], _CLASS_ORDER.get(c, last)),
    )


@dataclass(frozen=True, slots=True)
class Situation:
    """One fused situation: its base clusters and members (ordered by ``(anchor, signal_id)``) and its classes."""

    clusters: tuple[BaseCluster, ...]
    members: tuple[Member, ...]
    classes: tuple[str, ...]

    @property
    def primary_class(self) -> str:
        return self.classes[0]

    @property
    def correlated(self) -> bool:
        return len(self.classes) > 1

    @property
    def all_state_level(self) -> bool:
        """Every geocode is state-level (held as outside the city, plan R28)."""
        return all(m.scope == "state" for m in self.members)

    @property
    def sort_key(self) -> tuple[datetime, str]:
        return self.members[0].sort_key


def _candidate_pairs(ordered: Sequence[BaseCluster]) -> list[tuple[int, int]]:
    """The index pairs ``i < j`` that may join: related classes, one realm and one level, and for point clusters
    representatives within :data:`CORRELATE_RADIUS_M` (a vectorised test, a metre wider, so
    :func:`clusters_colocated` decides) or on one segment; for areas, one district or state. A superset of the
    pairs that pass :func:`clusters_colocated`, so the result is the all-pairs result, without testing all pairs."""
    groups: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    for i, c in enumerate(ordered):
        groups[(c.event_class, c.realm, c.scope)].append(i)
    reps = {i: ordered[i].rep for ids in groups.values() for i in ids if ordered[i].scope == "point"}
    out: set[tuple[int, int]] = set()
    for x, y in sorted(tuple(sorted(pair)) for pair in kinds.RELATED_CLASSES):
        for (cls, realm, scope), xs in groups.items():
            ys = groups.get((y, realm, scope)) if cls == x else None
            if not ys:
                continue
            if scope != "point":
                by_area: dict[str | None, list[int]] = defaultdict(list)
                for j in ys:
                    by_area[ordered[j].area_key].append(j)
                out.update((min(i, j), max(i, j)) for i in xs for j in by_area.get(ordered[i].area_key, ()))
                continue
            lat_x = np.array([reps[i].lat for i in xs], dtype=float)
            lon_x = np.array([reps[i].lon for i in xs], dtype=float)
            lat_y = np.array([reps[j].lat for j in ys], dtype=float)
            lon_y = np.array([reps[j].lon for j in ys], dtype=float)
            near = haversine_many(lat_x[:, None], lon_x[:, None], lat_y[None, :], lon_y[None, :])
            for a, b in zip(*np.nonzero(near <= CORRELATE_RADIUS_M + 1.0), strict=True):
                i, j = xs[int(a)], ys[int(b)]
                out.add((min(i, j), max(i, j)))
            on_segment: dict[int, list[int]] = defaultdict(list)
            for j in ys:
                if reps[j].on_segment is not None:
                    on_segment[reps[j].on_segment].append(j)
            for i in xs:
                seg = reps[i].on_segment
                for j in on_segment.get(seg, ()) if seg is not None else ():
                    if reps[i].is_line or reps[j].is_line:
                        out.add((min(i, j), max(i, j)))
    return sorted(out)


def correlate(clusters: Sequence[BaseCluster]) -> list[Situation]:
    """Join related, co-located, time-overlapping base clusters into situations: the candidate joins nearest first,
    never two clusters of one class in one situation (see the module docstring)."""
    ordered = sorted(clusters, key=lambda c: c.sort_key)
    edges: list[tuple[float, int, int]] = []
    for i, j in _candidate_pairs(ordered):
        a, b = ordered[i], ordered[j]
        if related(a.event_class, b.event_class) and clusters_colocated(a, b) and clusters_overlap(a, b):
            # to the metre: geocodes are not more precise, and a tie then goes to the earlier clusters
            edges.append((round(separation_m(a, b)), i, j))
    edges.sort()
    uf = UnionFind(len(ordered))
    classes: dict[int, frozenset[str]] = {i: frozenset({c.event_class}) for i, c in enumerate(ordered)}
    for _, i, j in edges:
        ri, rj = uf.find(i), uf.find(j)
        if ri == rj or classes[ri] & classes[rj]:
            continue  # already one situation, or it would hold two clusters of one class
        uf.union(ri, rj)
        classes[uf.find(ri)] = classes[ri] | classes[rj]
    situations: list[Situation] = []
    for group in uf.groups():
        parts = tuple(ordered[i] for i in group)
        members = tuple(sorted((m for c in parts for m in c.members), key=lambda m: m.sort_key))
        situations.append(Situation(clusters=parts, members=members, classes=tuple(rank_classes(members))))
    situations.sort(key=lambda s: s.sort_key)
    return situations
