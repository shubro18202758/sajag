"""City Packs: a city is a folder, and scripts/city_build.py rebuilds every
derived file from it.

    * every pack carries what a build reads (city.json, corridors.json, the
      committed OpenStreetMap extracts);
    * the live pack (Mumbai) rebuilt into a temp dir equals the committed
      files byte for byte — seed SQL, network step, evidence, resolved
      table, the pack's network.json, the ingress table, the twin's
      scenario library;
    * the second pack (Kolkata, the city the platform was first built for)
      builds into a temp dir from its own folder into a complete, strongly
      connected network — and the repo's files are not touched by it: the
      data layer is portable.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
CITY_BUILD = REPO / "scripts" / "city_build.py"


def _city_build():
    spec = importlib.util.spec_from_file_location("city_build", CITY_BUILD)
    module = importlib.util.module_from_spec(spec)
    sys.modules["city_build"] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("city", ["mumbai", "kolkata", "ahmedabad"])
def test_a_pack_carries_what_a_build_reads(city):
    pack = REPO / "cities" / city
    doc = json.loads((pack / "city.json").read_text(encoding="utf-8"))
    assert doc["id"] == city
    assert {"south", "west", "north", "east"} <= set(doc["bbox"])
    assert {"lat", "lon"} <= set(doc["centre"])
    spec = json.loads((pack / "corridors.json").read_text(encoding="utf-8"))
    assert spec["junctions"] and spec["segments"]
    assert any((pack / "osm").glob("*.overpass.json.gz"))


def test_the_live_city_is_mumbai():
    cb = _city_build()
    assert cb.LIVE_CITY == "mumbai"
    assert "services/signal-ingress/src/feeds/segments_mumbai.rs" in cb.outputs("mumbai")
    assert not any("segments_mumbai" in rel for rel in cb.outputs("kolkata"))


def test_the_live_pack_rebuilds_the_committed_files(tmp_path):
    cb = _city_build()
    cb.build("mumbai", tmp_path)
    differ = [rel for rel in cb.outputs("mumbai")
              if (tmp_path / rel).read_bytes() != (REPO / rel).read_bytes()]
    assert differ == []


def test_the_second_pack_builds_from_its_own_folder(tmp_path):
    cb = _city_build()
    committed = {rel: (REPO / rel).read_bytes() for rel in cb.outputs("mumbai")}
    report = cb.build("kolkata", tmp_path)
    summary = report["summary"]
    assert (summary["junctions"], summary["segments"]) == (49, 65)
    assert summary["strongly_connected"] is True
    assert summary["signal_programs"] > 0 and summary["cameras"] > 0 and summary["stations"] > 0
    for rel in cb.outputs("kolkata"):
        assert (tmp_path / rel).is_file(), rel
    evidence = json.loads((tmp_path / "scripts/data/osm_network.json").read_text(encoding="utf-8"))
    assert evidence["city"] == "kolkata" and not evidence["network"]["problems"]
    seed = (tmp_path / "services/corridor-store/seed/sample_corridor.sql").read_text(encoding="utf-8")
    assert "Kolkata corridor seed" in seed
    assert re.search(r"POINT\(88\.\d+ 22\.\d+\)", seed)          # the second city's ground
    # the event-profile spines are seeded for the live city only: no profile
    # step is written for a second pack
    step = (tmp_path / "services/corridor-store/seed/reanchor_osm_network.sql").read_text(encoding="utf-8")
    assert "UPDATE events.event_profiles" not in step
    # the repo's (Mumbai) files are untouched by a second pack's build
    assert {rel: (REPO / rel).read_bytes() for rel in cb.outputs("mumbai")} == committed
