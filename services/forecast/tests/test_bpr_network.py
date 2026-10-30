import numpy as np

from forecast.bpr import speed_from_vc, vc_from_speed
from forecast.network import haversine_m, load_network


def test_bpr_roundtrip_and_monotone():
    vc = np.linspace(0.0, 1.6, 33)
    sp = speed_from_vc(vc, 40.0)
    assert np.all(np.diff(sp) <= 0)
    back = vc_from_speed(sp, 40.0)
    assert np.allclose(back[1:], vc[1:], atol=1e-6)
    assert speed_from_vc(0.0, 40.0) == 40.0


def test_vc_from_speed_clips():
    assert vc_from_speed(60.0, 40.0) == 0.0  # faster than free flow → 0
    assert vc_from_speed(0.0, 40.0) <= 2.0


def test_network_bundled_snapshot(net):
    # the network stream's Mumbai v1 (72 junctions, 86 segments on OpenStreetMap)
    assert len(net.segments) >= 80
    assert net.segments[1066].road_name.startswith("Dr Ambedkar Road (Hindmata")
    assert net.junction_name(19).startswith("Hindmata")
    assert "OpenStreetMap" in net.attribution
    # every junction inside cities/mumbai/city.json "bbox"
    assert all(18.89 <= j.lat <= 19.28 and 72.77 <= j.lon <= 72.99 for j in net.junctions.values())
    assert all(j.name_mr for j in net.junctions.values())


def test_alternative_path_avoids_segment_and_respects_one_way(net):
    sid = 1063  # Dr Ambedkar Road, Byculla → Lalbaug
    path = net.alternative_path(sid)
    assert path and sid not in path
    seg = net.segments[sid]
    # the detour is a connected directed path from the segment's start to its end
    node = seg.from_junction
    for p in path:
        s = net.segments[p]
        if s.from_junction == node:
            node = s.to_junction
        else:
            assert not s.oneway and s.to_junction == node
            node = s.from_junction
    assert node == seg.to_junction
    # one-way carriageways (the Sea Link and Coastal Road directions) are never travelled backwards
    oneway = {i for i, s in net.segments.items() if s.oneway}
    assert {1006, 1007, 1008, 1009} <= oneway
    for a, b, i, _w in net.links():
        if i in oneway:
            assert (a, b) == (net.segments[i].from_junction, net.segments[i].to_junction)


def test_alternative_path_avoid_set_is_soft(net):
    full = net.alternative_path(1063)
    # avoiding every segment of the detour either finds another or falls back to the unconstrained one
    alt = net.alternative_path(1063, avoid=set(full))
    assert alt is not None and 1063 not in alt


def test_haversine():
    assert abs(haversine_m(18.9398, 72.8355, 18.9398, 72.8355)) < 1e-6
    # CSMT to Churchgate, about a kilometre
    assert 900 < haversine_m(18.9398, 72.8355, 18.9353, 72.8274) < 1100


def test_load_network_from_city_dir(tmp_path, net):
    import json

    (tmp_path / "network.json").write_text(json.dumps({
        "junctions": [{"junction_id": 1, "name": "A", "lat": 19.0, "lon": 72.84},
                      {"junction_id": 2, "name": "B", "lat": 19.01, "lon": 72.85}],
        "segments": [{"segment_id": 9, "road_name": "R", "from_junction": 1, "to_junction": 2,
                      "line": [[72.84, 19.0], [72.85, 19.01]]}]}))
    n = load_network(tmp_path)
    assert list(n.segments) == [9] and n.source.endswith("network.json")
    assert n.alternative_path(9) is None
