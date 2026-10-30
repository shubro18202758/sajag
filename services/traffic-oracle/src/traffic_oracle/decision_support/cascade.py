"""The DSS-layer cascade / second-order model (C-U; net-new — the twin has no spillover field).

For each COA it answers: when this response takes carriageway away, where does the traffic go, what does that
cost the rest of the network, which neighbourhoods feel it, and does it delay the 108?

* **Reassignment (pgRouting KSP)**: the through movements of the event's road (the entry neighbour with the
  most lanes on one side, the exit neighbour with the most lanes on the other, both directions) get their
  ``k`` shortest alternatives over the directed ``corridor.road_graph`` with the event's segments removed, and
  the segments of the live closures among the subject's second-order flags (a movement's own end excepted) — the
  ``vehicles/pursuit.py`` ``pgr_*`` pattern: one parameter-bound statement, the inner graph SQL a constant (the
  excluded ids reach it only as a ``bigint[]`` cast to text, never as interpolated text).  Diverted demand
  splits over the alternatives by a logit on path cost.
* **Spillover**: the extra delay the diverted flow imposes on every alternative segment (BPR with the twin's own
  curve, ``0.55·(v/c)^4.2``), the diverted vehicles' own detour time, and the queue that backs out of the event's
  road onto its upstream neighbours (``SimNetwork.neighbors``) when it outgrows the road.  Seeded Monte-Carlo
  (demand, capacity and duration draws) gives a distribution: mean and a SAMPLED p90.
* **Per-COA event injection** (computed here, not in the twin): an advisory moves 8 % of drivers off the road
  before they reach it; a closure takes all capacity; a diversion assigns 85 % of the road's demand to the
  alternatives; without one, 40 % of the excess re-routes on its own and the rest queues; dispatch and signal
  priority act on the 108.
* **108 / ambulance delay**: a 108 dispatched to a scene whose carriageway is closed with no emergency lane
  takes the best alternative (its extra cost is the delay); emergency signal priority saves up to 60 s;
  a live 108 route (a second-order flag) across a loaded segment loses the extra travel time there.
* Of the second-order flags, only a live 108 route (the 108 delay) and a live closure with a segment (kept out
  of the reassignment) reach the cascade; protected-corridor and convoy flags are not modelled, and the dissent
  says so flag by flag.  The surrogate models none of them.
* ``neighbourhoods_touched`` are the gazetteer neighbourhoods within 1.5 km of an affected segment, nearest first;
  ``parallel_routes_loaded`` the named roads that take diverted flow.

Pure arithmetic over a :class:`CascadeNetwork`; the I/O is :class:`PgRoutingGraph` (read-only SQL), replaceable
by any :class:`GraphHelper` (the tests use a fake).
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

import numpy as np

__all__ = [
    "ADVISORY_SHARE",
    "DIVERSION_SHARE",
    "KSP_K",
    "NEIGHBOURHOOD_RADIUS_M",
    "SELF_REROUTE_SHARE",
    "CascadeNetwork",
    "CascadeOutcome",
    "GraphHelper",
    "Path",
    "PgRoutingGraph",
    "SegmentInfo",
    "hold_junction",
    "prepare_network",
    "run_cascade",
]

KSP_K = 3
ADVISORY_SHARE = 0.08
DIVERSION_SHARE = 0.85
SELF_REROUTE_SHARE = 0.40
NEIGHBOURHOOD_RADIUS_M = 1500.0
#: a segment is "loaded" when the diverted flow adds at least this share of its capacity
LOAD_THRESHOLD = 0.02
LOGIT_THETA = 3.0
VEHICLE_SPACING_M = 7.0
SIGNAL_PRIORITY_SAVING_SEC = 60.0
#: the PoC's +180 s when no alternative is known for a 108 facing a closed carriageway
BLOCKED_108_FALLBACK_SEC = 180.0
_BPR_A = 0.55
_BPR_B = 4.2
_SAT_FLOW = 1800.0

# -- SQL (read-only, parameter-bound constants; pgRouting over the 012 directed line graph) ------------------

_GRAPH_SQL = "SELECT id, source, target, cost, reverse_cost FROM corridor.road_graph"

_SQL_ADJACENCY = "SELECT sa.from_segment_id, sa.to_segment_id, sa.via_junction_id, COALESCE(j.signal_control, FALSE) AS signal_control FROM corridor.segment_adjacency sa JOIN corridor.junctions j ON j.junction_id = sa.via_junction_id WHERE sa.from_segment_id = ANY($1::bigint[]) OR sa.to_segment_id = ANY($1::bigint[]) ORDER BY sa.from_segment_id, sa.to_segment_id, sa.via_junction_id"  # noqa: E501

_SQL_SEGMENT_INFO = "SELECT rs.segment_id, rs.road_name, rs.road_class, rs.lanes, rs.speed_limit_kmh, COALESCE(rs.oneway, FALSE) AS oneway, ST_Length(rs.geom::geography) AS length_m, ST_X(ST_PointOnSurface(rs.geom)) AS lon, ST_Y(ST_PointOnSurface(rs.geom)) AS lat FROM corridor.road_segments rs WHERE rs.segment_id = ANY($1::bigint[]) ORDER BY rs.segment_id"  # noqa: E501

#: k shortest paths with the event's segments removed from the graph ($4 bigint[] reaches the inner SQL only
#: through ``::text`` of a typed array — digits, commas and braces).
_SQL_KSP = "SELECT k.path_id, k.path_seq, k.node, k.cost, k.agg_cost FROM pgr_KSP('" + _GRAPH_SQL + " WHERE NOT (source = ANY(''' || $4::bigint[]::text || '''::bigint[]) OR target = ANY(''' || $4::bigint[]::text || '''::bigint[]))', $1::bigint, $2::bigint, $3::integer, directed := true) k ORDER BY k.path_id, k.path_seq"  # noqa: E501

#: many-to-one shortest-path costs (unit ETAs, the 108's direct approach)
_SQL_PATH_COSTS = "SELECT c.start_vid, c.agg_cost FROM pgr_dijkstraCost('" + _GRAPH_SQL + "', $1::bigint[], $2::bigint, directed := true) c ORDER BY c.start_vid"  # noqa: E501

_SQL_NEAREST_SEGMENTS = "SELECT p.i, (SELECT rs.segment_id FROM corridor.road_segments rs ORDER BY rs.geom <-> ST_SetSRID(ST_MakePoint(p.lon, p.lat), 4326) LIMIT 1) AS segment_id FROM unnest($1::float8[], $2::float8[]) WITH ORDINALITY AS p(lon, lat, i) ORDER BY p.i"  # noqa: E501


@dataclass(frozen=True)
class SegmentInfo:
    segment_id: int
    road_name: str
    road_class: str
    lanes: int
    speed_kmh: float
    length_m: float
    lon: float | None = None
    lat: float | None = None
    oneway: bool = False


@dataclass(frozen=True)
class Path:
    segments: tuple[int, ...]
    cost_sec: float


class GraphHelper(Protocol):
    async def adjacency(self, segment_ids: Sequence[int]) -> list[tuple[int, int, int, bool]]: ...

    async def segments(self, segment_ids: Sequence[int]) -> dict[int, SegmentInfo]: ...

    async def k_shortest_paths(
        self, source: int, target: int, k: int, exclude: Sequence[int]
    ) -> list[Path]: ...

    async def path_costs(self, sources: Sequence[int], target: int) -> dict[int, float]: ...

    async def nearest_segments(self, points: Sequence[tuple[float, float]]) -> list[int | None]: ...


class PgRoutingGraph:
    """:class:`GraphHelper` over one connection (read-only)."""

    def __init__(self, conn: Any) -> None:
        self.conn = conn

    async def adjacency(self, segment_ids: Sequence[int]) -> list[tuple[int, int, int, bool]]:
        rows = await self.conn.fetch(_SQL_ADJACENCY, [int(s) for s in segment_ids])
        return [
            (int(r["from_segment_id"]), int(r["to_segment_id"]), int(r["via_junction_id"]), bool(r["signal_control"]))
            for r in rows
        ]

    async def segments(self, segment_ids: Sequence[int]) -> dict[int, SegmentInfo]:
        out: dict[int, SegmentInfo] = {}
        for r in await self.conn.fetch(_SQL_SEGMENT_INFO, sorted({int(s) for s in segment_ids})):
            out[int(r["segment_id"])] = SegmentInfo(
                segment_id=int(r["segment_id"]),
                road_name=str(r["road_name"] or f"segment {r['segment_id']}"),
                road_class=str(r["road_class"] or "secondary"),
                lanes=int(r["lanes"] or 2),
                speed_kmh=float(r["speed_limit_kmh"] or 50.0),
                length_m=float(r["length_m"] or 500.0),
                lon=_finite(r["lon"]),
                lat=_finite(r["lat"]),
                oneway=bool(r["oneway"]),
            )
        return out

    async def k_shortest_paths(self, source: int, target: int, k: int, exclude: Sequence[int]) -> list[Path]:
        rows = await self.conn.fetch(_SQL_KSP, int(source), int(target), int(k), [int(s) for s in exclude])
        paths: dict[int, list[Any]] = {}
        for r in rows:
            paths.setdefault(int(r["path_id"]), []).append(r)
        out: list[Path] = []
        for pid in sorted(paths):
            seq = sorted(paths[pid], key=lambda r: int(r["path_seq"]))
            out.append(Path(tuple(int(r["node"]) for r in seq), float(seq[-1]["agg_cost"])))
        return out

    async def path_costs(self, sources: Sequence[int], target: int) -> dict[int, float]:
        srcs = sorted({int(s) for s in sources if int(s) != int(target)})
        out = {int(target): 0.0} if int(target) in {int(s) for s in sources} else {}
        if not srcs:
            return out
        for r in await self.conn.fetch(_SQL_PATH_COSTS, srcs, int(target)):
            out[int(r["start_vid"])] = float(r["agg_cost"])
        return out

    async def nearest_segments(self, points: Sequence[tuple[float, float]]) -> list[int | None]:
        if not points:
            return []
        rows = await self.conn.fetch(
            _SQL_NEAREST_SEGMENTS, [float(p[0]) for p in points], [float(p[1]) for p in points]
        )
        by_i = {int(r["i"]): (int(r["segment_id"]) if r["segment_id"] is not None else None) for r in rows}
        return [by_i.get(i + 1) for i in range(len(points))]


def _finite(v: Any) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    lon1, lat1, lon2, lat2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371000.0 * math.asin(math.sqrt(h))


@dataclass(frozen=True)
class SegmentFlow:
    """Capacity, base demand and free-flow time of one segment (from the twin's network, else its lanes)."""

    capacity_veh_h: float
    demand_veh_h: float
    t0_h: float


@dataclass
class CascadeNetwork:
    """Everything the per-COA cascade needs, gathered once per DSS."""

    route: tuple[int, ...]
    road_name: str
    lanes: int
    route_length_m: float
    route_flow: SegmentFlow
    #: per direction: (alternative paths, base cost through the route) — interior segments only in ``paths``
    directions: list[tuple[list[Path], float]] = field(default_factory=list)
    flows: dict[int, SegmentFlow] = field(default_factory=dict)
    info: dict[int, SegmentInfo] = field(default_factory=dict)
    upstream: tuple[int, ...] = ()
    neighbourhoods: tuple[tuple[str, float, float], ...] = ()
    hold_junction_id: int | None = None
    #: live closures (second-order flags) the KSP alternatives were computed WITHOUT — off the route and not a
    #: through movement's own end, so a clearance would open that road to the reassignment again
    closures_excluded: tuple[int, ...] = ()
    #: ... of which these lie on one of the k alternatives the reassignment finds WITH them open (so their
    #: clearance really changes the reassignment; the others change nothing)
    closures_on_alternatives: tuple[int, ...] = ()
    notes: list[str] = field(default_factory=list)

    @property
    def has_alternatives(self) -> bool:
        return any(paths for paths, _ in self.directions)

    @property
    def alternative_road_names(self) -> list[str]:
        names: list[str] = []
        for paths, _ in self.directions:
            for p in paths:
                for s in p.segments:
                    n = self.info[s].road_name if s in self.info else None
                    if n and n != self.road_name and n not in names:
                        names.append(n)
        return names


def _flow(info: SegmentInfo | None, spec: Any, tod: float) -> SegmentFlow:
    """A segment's flow model: the twin network's spec when it has one (capacity and base demand), else the
    segment's lanes at saturation flow with demand at 60 % of capacity."""
    if spec is not None:
        cap = float(spec.capacity_veh_h)
        demand = float(spec.base_peak_demand_veh_h) * tod
        t0 = (float(spec.length_m) / 1000.0) / max(float(spec.free_flow_kmh), 5.0)
        return SegmentFlow(max(cap, 1.0), demand, t0)
    lanes = max(1, info.lanes if info else 2)
    cap = _SAT_FLOW * lanes
    length = info.length_m if info else 500.0
    speed = info.speed_kmh if info else 50.0
    return SegmentFlow(cap, 0.6 * cap * tod, (length / 1000.0) / max(speed, 5.0))


def hold_junction(adj: Iterable[tuple[int, int, int, bool]], route: Sequence[int]) -> int | None:
    """The junction a signal hold (or an ICCC check) on the route targets: a signalised junction at its ends,
    else any junction there (lowest id: deterministic)."""
    route_set = {int(s) for s in route}
    rows = [r for r in adj if r[0] in route_set or r[1] in route_set]
    signalised = sorted({via for _, _, via, sig in rows if sig})
    if signalised:
        return signalised[0]
    any_via = sorted({via for _, _, via, _ in rows})
    return any_via[0] if any_via else None


async def prepare_network(
    graph: GraphHelper,
    route: Sequence[int],
    *,
    network: Any,
    tod: float,
    neighbourhoods: Iterable[tuple[str, float, float]] = (),
    k: int = KSP_K,
    closed_segments: Iterable[int] = (),
) -> CascadeNetwork:
    """Read the route's neighbourhood of the graph once: through movements, their KSP alternatives (route
    excluded, and every live closure in ``closed_segments`` that is not the movement's own end), segment flows
    and the junction a signal hold would use."""
    route = tuple(int(s) for s in route)
    if not route:
        raise ValueError("the cascade needs a road route")
    closed = {int(s) for s in closed_segments} - set(route)
    adj = await graph.adjacency(route)
    route_set = set(route)
    first, last = route[0], route[-1]
    entries = [(f, via, sig) for f, t, via, sig in adj if t == first and f not in route_set]
    exits = [(t, via, sig) for f, t, via, sig in adj if f == last and t not in route_set]
    if len(route) == 1 and entries and exits:
        # one segment: the two ends are its two via junctions — a through movement crosses from one to the other
        sides = sorted({via for _, via, _ in entries} | {via for _, via, _ in exits})
        if len(sides) >= 2:
            a, b = sides[0], sides[-1]
            entries = [e for e in entries if e[1] == a]
            exits = [x for x in exits if x[1] == b]
    hold = hold_junction(adj, route)

    candidates = {s for s, _, _ in entries} | {s for s, _, _ in exits}
    info = await graph.segments(sorted(route_set | candidates))

    def lanes_of(s: int) -> int:
        i = info.get(s)
        return i.lanes if i else 0

    src = max((s for s, _, _ in entries), key=lambda s: (lanes_of(s), -s), default=None)
    dst = max((s for s, _, _ in exits), key=lambda s: (lanes_of(s), -s), default=None)
    directions_raw: list[tuple[int, int]] = []
    if src is not None and dst is not None and src != dst:
        directions_raw = [(src, dst), (dst, src)]
    directions: list[tuple[list[Path], float]] = []
    seen: set[int] = set(route_set)
    excluded_closures: set[int] = set()
    on_alternatives: set[int] = set()
    for s, t in directions_raw:
        off = closed - {s, t}  # a movement's own end stays in its graph
        excluded_closures |= off
        paths = await graph.k_shortest_paths(s, t, k, sorted(route_set | off))
        if off:
            # which closures matter: the alternatives the reassignment would use with them open
            open_paths = await graph.k_shortest_paths(s, t, k, sorted(route_set))
            on_alternatives |= {x for p in open_paths for x in p.segments} & off
        base = (await graph.path_costs([s], t)).get(s)
        if not paths:
            continue
        interior = [
            Path(tuple(x for x in p.segments if x not in (s, t)), p.cost_sec) for p in paths if p.segments
        ]
        directions.append((interior, float(base) if base is not None else min(p.cost_sec for p in paths)))
        for p in interior:
            seen.update(p.segments)
    upstream_set = {s for s, _, _ in entries}
    if network is not None:
        # spillover reaches the road's neighbours in the twin's network (SimNetwork.neighbors)
        upstream_set |= set(network.neighbors(first))
    upstream = tuple(sorted(upstream_set - route_set))
    more = await graph.segments(sorted((seen | set(upstream)) - set(info)))
    info.update(more)
    flows = {sid: _flow(info.get(sid), network.get(sid) if network else None, tod) for sid in seen | set(upstream)}
    route_specs = [network.get(s) if network else None for s in route]
    lanes = min((i.lanes for s in route if (i := info.get(s))), default=2)
    if route_specs and all(r is not None for r in route_specs):
        lanes = min(int(r.lanes) for r in route_specs)
    length = sum((info[s].length_m if s in info else 500.0) for s in route)
    route_flow = flows.get(first) or _flow(info.get(first), network.get(first) if network else None, tod)
    road_name = info[first].road_name if first in info else f"segment {first}"
    net = CascadeNetwork(
        route=route,
        road_name=road_name.split(" (")[0] if road_name else road_name,
        lanes=max(1, lanes),
        route_length_m=length,
        route_flow=route_flow,
        directions=directions,
        flows=flows,
        info=info,
        upstream=upstream,
        neighbourhoods=tuple(neighbourhoods),
        hold_junction_id=hold,
        closures_excluded=tuple(sorted(excluded_closures)),
        closures_on_alternatives=tuple(sorted(on_alternatives)),
    )
    if not directions:
        net.notes.append("no through movement with an alternative was found: no reassignment")
    if excluded_closures:
        net.notes.append(f"live closures kept out of the reassignment: segments {sorted(excluded_closures)}")
    return net


@dataclass(frozen=True)
class CascadeOutcome:
    spillover_mean: float
    spillover_p90: float
    neighbourhoods_touched: tuple[str, ...]
    parallel_routes_loaded: tuple[str, ...]
    affected_segment_ids: tuple[int, ...]
    ambulance_delay_sec: float
    metrics: dict[str, Any]

    def cascade_doc(self) -> dict[str, Any]:
        return {
            "spillover_vehicle_hours": {"mean": round(self.spillover_mean, 1), "p90": round(self.spillover_p90, 1)},
            "neighbourhoods_touched": list(self.neighbourhoods_touched),
            "parallel_routes_loaded": list(self.parallel_routes_loaded),
            "affected_segment_ids": list(self.affected_segment_ids),
        }


def _bpr_h(flow: SegmentFlow, v: float) -> float:
    return flow.t0_h * (1.0 + _BPR_A * (max(v, 0.0) / flow.capacity_veh_h) ** _BPR_B)


def _shares(paths: Sequence[Path]) -> list[float]:
    if not paths:
        return []
    cmin = max(min(p.cost_sec for p in paths), 1.0)
    weights = [math.exp(-LOGIT_THETA * (p.cost_sec - cmin) / cmin) for p in paths]
    total = sum(weights)
    return [w / total for w in weights]


def run_cascade(
    net: CascadeNetwork,
    *,
    lanes_blocked: int,
    capacity_factor: float,
    active_min: float,
    advisory: bool,
    closure: bool,
    diversion: bool,
    emergency_lane: bool,
    dispatch_108: bool,
    signal_priority: bool,
    ambulance_eta_sec: float | None,
    seed: int,
    index: int,
    reps: int = 240,
    live_108_segments: Iterable[int] = (),
) -> CascadeOutcome:
    """The cascade of one COA (see the module docstring)."""
    lanes = max(1, net.lanes)
    lb = min(max(0, int(lanes_blocked)), lanes)
    open_frac = 0.0 if closure else (lanes - lb) / lanes
    cap = net.route_flow.capacity_veh_h * open_frac * capacity_factor
    lam = net.route_flow.demand_veh_h
    adv = ADVISORY_SHARE if advisory else 0.0
    sig_dur = 0.10 + 0.05 * (lb * 3.0 / lanes) + (0.06 if closure else 0.0)
    rng = np.random.default_rng(int(seed) + int(index) * 7919 + 104729)

    # per alternative segment: summed logit share per unit of diverted flow
    per_seg: dict[int, float] = {}
    detour_cost = 0.0  # mean extra seconds per diverted vehicle
    ndir = len(net.directions)
    for paths, base in net.directions:
        shares = _shares(paths)
        for p, sh in zip(paths, shares, strict=True):
            for s in p.segments:
                per_seg[s] = per_seg.get(s, 0.0) + sh / ndir
            detour_cost += sh * max(0.0, p.cost_sec - base) / ndir

    spill = np.empty(reps)
    assigned = np.empty(reps)
    queue_len = np.empty(reps)
    for r in range(reps):
        demand = lam * rng.normal(1.0, 0.08)
        dur = max(0.05, active_min / 60.0 * rng.lognormal(0.0, sig_dur))
        c = max(0.0, cap * rng.normal(1.0, 0.06))
        residual = demand * (1.0 - adv)
        excess = max(0.0, residual - c)
        if not net.has_alternatives:
            # nowhere to go: the advised drivers stay off the road, the excess queues
            a, q = 0.0, excess
        elif diversion:
            a = demand * adv + DIVERSION_SHARE * residual
            q = max(0.0, residual * (1.0 - DIVERSION_SHARE) - c)
        else:
            rerouted = SELF_REROUTE_SHARE * excess
            a, q = demand * adv + rerouted, excess - rerouted
        alt_vh = 0.0
        for s, share in per_seg.items():
            f = net.flows.get(s)
            if f is None:
                continue
            x = a * share
            alt_vh += ((f.demand_veh_h + x) * _bpr_h(f, f.demand_veh_h + x) - f.demand_veh_h * _bpr_h(
                f, f.demand_veh_h) - x * f.t0_h) * dur
        detour_vh = a * dur * detour_cost / 3600.0
        # the queue on the event's road; what does not fit backs out onto its upstream neighbours
        queued_veh = q * dur
        length_q = queued_veh * VEHICLE_SPACING_M / lanes
        back_vh = 0.0
        if length_q > net.route_length_m and net.upstream:
            spilled = (length_q - net.route_length_m) * lanes / VEHICLE_SPACING_M
            back_vh = spilled * dur / 2.0
        spill[r] = max(0.0, alt_vh) + detour_vh + back_vh
        assigned[r] = a
        queue_len[r] = length_q

    a_mean = float(assigned.mean())
    loaded: list[tuple[float, int]] = []
    for s, share in per_seg.items():
        f = net.flows.get(s)
        if f is not None and a_mean * share / f.capacity_veh_h >= LOAD_THRESHOLD:
            loaded.append((a_mean * share / f.capacity_veh_h, s))
    loaded.sort(key=lambda t: (-t[0], t[1]))
    capacity_lost = closure or lb > 0 or float(np.mean(queue_len)) > 0.0
    affected: list[int] = list(net.route) if capacity_lost else []
    affected += [s for _, s in loaded if s not in affected]
    spilled_back = float(np.mean(queue_len)) > net.route_length_m
    if spilled_back:
        affected += [s for s in net.upstream if s not in affected]

    routes: list[str] = []
    for _, s in loaded:
        name = net.info[s].road_name if s in net.info else None
        if name and name.split(" (")[0] != net.road_name and name not in routes:
            routes.append(name)

    points: list[tuple[float, float]] = []
    for s in affected:
        i = net.info.get(s)
        if i is not None and i.lon is not None and i.lat is not None:
            points.append((i.lon, i.lat))
    scene = net.info.get(net.route[0])
    scene_pt = (scene.lon, scene.lat) if scene is not None and scene.lon is not None else None
    touched: list[tuple[float, float, str]] = []
    for name, lon, lat in net.neighbourhoods:
        if not points:
            break
        d = min(haversine_m((lon, lat), p) for p in points)
        if d <= NEIGHBOURHOOD_RADIUS_M:
            # nearest an affected segment first; a tie goes to the one nearer the scene
            touched.append((round(d, -1), haversine_m((lon, lat), scene_pt) if scene_pt else 0.0, name))
    touched.sort()

    # the 108
    delay = 0.0
    if dispatch_108:
        if closure and not emergency_lane:
            best = None
            for paths, base in net.directions:
                for p in paths:
                    extra = max(0.0, p.cost_sec - base)
                    best = extra if best is None else min(best, extra)
            delay = max(30.0, best) if best is not None else BLOCKED_108_FALLBACK_SEC
        elif signal_priority:
            eta = ambulance_eta_sec or 480.0
            delay = -min(SIGNAL_PRIORITY_SAVING_SEC, 0.125 * eta)
    live = {int(s) for s in live_108_segments}
    for s in live & set(affected):
        if s in net.route and closure:
            delay += BLOCKED_108_FALLBACK_SEC
            continue
        f = net.flows.get(s)
        if f is not None and s in per_seg:
            x = a_mean * per_seg[s]
            delay += (_bpr_h(f, f.demand_veh_h + x) - _bpr_h(f, f.demand_veh_h)) * 3600.0

    return CascadeOutcome(
        spillover_mean=float(spill.mean()),
        spillover_p90=float(np.percentile(spill, 90)),
        neighbourhoods_touched=tuple(n for _, _, n in touched),
        parallel_routes_loaded=tuple(routes[:16]),
        affected_segment_ids=tuple(affected[:512]),
        ambulance_delay_sec=round(delay, 1),
        metrics={
            "replications": reps,
            "assigned_veh_h_mean": round(a_mean, 1),
            "queue_length_m_mean": round(float(np.mean(queue_len)), 1),
            "spilled_back": spilled_back,
            "alternatives": sum(len(p) for p, _ in net.directions),
            "route": list(net.route),
        },
    )


def neighbourhoods_near(
    entries: Iterable[Mapping[str, Any]], point: tuple[float, float] | None, *, limit: int = 3, radius_m: float = 3000.0
) -> list[str]:
    """Gazetteer neighbourhoods nearest a point (the surrogate's ``neighbours`` list)."""
    if point is None:
        return []
    found: list[tuple[float, str]] = []
    for e in entries:
        d = haversine_m(point, (float(e["lon"]), float(e["lat"])))
        if d <= radius_m:
            found.append((d, str(e["canonical_name"])))
    found.sort()
    return [n for _, n in found[:limit]]
