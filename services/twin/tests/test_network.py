"""Loading the City Pack network, control classes, and the read-only live-state reader."""

from __future__ import annotations

from datetime import datetime

import httpx
import pytest

from conftest import crossroad_network, kolkata_network_path, line_network, mumbai_network_path
from sajag_twin.demand import IST
from sajag_twin.network import NetworkError, load_network, network_from_dict, through_legs, Leg
from sajag_twin.oracle_client import OracleClient
from sajag_twin.twin import Twin


def test_directed_links_and_lanes_per_direction():
    two_way = network_from_dict(line_network(lengths=(500.0,), lanes=(4,), oneway=False))
    assert [l.link_id for l in two_way.links] == ["1001:f", "1001:r"]
    assert all(l.lanes == 2 for l in two_way.links)  # lanes count both directions
    one_way = network_from_dict(line_network(lengths=(500.0,), lanes=(3,), oneway=True))
    assert [(l.link_id, l.lanes) for l in one_way.links] == [("1001:f", 3)]


def test_control_classes_and_virtual_cross_street():
    prog = {"cycle_sec": 110, "offset_sec": 94,
            "phases": [{"green_sec": 50, "movements": ["through"]}, {"green_sec": 42, "movements": ["cross"]}]}
    net = network_from_dict(line_network(lengths=(500.0, 500.0, 500.0), lanes=(2, 2, 2), programs={"2": prog},
                                         names={3: "Plain crossing"}))
    assert net.junctions[1].control == "boundary"
    assert net.junctions[2].control == "programmed" and net.junctions[2].program.offset_sec == 94
    # a node named a crossing with no program gets the template and says so
    j3 = net.junctions[3]
    assert j3.control == "assumed" and "assumed" in j3.program.source
    assert [g for g, _ in j3.program.phases] == [50, 42] and j3.program.cycle_sec == 110
    # neither has its cross road in this network: a virtual cross street serves "cross"
    assert net.junctions[2].virtual_cross and j3.virtual_cross
    cross = network_from_dict(crossroad_network())
    assert not cross.junctions[5].virtual_cross
    assert sorted(cross.junctions[5].approach_label.values()) == ["cross", "cross", "through", "through"]


def test_through_legs_follow_the_platform_rule():
    legs = [Leg(1, "primary", 90.0, "A"), Leg(2, "primary", 270.0, "A"), Leg(3, "secondary", 0.0, "B")]
    assert through_legs(legs) == frozenset({1, 2})
    # a bend beyond 75 degrees is not a through pair: the best single leg is
    bent = [Leg(1, "secondary", 0.0, "A"), Leg(2, "primary", 90.0, "B")]
    assert through_legs(bent) == frozenset({2})


def test_resolve_junction_by_id_or_landmark_key():
    net = network_from_dict(crossroad_network())
    assert net.resolve_junction(5) == 5 and net.resolve_junction("5") == 5 and net.resolve_junction("centre") == 5
    with pytest.raises(NetworkError):
        net.resolve_junction("nowhere")


def test_bad_network_is_refused(tmp_path):
    with pytest.raises(NetworkError):
        network_from_dict({"junctions": [], "segments": []})
    p = tmp_path / "broken.json"
    p.write_text("{not json")
    with pytest.raises(NetworkError):
        load_network(p)


def _oracle(rows, seen):
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        assert request.method == "GET"  # the twin only ever reads
        return httpx.Response(200, json=rows)
    return httpx.MockTransport(handler)


def test_live_state_is_read_only_and_labelled():
    seen: list = []
    net = network_from_dict(crossroad_network())
    rows = [{"segmentId": s, "speedKmh": 20.0, "congestionIdx": 0.9, "dataQuality": "synthetic"} for s in (2001, 2002, 2003, 2004)]
    tw = Twin(net, OracleClient("http://oracle.test", transport=_oracle(rows, seen)))
    dem = tw.build_demand(datetime(2026, 10, 28, 18, 0, tzinfo=IST), 30)
    assert dem.label == "EMULATED" and dem.source == "emulated-feed" and dem.coverage == 1.0
    assert seen and seen[0].url.path == "/api/traffic/snapshot"
    assert {"min_lon", "min_lat", "max_lon", "max_lat"} <= set(seen[0].url.params.keys())
    # rows from another city (no matching segment) are ignored: SIMULATED
    other = [{"segmentId": 9999, "congestionIdx": 0.5, "dataQuality": "real"}]
    tw2 = Twin(net, OracleClient("http://oracle.test", transport=_oracle(other, [])))
    assert tw2.build_demand(datetime(2026, 10, 28, 18, 0, tzinfo=IST), 30).label == "SIMULATED"
    # an unreachable oracle: SIMULATED, no error
    def down(request):
        raise httpx.ConnectError("refused", request=request)
    tw3 = Twin(net, OracleClient("http://oracle.test", transport=httpx.MockTransport(down)))
    assert tw3.build_demand(datetime(2026, 10, 28, 18, 0, tzinfo=IST), 30, mode="live").label == "SIMULATED"


@pytest.mark.skipif(mumbai_network_path() is None, reason="Mumbai network.json not in this tree")
def test_mumbai_network_loads_and_simulates_fast():
    import time

    tw = Twin(load_network(mumbai_network_path()))
    d = tw.describe()
    assert d["city"] == "mumbai" and d["junctions"] >= 70 and d["cells"] > 1000
    # the canonical landmark ids resolve (the monsoon pinch points among them)
    for key in ("dadar_tt", "hindmata", "kings_circle", "sion_circle", "kalanagar", "haji_ali"):
        tw.net.resolve_junction(key)
    assert tw.net.junctions[20].control == "programmed"   # Dadar TT Circle (OSM traffic_signals)
    dem = tw.build_demand(datetime(2026, 10, 28, 18, 0, tzinfo=IST), 30, mode="simulated")
    assert any("Mumbai weekday profile" in n for n in dem.notes)
    sc = tw.scenario(dem, 30)
    from sajag_twin.signals import Plan
    t = time.perf_counter()
    res = tw.run(sc, [Plan("do nothing")])
    assert time.perf_counter() - t < 4.0  # 30 min, whole network, on CPU
    assert res.exited_veh[0] > 0


@pytest.mark.skipif(kolkata_network_path() is None, reason="Kolkata network.json not in this tree")
def test_the_second_pack_kolkata_still_loads_and_simulates():
    import time

    tw = Twin(load_network(kolkata_network_path()))
    d = tw.describe()
    assert d["city"] == "kolkata" and d["junctions"] >= 48 and d["cells"] > 1000
    # the canonical landmark ids resolve
    for key in ("park_circus", "gariahat", "ultadanga", "esplanade"):
        tw.net.resolve_junction(key)
    assert tw.net.junctions[33].control == "programmed"
    dem = tw.build_demand(datetime(2026, 10, 28, 18, 0, tzinfo=IST), 30, mode="simulated")
    sc = tw.scenario(dem, 30)
    from sajag_twin.signals import Plan
    t = time.perf_counter()
    res = tw.run(sc, [Plan("do nothing")])
    assert time.perf_counter() - t < 3.0  # 30 min, whole network, on CPU
    assert res.exited_veh[0] > 0
