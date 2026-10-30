"""The emulator's network-bound data agrees with the Mumbai city network.

The library routes, the profiles' cause segments and the living city's
sites and beats are written by tools/mumbai_library.py from the city
network; the tests elsewhere run on its slim snapshot.  When the full pack
network (cities/mumbai/network.json, or EMULATOR_CITY_NETWORK) is present,
these tests rebuild everything from it and fail on any drift — a
regenerated network then needs one re-run of the tool.  They skip in a tree
without the pack network.
"""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

import pytest

from event_emulator.mumbai_network import (
    PATROL_ROWS,
    PROFILE_SEGMENTS,
    SIGNALISED_JUNCTIONS,
    SITE_ROWS,
)
from event_emulator.library import load_library
from mumbai import SLIM

SERVICE = Path(__file__).resolve().parents[1]
#: The pack network (EMULATOR_CITY_NETWORK points elsewhere, e.g. at the
#: network stream's tree before the merge).
NETWORK = Path(os.environ.get("EMULATOR_CITY_NETWORK")
               or SERVICE.parents[1] / "cities" / "mumbai" / "network.json")


@pytest.fixture(scope="module")
def network() -> dict:
    if not NETWORK.is_file():
        pytest.skip(f"{NETWORK} is not in this tree")
    return json.loads(NETWORK.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def tool():
    spec = importlib.util.spec_from_file_location(
        "mumbai_library", SERVICE / "tools" / "mumbai_library.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_the_snapshot_is_the_city_network(network):
    ends = {s["segment_id"]: (s["from_junction"], s["to_junction"], bool(s["oneway"]))
            for s in network["segments"]}
    assert {s["segment_id"]: (s["from_junction"], s["to_junction"], s["oneway"])
            for s in SLIM["segments"]} == ends
    assert {j["junction_id"]: j.get("key") for j in SLIM["junctions"]} == {
        j["junction_id"]: j.get("key") for j in network["junctions"]}
    assert set(SIGNALISED_JUNCTIONS) == {int(k) for k in network.get("signal_programs") or {}}


def test_the_library_is_built_from_the_city_network(network, tool):
    net = tool.Network(network)
    built = {u["id"]: u["scenarioConfig"] for u in tool.build(net)}
    lib = load_library()
    assert set(built) == set(lib)
    for uid, cfg in built.items():
        have = lib[uid].config
        assert have["route_segment_ids"] == cfg["route_segment_ids"], uid
        assert [fe["segment_id"] for fe in have["forced_events"]] == [
            fe["segment_id"] for fe in cfg["forced_events"]], uid
        assert not tool.legal(net, have["route_segment_ids"]), uid
    assert PROFILE_SEGMENTS == tool.profile_segments(net, tool.build(net))


def test_the_living_city_is_built_from_the_city_network(network, tool):
    net = tool.Network(network)
    sites, patrols, signalised = tool.living_sites(net)
    assert [(s["site_id"], tuple(s["segments"]), tuple(s["junctions"])) for s in sites] == [
        (row[0], tuple(row[4]), tuple(row[5])) for row in SITE_ROWS]
    assert [(u, tuple(r)) for u, _b, r in patrols] == [(u, tuple(r)) for u, _b, r in PATROL_ROWS]
    assert set(signalised) == set(SIGNALISED_JUNCTIONS)
