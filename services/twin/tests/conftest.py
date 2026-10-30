"""Synthetic networks and hand-made demand for the twin's tests."""

from __future__ import annotations

import math
import os
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest

from sajag_twin.ctm import Compiled, compile_network
from sajag_twin.demand import IST, Demand
from sajag_twin.network import network_from_dict

LAT0, LON0 = 19.00, 72.85
M_PER_DEG_LON = 111320.0 * math.cos(math.radians(LAT0))
M_PER_DEG_LAT = 110540.0


def _pt(x_m: float, y_m: float) -> tuple[float, float]:
    return (LON0 + x_m / M_PER_DEG_LON, LAT0 + y_m / M_PER_DEG_LAT)


def line_network(
    lengths=(1000.0, 1000.0),
    lanes=(2, 2),
    classes=None,
    speeds=None,
    oneway=True,
    programs: dict | None = None,
    names: dict | None = None,
) -> dict:
    """Junctions 1..n+1 along a west-east line; segment 1000+i joins i -> i+1."""
    classes = classes or ("primary",) * len(lengths)
    speeds = speeds or (36,) * len(lengths)
    xs = [0.0]
    for length in lengths:
        xs.append(xs[-1] + length)
    junctions = []
    for i, x in enumerate(xs, start=1):
        lon, lat = _pt(x, 0.0)
        junctions.append({"junction_id": i, "key": f"j{i}", "name": (names or {}).get(i, f"Node {i}"),
                          "name_mr": "", "lon": lon, "lat": lat})
    segments = []
    for i, length in enumerate(lengths, start=1):
        a, b = _pt(xs[i - 1], 0.0), _pt(xs[i], 0.0)
        segments.append({
            "segment_id": 1000 + i, "road_name": f"Road {i}", "from_junction": i, "to_junction": i + 1,
            "oneway": oneway, "road_class": classes[i - 1], "lanes": lanes[i - 1],
            "speed_limit_kmh": speeds[i - 1], "length_m": float(length), "line": [list(a), list(b)],
        })
    return {"schema": "sajag.network/1", "city": "testville", "junctions": junctions, "segments": segments,
            "signal_programs": programs or {}}


def crossroad_network(arm_m: float = 800.0, program: dict | None = None, cross_class: str = "secondary",
                      cross_lanes: int = 2) -> dict:
    """A signalised crossing (junction 5, named a crossing) with four two-way arms.

    East-west arms are 4-lane primary (the through road); north-south arms
    are 2-lane secondary (the cross road). Junctions 1..4 are the arm ends.
    """
    c = _pt(0, 0)
    ends = {1: _pt(-arm_m, 0), 2: _pt(arm_m, 0), 3: _pt(0, arm_m), 4: _pt(0, -arm_m)}
    junctions = [{"junction_id": 5, "key": "centre", "name": "Centre crossing", "name_mr": "मध्य चौक",
                  "lon": c[0], "lat": c[1]}]
    for jid, (lon, lat) in ends.items():
        junctions.append({"junction_id": jid, "key": f"end{jid}", "name": f"End {jid}", "name_mr": "", "lon": lon, "lat": lat})
    segs = []
    for sid, (a, cls, lanes) in zip((2001, 2002, 2003, 2004), ((1, "primary", 4), (2, "primary", 4), (3, cross_class, cross_lanes), (4, cross_class, cross_lanes))):
        segs.append({"segment_id": sid, "road_name": f"Arm {a}", "from_junction": a, "to_junction": 5, "oneway": False,
                     "road_class": cls, "lanes": lanes, "speed_limit_kmh": 40, "length_m": arm_m,
                     "line": [list(ends[a]), list(c)]})
    prog = program or {"cycle_sec": 90, "offset_sec": 0,
                       "phases": [{"green_sec": 36, "movements": ["through"]}, {"green_sec": 36, "movements": ["cross"]}]}
    return {"schema": "sajag.network/1", "city": "testville", "junctions": junctions, "segments": segs,
            "signal_programs": {"5": prog}}


def manual_demand(cp: Compiled, entries_pcu_h: dict[int, float], minutes: int, *, straight_only: bool = True,
                  vx_pcu_h: float = 0.0) -> Demand:
    """Constant side-street entries (PCU/h) per link index; all traffic goes straight on."""
    L = cp.L
    beta = np.zeros(cp.M)
    for a in range(L):
        lo = cp.mv_start[a]
        hi = cp.mv_start[a + 1] if a + 1 < L else cp.M
        exits = [m for m in range(lo, hi) if cp.mv_out[m] >= 0]
        sinks = [m for m in range(lo, hi) if cp.mv_out[m] < 0]
        if exits and straight_only:
            best = min(exits, key=lambda m: cp.mv_turn_deg[m])
            beta[best] = 1.0
        elif exits:
            for m in exits:
                beta[m] = 1.0 / len(exits)
        else:
            for m in sinks:
                beta[m] = 1.0
    lam = np.zeros((minutes, L))
    for li, q in entries_pcu_h.items():
        lam[:, li] = q * cp.dt / 3600.0
    lamx = np.full((minutes, cp.X), vx_pcu_h * cp.dt / 3600.0)
    return Demand(beta=beta, lam=lam, lamx=lamx, target_pcu_h=lam * 3600.0 / cp.dt, n0=np.zeros(cp.C),
                  horizon_origin_s=0.0, start=datetime(2026, 10, 28, 18, 0, tzinfo=IST), source="test",
                  label="SIMULATED")


@pytest.fixture
def compile_dict():
    def _c(doc: dict, dt: float = 2.0):
        return compile_network(network_from_dict(doc), dt)
    return _c


def city_network_path(city: str) -> Path | None:
    """A City Pack's network when this tree has it (SAJAG_TWIN_NETWORK wins
    for the live city, Mumbai)."""
    env = os.environ.get("SAJAG_TWIN_NETWORK")
    if city == "mumbai" and env and Path(env).is_file():
        return Path(env)
    here = Path(__file__).resolve()
    for parent in here.parents:
        cand = parent / "cities" / city / "network.json"
        if cand.is_file():
            return cand
    return None


def mumbai_network_path() -> Path | None:
    """The live city's network (Mumbai)."""
    return city_network_path("mumbai")


def kolkata_network_path() -> Path | None:
    """The second City Pack's network (Kolkata), kept loadable: the twin is
    city-agnostic."""
    return city_network_path("kolkata")
