"""Mumbai's reference movements are legal paths on the committed network:
the protected-movement spines (Mantralaya -> Airport T2 and its Raj Bhavan
and BKC variants) and every hospital green corridor end where it says."""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

from convoy_brain.city_routes import GREEN_CORRIDORS, PROTECTED_MOVEMENTS

REPO = Path(__file__).resolve().parents[3]


def _network():
    spec = importlib.util.spec_from_file_location("gen_osm_network_for_brain",
                                                  REPO / "scripts" / "gen_osm_network.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["gen_osm_network_for_brain"] = mod
    spec.loader.exec_module(mod)
    doc = json.loads((REPO / "scripts" / "data" / "osm_network.json").read_text(encoding="utf-8"))
    return mod, doc


@pytest.fixture(scope="module")
def net():
    mod, doc = _network()
    if doc.get("city") != "mumbai":
        pytest.skip("the committed evidence is not the Mumbai network")
    edges = mod.evidence_edges(doc)
    ids = {s["segment_id"] for s in doc["segments"]}
    junctions = {j["junction_id"]: j for j in doc["junctions"]}
    segments = {s["segment_id"]: s for s in doc["segments"]}
    return mod, edges, ids, junctions, segments


def _key(junctions, jid):
    return junctions[jid].get("key")


@pytest.mark.parametrize("name", sorted(PROTECTED_MOVEMENTS))
def test_every_protected_movement_is_a_legal_path_between_its_ends(net, name):
    mod, edges, ids, junctions, segments = net
    m = PROTECTED_MOVEMENTS[name]
    assert mod.spine_problems(tuple(m["spine"]), ids, edges) == []
    first, last = segments[m["spine"][0]], segments[m["spine"][-1]]
    assert m["origin_junction"] in {_key(junctions, first["from_junction"]),
                                    _key(junctions, first["to_junction"])}
    assert m["destination_junction"] in {_key(junctions, last["from_junction"]),
                                         _key(junctions, last["to_junction"])}


def test_the_base_movement_is_the_seeded_profile_spine():
    sql = (REPO / "services" / "corridor-store" / "migrations"
           / "008_event_profiles.sql").read_text(encoding="utf-8")
    row = sql[sql.index("('vvip_convoy_base'"):]
    seeded = tuple(int(x) for x in re.search(r"ARRAY\[([0-9,\s]+)\]", row).group(1).split(","))
    assert PROTECTED_MOVEMENTS["mantralaya_airport_t2"]["spine"] == seeded


@pytest.mark.parametrize("hospital", sorted(GREEN_CORRIDORS))
def test_every_green_corridor_ends_at_its_hospital_junction(net, hospital):
    mod, edges, ids, junctions, segments = net
    g = GREEN_CORRIDORS[hospital]
    path = tuple(g["reference_path"])
    assert mod.spine_problems(path, ids, edges) == []
    assert path[-1] == g["approach_segment"]
    approach = segments[g["approach_segment"]]
    assert g["junction"] in {_key(junctions, approach["from_junction"]),
                             _key(junctions, approach["to_junction"])}
    head = segments[path[0]]
    assert g["from_junction"] in {_key(junctions, head["from_junction"]),
                                  _key(junctions, head["to_junction"])}


def test_the_reference_text_names_no_person_and_keeps_the_officer_rule():
    import convoy_brain.city_routes as cr

    doc = " ".join((cr.__doc__ or "").split())
    assert "named officer approves" in doc and "current signal plan holds" in doc
    assert not re.search(r"\b(Hon|Shri|Smt|Minister|CM|PM)\b", json.dumps(
        [PROTECTED_MOVEMENTS, GREEN_CORRIDORS]))
