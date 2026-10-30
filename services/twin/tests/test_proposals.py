"""Candidate programs, ranking guards and the proposal object."""

from __future__ import annotations

from datetime import datetime

import pytest

from conftest import crossroad_network, line_network
from sajag_twin import params as P
from sajag_twin.demand import IST, Forecast
from sajag_twin.network import Program, network_from_dict
from sajag_twin.proposals import corridor_path, eligibility, rank, run_proposals
from sajag_twin.signals import extend_green, green_start, green_wave_offsets
from sajag_twin.twin import Twin

EVENING = datetime(2026, 10, 28, 18, 0, tzinfo=IST)


def delta(focus=-10.0, net=-1.0, cross=5.0, queue_pct=-5.0, spill=0.0):
    return {
        "delay_change_pct": focus, "network_delay_change_pct": net, "cross_street_delay_change_pct": cross,
        "max_queue_change_pct": queue_pct, "max_queue_change_m": 0.0, "network_spillback_change_min": spill,
    }


def test_extend_green_keeps_cycle_offset_and_floor():
    p = Program(110, 94, ((50, ("through",)), (42, ("cross",))))
    q = extend_green(p, "through", 10)
    assert q.cycle_sec == 110 and q.offset_sec == 94
    assert [g for g, _ in q.phases] == [60, 32]
    r = extend_green(p, "cross", 40)  # through can only give down to the floor
    assert [g for g, _ in r.phases] == [P.MIN_GREEN_S, 42 + 50 - P.MIN_GREEN_S]
    floor = Program(110, 0, ((P.MIN_GREEN_S, ("through",)), (77, ("cross",))))
    assert extend_green(floor, "cross", 10) is None
    assert extend_green(p, "left", 10) is None


def test_guards_reject_moving_the_jam():
    assert eligibility(delta(), 25.0) == []
    assert "raises network delay" in eligibility(delta(focus=-30, net=0.5), 25.0)[0]
    assert any("cross-street" in w for w in eligibility(delta(cross=40.0), 25.0))
    assert any("spill-back" in w for w in eligibility(delta(spill=2.0), 25.0))
    assert any("less than" in w for w in eligibility(delta(focus=-1.0), 25.0))


def test_rank_puts_eligible_first_then_score():
    ds = [
        delta(focus=-40.0, net=+0.3),  # big local gain but moves the jam
        delta(focus=-8.0, net=-0.5, queue_pct=-10.0),
        delta(focus=-12.0, net=-1.0, queue_pct=-5.0),
        delta(focus=-20.0, cross=60.0),  # starves the cross street
    ]
    order = rank(ds, 25.0)
    assert [i for i, _, _ in order][:2] == [2, 1]
    assert all(why for i, _, why in order if i in (0, 3))


def test_green_wave_offsets_follow_travel_time():
    progs = {str(j): {"cycle_sec": 100, "offset_sec": 7 * j,
                      "phases": [{"green_sec": 45, "movements": ["through"]}, {"green_sec": 37, "movements": ["cross"]}]}
             for j in (2, 3, 4)}
    net = network_from_dict(line_network(lengths=(500.0, 600.0, 900.0, 500.0), lanes=(2, 2, 2, 2), oneway=True,
                                         programs=progs, names={2: "A crossing", 3: "B crossing", 4: "C crossing"}))
    js, links = corridor_path(net, segment_ids=[1001, 1002, 1003, 1004])
    assert js == [1, 2, 3, 4, 5]
    programs = {j: net.junctions[j].program for j in (2, 3, 4)}
    out = green_wave_offsets(net, js, programs, speed_kmh=36.0)  # 10 m/s
    assert out[2].offset_sec == 14
    assert (out[3].offset_sec - out[2].offset_sec) % 100 == 60  # 600 m at 10 m/s
    assert (out[4].offset_sec - out[3].offset_sec) % 100 == 90
    assert all(green_start(p, "through") == 0 for p in out.values())
    assert [g for g, _ in out[3].phases] == [45, 37]  # greens unchanged


def test_proposal_object_for_a_loaded_main_road():
    tw = Twin(network_from_dict(crossroad_network()))
    # the main road (east-west) will run at v/c 1.05 in 10 minutes
    j = tw.net.junctions[5]
    ew = [tw.net.links[i].segment_id for i, lab in j.approach_label.items() if lab == "through"]
    fc = Forecast(vc=1.05, in_min=10, junction_id=5, segment_ids=tuple(ew), source="test forecast")
    dem = tw.build_demand(EVENING, 45, mode="simulated", forecasts=[fc])
    sc = tw.scenario(dem, 45)
    out = run_proposals(tw, sc, junction_ids=[5], corridor=None, horizon_min=45)
    assert out["candidates_evaluated"] >= 10
    kinds = {r["kind"] for r in out["ranked"]}
    assert {"extend_green", "max_pressure", "webster_retime"} <= kinds
    p = out["proposal"]
    assert p is not None, out["ranked"][:3]
    assert p["verification_state"] == "MODELLED"
    assert p["requires"] == "named officer approval" and p["requires_officer"] is True
    assert p["status"] == "PROPOSED" and p["if_no_decision"] == "the current plan holds"
    assert p["targets"] == ["junction:5"]
    m = p["twin_metrics"]
    assert m["delay_change_pct"] <= -P.MIN_GAIN_PCT
    assert m["network_delay_change_pct"] <= 0.0
    assert m["cross_street_delay_change_pct"] <= 25.0
    assert p["kind"] in ("extend_green", "max_pressure", "webster_retime")
    if p["kind"] == "extend_green":
        assert p["change"]["movement"] == "through"
        prog = p["change"]["programs"]["5"]
        assert prog["cycle_sec"] == 90 and prog["offset_sec"] == 0  # extend green keeps cycle and offset
    assert p["change"]["revert_to"]["5"]["phases"][0]["green_sec"] == 36
    assert 0.0 < p["confidence"]["score"] <= 1.0
    assert p["demand"]["label"] == "SIMULATED"
    assert any("SIMULATED" in a for a in p["assumptions"])
    # the ranked list shows every candidate, eligible ones first
    flags = [r["eligible"] for r in out["ranked"]]
    assert flags == sorted(flags, reverse=True)


def test_hold_when_nothing_helps():
    # a symmetric crossing (same road both ways) at 03:00, no directional peak, already on
    # Webster's timing for its demand: any shift of green hurts one road more than it helps the other
    at = datetime(2026, 10, 28, 3, 0, tzinfo=IST)
    probe = Twin(network_from_dict(crossroad_network(cross_class="primary", cross_lanes=4)))
    best = probe.webster_for(probe.build_demand(at, 30, mode="simulated"), 5).program
    doc = crossroad_network(cross_class="primary", cross_lanes=4, program={k: v for k, v in best.to_dict().items() if k != "source"})
    tw = Twin(network_from_dict(doc))
    sc = tw.scenario(tw.build_demand(at, 30, mode="simulated"), 30)
    out = run_proposals(tw, sc, junction_ids=[5], corridor=None, horizon_min=30)
    assert "webster_retime" not in {r["kind"] for r in out["ranked"]}  # already on Webster's timing
    assert out["proposal"] is None, out["ranked"][:2]
    assert out["recommendation"].startswith("hold")
    assert all(r["not_eligible_because"] for r in out["ranked"])


def test_corridor_path_rejects_a_broken_path():
    net = network_from_dict(line_network(lengths=(500.0, 600.0), oneway=True))
    with pytest.raises(ValueError):
        corridor_path(net, segment_ids=[1002, 1001])
