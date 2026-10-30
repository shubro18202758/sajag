"""The DSS-layer cascade model (C-U; net-new — the twin has no spillover field).

* spillover over the road's neighbours (``SimNetwork.neighbors``): a closure's queue backs out onto them;
* the pgRouting KSP reassignment, through a FAKE graph helper: the route is excluded, the diverted flow loads the
  alternatives, their named roads are the ``parallel_routes_loaded``; a live closure (a second-order flag) is
  kept out of the alternatives, a through movement's own end excepted;
* the 108 / ambulance delay: a closed carriageway with no emergency lane costs the 108 the detour; signal priority
  saves time; a live 108 route across a loaded segment is delayed;
* the twin departs at the generation's time (not the wall clock), and each COA's method names only what it has;
* the read-only SQL keeps the excluded ids out of the statement text, and the real ``PgRoutingGraph`` runs over
  the recording fake connection (int3c's graph around segment 1045).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest

from fixtures.dss.fakedss import ROAD_SEGMENTS, FakeDssConn, FakeDssDB
from traffic_oracle.decision_support import cascade, coa, wargame
from traffic_oracle.decision_support.cascade import Path, SegmentInfo
from traffic_oracle.simulation.network import SegmentSpec, SimNetwork

HOODS = (("Near Hood", 88.447, 22.578), ("Alt Hood", 88.416, 22.560), ("Far Hood", 88.210, 22.460))


def _network() -> SimNetwork:
    """A five-segment toy: route 1 (A–B), entry 2 at A, exit 3 at B, an alternative 4–5 from 2 to 3."""
    net = SimNetwork()
    for sid, lanes, length in ((1, 2, 400.0), (2, 2, 800.0), (3, 2, 800.0), (4, 2, 900.0), (5, 2, 900.0)):
        net.segments[sid] = SegmentSpec(segment_id=sid, road_name=f"Road {sid}", road_class="secondary",
                                        lanes=lanes, speed_limit_kmh=40, oneway=False, length_m=length)
    for a, b in ((1, 2), (1, 3), (2, 4), (4, 5), (5, 3)):
        net.adjacency.setdefault(a, set()).add(b)
        net.adjacency.setdefault(b, set()).add(a)
    return net


@dataclass
class FakeGraph:
    """A :class:`cascade.GraphHelper` over the toy network, recording its calls."""

    calls: list[tuple] = field(default_factory=list)
    alternatives: bool = True

    async def adjacency(self, ids):
        self.calls.append(("adjacency", tuple(ids)))
        return [(2, 1, 100, True), (1, 3, 200, False), (3, 1, 200, False), (1, 2, 100, True)]

    async def segments(self, ids):
        self.calls.append(("segments", tuple(sorted(ids))))
        pts = {1: (88.447, 22.578), 2: (88.451, 22.590), 3: (88.446, 22.565), 4: (88.416, 22.560), 5: (88.421, 22.565)}
        names = {1: "Main Road (Scene)", 2: "Main Road (North)", 3: "Main Road (South)", 4: "Bypass West",
                 5: "Bypass South"}
        return {s: SegmentInfo(s, names[s], "secondary", 2, 40.0, 800.0, *pts[s]) for s in ids if s in pts}

    async def k_shortest_paths(self, source, target, k, exclude):
        self.calls.append(("ksp", source, target, k, tuple(exclude)))
        if not self.alternatives:
            return []
        assert 1 in exclude  # the route is removed from the graph
        if (source, target) == (2, 3):
            return [Path((2, 4, 5, 3), 300.0)]
        return [Path((3, 5, 4, 2), 310.0)]

    async def path_costs(self, sources, target):
        self.calls.append(("costs", tuple(sources), target))
        return {s: 120.0 for s in sources}

    async def nearest_segments(self, points):
        return [1 for _ in points]


async def _net(alternatives: bool = True, tod: float = 1.0) -> tuple[cascade.CascadeNetwork, FakeGraph]:
    graph = FakeGraph(alternatives=alternatives)
    net = await cascade.prepare_network(graph, [1], network=_network(), tod=tod, neighbourhoods=HOODS)
    return net, graph


def _run(net, **kw):
    args = dict(lanes_blocked=0, capacity_factor=1.0, active_min=45, advisory=False, closure=False,
                diversion=False, emergency_lane=True, dispatch_108=False, signal_priority=False,
                ambulance_eta_sec=300.0, seed=20261024, index=0)
    args.update(kw)
    return cascade.run_cascade(net, **args)


async def test_ksp_reassignment_through_a_fake_graph_helper():
    net, graph = await _net()
    ksp = [c for c in graph.calls if c[0] == "ksp"]
    assert {(c[1], c[2]) for c in ksp} == {(2, 3), (3, 2)}  # both directions of the through movement
    assert all(c[3] == cascade.KSP_K and c[4] == (1,) for c in ksp)
    assert net.has_alternatives
    assert net.hold_junction_id == 100  # the signalised end
    out = _run(net, lanes_blocked=2, closure=True, diversion=True, capacity_factor=0.4, advisory=True,
               emergency_lane=False)
    assert out.spillover_mean > 0 and out.spillover_p90 >= out.spillover_mean
    assert set(out.parallel_routes_loaded) == {"Bypass West", "Bypass South"}
    assert {4, 5} <= set(out.affected_segment_ids) and 1 in out.affected_segment_ids
    assert out.metrics["assigned_veh_h_mean"] > 0


async def test_spillover_over_the_neighbours_when_the_queue_outgrows_the_road():
    net, _ = await _net(alternatives=False)
    assert not net.has_alternatives
    assert set(net.upstream) >= {2, 3}  # the road's SimNetwork neighbours
    out = _run(net, lanes_blocked=2, closure=True, capacity_factor=0.4, emergency_lane=False)
    assert out.metrics["spilled_back"] is True
    assert {2, 3} <= set(out.affected_segment_ids)
    assert out.spillover_mean > 0
    assert out.parallel_routes_loaded == ()  # nowhere to divert to


async def test_no_capacity_loss_no_cascade():
    net, _ = await _net()
    out = _run(net)
    assert out.spillover_mean == 0.0 and out.affected_segment_ids == () and out.neighbourhoods_touched == ()
    assert out.ambulance_delay_sec == 0.0


async def test_neighbourhoods_are_the_gazetteer_ones_near_affected_segments():
    net, _ = await _net()
    out = _run(net, lanes_blocked=2, closure=True, diversion=True, emergency_lane=False)
    assert out.neighbourhoods_touched[0] == "Near Hood"
    assert "Alt Hood" in out.neighbourhoods_touched  # the bypass passes by it
    assert "Far Hood" not in out.neighbourhoods_touched


async def test_ambulance_delay():
    net, _ = await _net()
    blocked = _run(net, lanes_blocked=2, closure=True, diversion=True, emergency_lane=False, dispatch_108=True)
    # the detour: the best alternative (300 s) minus the direct path (120 s)
    assert blocked.ambulance_delay_sec == pytest.approx(180.0)
    priority = _run(net, lanes_blocked=1, signal_priority=True, dispatch_108=True, ambulance_eta_sec=480.0)
    assert priority.ambulance_delay_sec == pytest.approx(-60.0)
    short = _run(net, signal_priority=True, dispatch_108=True, ambulance_eta_sec=200.0)
    assert short.ambulance_delay_sec == pytest.approx(-25.0)
    none = _run(net, lanes_blocked=2, closure=True, diversion=True, emergency_lane=False, dispatch_108=False)
    assert none.ambulance_delay_sec == 0.0
    # a live 108 route over a loaded bypass segment is delayed too
    live = _run(net, lanes_blocked=2, closure=True, diversion=True, emergency_lane=False, live_108_segments=[4])
    assert live.ambulance_delay_sec > 0


async def test_no_alternative_known_falls_back_to_the_blocked_108_constant():
    net, _ = await _net(alternatives=False)
    out = _run(net, lanes_blocked=2, closure=True, emergency_lane=False, dispatch_108=True)
    assert out.ambulance_delay_sec == cascade.BLOCKED_108_FALLBACK_SEC


async def test_the_cascade_is_seeded():
    net, _ = await _net()
    a = _run(net, lanes_blocked=1, capacity_factor=0.5, seed=5)
    b = _run(net, lanes_blocked=1, capacity_factor=0.5, seed=5)
    c = _run(net, lanes_blocked=1, capacity_factor=0.5, seed=6)
    assert a == b
    assert (a.spillover_mean, a.spillover_p90) != (c.spillover_mean, c.spillover_p90)


async def test_an_advisory_moves_drivers_off_the_road():
    net, _ = await _net()
    quiet = _run(net, advisory=False)
    advised = _run(net, advisory=True)
    assert quiet.metrics["assigned_veh_h_mean"] == 0
    assert advised.metrics["assigned_veh_h_mean"] > 0


async def test_a_live_closure_is_kept_out_of_the_reassignment():
    """A live closure among the second-order flags is removed from the KSP graph (so a cleared closure really
    gives the reassignment that road back); a movement's own end and the route itself are never 'excluded'."""
    graph = FakeGraph()
    net = await cascade.prepare_network(graph, [1], network=_network(), tod=1.0, neighbourhoods=HOODS,
                                        closed_segments=[4, 1])
    ksp = [c for c in graph.calls if c[0] == "ksp"]
    # per direction: the alternatives without the closure, then (to see whether it matters) with it open
    assert [c[4] for c in ksp] == [(1, 4), (1,), (1, 4), (1,)]
    assert net.closures_excluded == (4,)
    assert net.closures_on_alternatives == (4,)  # the bypass 2–4–5–3 runs over it
    assert any("live closures kept out of the reassignment" in n for n in net.notes)
    off_path = FakeGraph()
    elsewhere = await cascade.prepare_network(off_path, [1], network=_network(), tod=1.0, closed_segments=[99])
    assert elsewhere.closures_excluded == (99,) and elsewhere.closures_on_alternatives == ()
    end = FakeGraph()
    at_end = await cascade.prepare_network(end, [1], network=_network(), tod=1.0, closed_segments=[2])
    assert all(c[4] == (1,) for c in end.calls if c[0] == "ksp")  # 2 is the through movement's own end
    assert at_end.closures_excluded == ()
    plain, _ = await _net()
    assert plain.closures_excluded == ()


async def test_a_live_closure_on_the_only_alternative_leaves_no_reassignment():
    """Over the fake's graph every alternative to segment 1045 runs through 1047 (Major Arterial Road):
    with a live closure there the cascade has no road to reassign to."""
    conn = FakeDssConn(FakeDssDB())
    graph = cascade.PgRoutingGraph(conn)
    net = await cascade.prepare_network(graph, [1045], network=None, tod=1.0, closed_segments=[1047])
    assert net.closures_excluded == (1047,) and net.closures_on_alternatives == (1047,)
    assert not net.has_alternatives
    out = _run(net, lanes_blocked=8, closure=True, diversion=True, emergency_lane=False, capacity_factor=0.4)
    assert out.parallel_routes_loaded == ()


def test_the_ksp_sql_never_interpolates_the_excluded_ids():
    sql = cascade._SQL_KSP
    assert "$4::bigint[]::text" in sql and "pgr_KSP(" in sql and "directed := true" in sql
    assert "{" not in sql and "%" not in sql
    assert "corridor.road_graph" in sql
    assert cascade._SQL_PATH_COSTS.count("$") == 2


async def test_pgrouting_graph_over_the_sector_v_graph():
    """The real ``PgRoutingGraph`` over the recording fake (int3c's graph around segment 1045)."""
    conn = FakeDssConn(FakeDssDB())
    graph = cascade.PgRoutingGraph(conn)
    net = await cascade.prepare_network(graph, [1045], network=None, tod=1.0, neighbourhoods=(
        ("Narkelbagan", 88.4469, 22.5691), ("Rajarhat", 88.463, 22.600), ("Kestopur", 88.416, 22.603)))
    assert net.hold_junction_id == 9  # the fake's signalised junction
    assert net.has_alternatives
    names = net.alternative_road_names
    assert "Kestopur Road" in names and "Major Arterial Road (New Town)" in names
    # only the detour roads: never the route's own road (1045) nor its entry / exit legs (1016, 1040)
    assert not {ROAD_SEGMENTS[s][0] for s in (1016, 1040, 1045)} & set(names)
    assert cascade._SQL_KSP in conn.calls
    out = _run(net, lanes_blocked=8, closure=True, diversion=True, emergency_lane=False, dispatch_108=True,
               capacity_factor=0.4, advisory=True)
    assert out.ambulance_delay_sec > 0
    assert "Narkelbagan" in out.neighbourhoods_touched


def _drafts():
    anchors = coa.Anchors(segment_id=1045, junction_id=None, route_segment_ids=(1045,), hold_junction_id=28)
    return {d.kind: d for d in coa.build_coas(event_class="road_accident", anchors=anchors, injuries=True)}


async def test_the_twin_departs_at_the_generations_time(monkeypatch):
    """``twin_disruption`` gives the twin the generation's ``now`` as its departure, so the twin's time of day
    matches the surrogate's and a given subject, time and seed reproduce."""
    from traffic_oracle.simulation import router as sim_router

    seen: list = []

    async def fake_simulate_twin(req, request):
        seen.append(req.departure_time)
        return {"runs": [{"total_disruption_vehicle_hours": 1.5, "avg_closure_duration_sec": 240.0,
                          "ambulance_delay_sec": 0.0}]}

    monkeypatch.setattr(sim_router, "simulate_twin", fake_simulate_twin)
    at = datetime(2026, 10, 24, 3, 30, tzinfo=UTC)
    out = await wargame.twin_disruption(None, [1045], _drafts()["aggressive"], seed=7, horizon_min=45, now=at)
    assert seen == [at]
    assert out["replications"] == 1 and out["mean"] == pytest.approx(1.5 * (50 * 60 / 240.0) ** 2)


def test_the_surrogate_method_names_only_what_the_coa_has():
    """Ethics rule 7: the baseline has no lane loss, advisory, dispatch or signal priority, and says so."""
    d = _drafts()
    assert wargame._why_surrogate(d["baseline"], 3) == (
        "no closure or diversion, so there is nothing for the twin to run")
    assert wargame._why_surrogate(d["minimal"], 3).endswith("the twin cannot express this COA's advisory")
    assert wargame._why_surrogate(d["standard"], 3).endswith(
        "this COA's lane loss, advisory, dispatch and signal priority")
    assert wargame._why_surrogate(d["information"], 3).endswith("this COA's dispatch")
