#!/usr/bin/env python3
"""city_build.py — rebuild every file the services read from one City Pack.

A city is a folder: ``cities/<id>/`` holds ``city.json`` (names, bbox,
centre, plates, agencies), ``landmarks.json`` (canonical place names),
``corridors.json`` (the curated corridor network) and ``osm/`` (the committed
OpenStreetMap extracts, ODbL).  Everything below is DERIVED from it,
deterministically and offline (no network, no database):

  1. the road network — ``scripts/gen_osm_network.py --city <id>``:
       services/corridor-store/seed/sample_corridor.sql      fresh-install seed
       services/corridor-store/seed/reanchor_osm_network.sql the network step
       services/corridor-store/seed/display_geometry_osm.sql superseded display file
       scripts/data/osm_network.json                         the evidence
       scripts/data/osm_network_map.json                     the resolved table
       cities/<id>/network.json                              the compact network
  2. the signal-ingress segment table (the live city only — the Rust crate
     compiles one table) — ``scripts/gen_ingress_segments.py``:
       services/signal-ingress/src/feeds/segments_mumbai.rs
  3. the twin's use-case scenarios and scenario library (the live city):
       services/traffic-oracle/src/traffic_oracle/simulation/use_case_scenarios.json
         re-synced from the event emulator's use-case library — ONLY when
         every library route is a legal path on this network (otherwise the
         library is on another network and the twin's copy is kept);
       scripts/scenario_library.json  (``python -m traffic_oracle.simulation export``)

Other streams' generators that read the pack (the deck's city module, the
OSINT gazetteer) are run too when they exist and the build writes into the
repository (``--with-others``).

Usage:
    python3 scripts/city_build.py mumbai                  # rebuild into the repo
    python3 scripts/city_build.py kolkata --out DIR       # a second pack, elsewhere
    python3 scripts/city_build.py mumbai --check          # rebuild into a temp dir
                                                          # and diff with the repo
Run it twice: the second run changes nothing (every output is byte-stable).
"""

from __future__ import annotations

import argparse
import filecmp
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
#: the city whose network the services run (the one the ingress table and the
#: twin's scenarios are built for)
LIVE_CITY = "mumbai"
ORACLE_SRC = REPO / "services" / "traffic-oracle" / "src"
USE_CASE_LIBRARY = (REPO / "services" / "event-emulator" / "src" / "event_emulator"
                    / "use_case_library.json")
TWIN_USE_CASES = Path("services/traffic-oracle/src/traffic_oracle/simulation/use_case_scenarios.json")
#: the ScenarioSpec fields the twin reads from a use case's scenarioConfig
TWIN_FIELDS = ("scenario_id", "name", "description", "category", "route_segment_ids",
               "departure_time", "vvip_class", "closure_policy", "horizon_min",
               "n_replications", "seed", "convoy_speed_kmh", "weather", "event_overrides",
               "forced_events", "expected_features", "event_kind", "crowd_class",
               "duration_class")
#: use cases the twin does not simulate (no corridor movement to run)
TWIN_SKIP = {"watchlist_anpr_sweep"}

#: every file a build writes, repo-relative (for --check)
NETWORK_OUTPUTS = (
    "services/corridor-store/seed/sample_corridor.sql",
    "services/corridor-store/seed/reanchor_osm_network.sql",
    "services/corridor-store/seed/display_geometry_osm.sql",
    "scripts/data/osm_network.json",
    "scripts/data/osm_network_map.json",
)
LIVE_OUTPUTS = (
    "services/signal-ingress/src/feeds/segments_mumbai.rs",
    str(TWIN_USE_CASES),
    "scripts/scenario_library.json",
)


def _run(cmd: list[str], **kw) -> None:
    print("+", " ".join(str(c) for c in cmd), file=sys.stderr)
    subprocess.run(cmd, check=True, **kw)


def _generator():
    spec = importlib.util.spec_from_file_location("gen_osm_network", REPO / "scripts" / "gen_osm_network.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["gen_osm_network"] = mod
    spec.loader.exec_module(mod)
    return mod


def outputs(city: str) -> list[str]:
    out = [*NETWORK_OUTPUTS, f"cities/{city}/network.json"]
    if city == LIVE_CITY:
        out += LIVE_OUTPUTS
    return out


def sync_use_cases(out_root: Path, network_json: Path) -> str:
    """Re-sync the twin's use-case scenarios from the emulator's library when
    the library is on this network; returns what happened."""
    target = out_root / TWIN_USE_CASES
    current = REPO / TWIN_USE_CASES
    if out_root != REPO and current.is_file() and not target.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(current.read_bytes())
    if not USE_CASE_LIBRARY.is_file():
        return "kept (no use-case library)"
    gen = _generator()
    doc = json.loads(network_json.read_text(encoding="utf-8"))
    edges = gen.evidence_edges(doc)
    ids = {s["segment_id"] for s in doc["segments"]}
    library = json.loads(USE_CASE_LIBRARY.read_text(encoding="utf-8"))
    rows, illegal = [], []
    for u in library:
        cfg = u.get("scenarioConfig") or {}
        if u.get("id") in TWIN_SKIP:
            continue
        route = tuple(int(s) for s in cfg.get("route_segment_ids", []))
        forced = {int(e["segment_id"]) for e in cfg.get("forced_events", [])}
        if gen.spine_problems(route, ids, edges) or not forced <= ids:
            illegal.append(str(u.get("id")))
            continue
        rows.append({k: cfg[k] for k in TWIN_FIELDS if k in cfg})
    if illegal or not rows:
        return (f"kept: the emulator's library is not on this network "
                f"({', '.join(illegal[:5]) or 'no use cases'})")
    old = json.loads(target.read_text(encoding="utf-8")) if target.is_file() else {}
    new = {
        "about": old.get("about", "The city's use-case scenarios (the twin's copy of the event "
                                  "emulator's use-case library configs)."),
        "source": "services/event-emulator/src/event_emulator/use_case_library.json",
        "scenarios": rows,
    }
    text = json.dumps(new, indent=1, ensure_ascii=False) + "\n"
    if not target.is_file() or target.read_text(encoding="utf-8") != text:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return f"synced {len(rows)} use cases"
    return f"unchanged ({len(rows)} use cases)"


def export_scenarios(out_root: Path) -> None:
    """scripts/scenario_library.json from the twin (its own seed parse); a
    build elsewhere points the twin at that build's seed and use cases."""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ORACLE_SRC) + os.pathsep + env.get("PYTHONPATH", "")
    env["SAJAG_TWIN_USE_CASES"] = str(out_root / TWIN_USE_CASES)
    script = (
        "import json, sys\n"
        "from pathlib import Path\n"
        "root = Path(sys.argv[1])\n"
        "import traffic_oracle.simulation.network as n\n"
        "n._SEED_RELATIVE = root / 'services/corridor-store/seed/sample_corridor.sql'\n"
        "import traffic_oracle.simulation.scenarios as s\n"
        "payload = s.export_library()\n"
        "target = root / 'scripts/scenario_library.json'\n"
        "target.parent.mkdir(parents=True, exist_ok=True)\n"
        "target.write_text(json.dumps(payload, indent=2), encoding='utf-8')\n"
        "print(f'wrote {target} ({payload[\"n_scenarios\"]} scenarios)', file=sys.stderr)\n"
    )
    _run([sys.executable, "-c", script, str(out_root)], env=env)


def build(city: str, out_root: Path, with_others: bool = False) -> dict:
    """Rebuild every derived file of ``city`` under ``out_root``."""
    out_root = out_root.resolve()
    cmd = [sys.executable, str(REPO / "scripts" / "gen_osm_network.py"), "--city", city]
    if out_root != REPO:
        cmd += ["--out-root", str(out_root)]
    _run(cmd)
    network_json = out_root / "scripts" / "data" / "osm_network.json"
    report = {"city": city, "out_root": str(out_root)}
    if city == LIVE_CITY:
        _run([sys.executable, str(REPO / "scripts" / "gen_ingress_segments.py"),
              "--network", str(network_json),
              "--out", str(out_root / "services/signal-ingress/src/feeds/segments_mumbai.rs")])
        report["use_cases"] = sync_use_cases(out_root, network_json)
        print(f"use cases: {report['use_cases']}", file=sys.stderr)
        library = REPO / "scripts" / "scenario_library.json"
        before = library.read_bytes() if library.is_file() else b""
        export_scenarios(out_root)
        # the network evidence notes where the twin's scenario library and
        # the emulator's library disagree: a changed library means one more
        # (cheap) network pass so a second build changes nothing
        if out_root == REPO and library.read_bytes() != before:
            _run(cmd)
    if with_others and out_root == REPO:
        deck = REPO / "services" / "command-deck" / "scripts" / "gen_deck_city.mjs"
        if deck.is_file():
            _run(["node", str(deck)])
        gaz = REPO / "scripts" / "gen_osint_gazetteer.py"
        if gaz.is_file():
            _run([sys.executable, str(gaz)])
    report["summary"] = summarise(network_json)
    return report


def summarise(network_json: Path) -> dict:
    doc = json.loads(network_json.read_text(encoding="utf-8"))
    segs = doc["segments"]
    out = {
        "junctions": len(doc["junctions"]),
        "segments": len(segs),
        "directed_links": sum(1 if s["oneway"] else 2 for s in segs),
        "one_way_segments": sum(1 for s in segs if s["oneway"]),
        "km": round(sum(s["length_m"] for s in segs) / 1000.0, 1),
        "strongly_connected": doc["network"]["strong_components"] == 1,
        "signal_programs": len(doc["signal_programs"]),
        "cameras": len(doc["cameras"]),
        "stations": len(doc["stations"]),
    }
    vip = _vip_route(network_json)
    if vip:
        by_id = {s["segment_id"]: s for s in segs}
        out["vip_route"] = vip
        out["vip_km"] = round(sum(by_id[s]["length_m"] for s in vip) / 1000.0, 1)
        out["vip_free_flow_min"] = round(
            sum(by_id[s]["length_m"] / (by_id[s]["speed_limit_kmh"] / 3.6) for s in vip) / 60.0, 1)
    return out


def _vip_route(network_json: Path) -> list[int] | None:
    """The VIP-movement profile's spine (migration 008), when this build is
    the network it is seeded for and the spine is a path on it."""
    gen = _generator()
    try:
        spine = gen.seeded_profile_spines().get("vvip_convoy_base")
    except (OSError, ValueError):
        return None
    doc = json.loads(network_json.read_text(encoding="utf-8"))
    if not spine or gen.spine_problems(spine, {s["segment_id"] for s in doc["segments"]},
                                       gen.evidence_edges(doc)):
        return None
    return list(spine)


def check(city: str) -> int:
    """Rebuild into a temp dir; every output must equal the repo's file."""
    with tempfile.TemporaryDirectory(prefix=f"city_build_{city}_") as tmp:
        build(city, Path(tmp))
        bad = [rel for rel in outputs(city)
               if not (REPO / rel).is_file()
               or not filecmp.cmp(REPO / rel, Path(tmp) / rel, shallow=False)]
    for rel in bad:
        print(f"DIFFERS: {rel}", file=sys.stderr)
    print(f"[{city}] {'OK: every derived file is current' if not bad else f'{len(bad)} file(s) differ'}")
    return 1 if bad else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("city", help="the city pack cities/<city>/")
    ap.add_argument("--out", type=Path, default=None,
                    help="write under this directory (repo-relative paths) instead of the repo")
    ap.add_argument("--check", action="store_true",
                    help="rebuild into a temp dir and fail when a repo file differs")
    ap.add_argument("--with-others", action="store_true",
                    help="also run other streams' pack generators (deck city module, gazetteer)")
    args = ap.parse_args(argv)
    if not (REPO / "cities" / args.city / "city.json").is_file():
        ap.error(f"no city pack cities/{args.city}/city.json")
    if args.check:
        return check(args.city)
    report = build(args.city, args.out or REPO, args.with_others)
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
