"""Geometry helpers, and every network id the proposals name exists in the Mumbai city pack."""

import json
from pathlib import Path

from cityfeeds.geo import MUMBAI, bearing_deg, compass, haversine_km, point_in_ring
from cityfeeds.proposals import ARTERIAL_ROADS, ARTERIALS, HEAT_POST_KEYS, HEAT_POSTS, NETWORK_SOURCE

NET = next(p / "cities" / "mumbai" / "network.json" for p in Path(__file__).resolve().parents
           if (p / "cities" / "mumbai" / "network.json").is_file())


def test_distance_and_bearing():
    # Dadar/Matunga centre to the Santacruz observatory (airport): about 8 km, to the north
    assert abs(haversine_km(*MUMBAI, 19.0896, 72.8656) - 8.0) < 1.0
    assert compass(bearing_deg(*MUMBAI, 15.0, 70.0)) in ("SSW", "SW")  # the Arabian Sea, south-west


def test_point_in_ring():
    sq = [[72.7, 18.8], [73.0, 18.8], [73.0, 19.3], [72.7, 19.3], [72.7, 18.8]]
    assert point_in_ring(72.856, 19.018, sq) and not point_in_ring(73.5, 19.0, sq)


def test_ids_come_from_the_city_pack_and_exist_there():
    assert NETWORK_SOURCE == "cities/mumbai/network.json"
    net = json.loads(NET.read_text(encoding="utf-8"))
    segs = {s["segment_id"]: s["road_name"] for s in net["segments"]}
    juns = {j["junction_id"]: j["key"] for j in net["junctions"]}
    assert len(ARTERIALS) == len(ARTERIAL_ROADS)  # every named arterial is in the pack
    for ids, road, j, _name in ARTERIALS:
        assert ids and all(segs[i] == road for i in ids) and j in juns
    assert [juns[j] for j, _n in HEAT_POSTS] == HEAT_POST_KEYS
