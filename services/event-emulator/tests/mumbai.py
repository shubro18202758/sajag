"""The Kolkata network snapshot the tests run on (data/mumbai_network_slim.json,
written by tools/mumbai_library.py from the city network)."""

from __future__ import annotations

import json
from pathlib import Path

SLIM = json.loads((Path(__file__).with_name("data") / "mumbai_network_slim.json")
                  .read_text(encoding="utf-8"))
JUNCTIONS = {j["junction_id"]: j for j in SLIM["junctions"]}
SEGMENTS = {s["segment_id"]: s for s in SLIM["segments"]}
KEYS = {j["key"]: j["junction_id"] for j in SLIM["junctions"] if j.get("key")}


def junction_xy(jid: int) -> tuple[float, float]:
    j = JUNCTIONS[jid]
    return (float(j["lon"]), float(j["lat"]))


def anchor(sid: int) -> tuple[float, float]:
    """A segment's fake on-road anchor: halfway between its crossings."""
    s = SEGMENTS[sid]
    a = junction_xy(s["from_junction"])
    b = junction_xy(s["to_junction"])
    return (round((a[0] + b[0]) / 2.0, 5), round((a[1] + b[1]) / 2.0, 5))


def legal_path(route: list[int]) -> bool:
    """A legal directed path on the snapshot (one-ways their own way)."""
    if not route or len(set(route)) != len(route):
        return False

    def ends(sid: int) -> list[tuple[int, int]]:
        s = SEGMENTS[sid]
        out = [(s["from_junction"], s["to_junction"])]
        if not s["oneway"]:
            out.append((s["to_junction"], s["from_junction"]))
        return out

    if any(sid not in SEGMENTS for sid in route):
        return False
    frontier = {e[1] for e in ends(route[0])}
    for sid in route[1:]:
        frontier = {e[1] for e in ends(sid) if e[0] in frontier}
        if not frontier:
            return False
    return True


def segment_named(fragment: str) -> int:
    """The lowest-id segment whose road name carries ``fragment``."""
    return min(sid for sid, s in SEGMENTS.items() if fragment.lower() in s["road_name"].lower())


def between(a: str, b: str) -> int:
    """The segment joining crossings ``a`` and ``b`` (either way)."""
    ja, jb = KEYS[a], KEYS[b]
    return min(sid for sid, s in SEGMENTS.items()
               if {s["from_junction"], s["to_junction"]} == {ja, jb})


def bearing(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Compass bearing (degrees) from point ``a`` to ``b`` (lon, lat)."""
    import math

    dx = (b[0] - a[0]) * math.cos(math.radians((a[1] + b[1]) / 2.0))
    dy = b[1] - a[1]
    return round(math.degrees(math.atan2(dx, dy)) % 360.0, 1)


def legs_at(jid: int) -> list[dict]:
    """A junction's legs (segment, class, bearing AWAY from the junction)."""
    out = []
    here = junction_xy(jid)
    for sid, s in sorted(SEGMENTS.items()):
        if jid not in (s["from_junction"], s["to_junction"]):
            continue
        other = s["to_junction"] if s["from_junction"] == jid else s["from_junction"]
        out.append({"segment_id": sid, "road_class": s["road_class"] or "secondary",
                     "bearing_deg": bearing(here, junction_xy(other))})
    return out


def passes(route: list[int]) -> list[int]:
    """The crossings a legal route passes, in order."""
    first = SEGMENTS[route[0]]
    if len(route) == 1:
        return [first["from_junction"], first["to_junction"]]
    second = SEGMENTS[route[1]]
    ends = (second["from_junction"], second["to_junction"])
    start = first["from_junction"] if first["to_junction"] in ends else first["to_junction"]
    out = [start]
    for sid in route:
        s = SEGMENTS[sid]
        out.append(s["to_junction"] if s["from_junction"] == out[-1] else s["from_junction"])
    return out
