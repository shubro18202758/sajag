"""Signal plans for the twin: fixed-time windows, generated programs, max-pressure.

A *plan* is a list of :class:`Window` objects. Outside every window a
junction runs its base program (the network's, or the twin's labelled
template). Inside a window it runs either another fixed-time program or
max-pressure control. Times are seconds from the start of the measured
horizon.

The phase clock is the platform's (traffic-oracle ``signals/plans.py``
``phase_at``): ``pos = (floor(epoch) - offset_sec) mod cycle_sec``; phases
run back to back from position 0 and whatever the greens leave at the end
of the cycle is lost time.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from sajag_twin import params as P
from sajag_twin.network import Network, NetworkError, Program

__all__ = [
    "MaxPressureState",
    "Plan",
    "Window",
    "extend_green",
    "green_start",
    "green_table",
    "green_wave_offsets",
    "step_greens",
]


@dataclass(frozen=True)
class Window:
    junction_id: int
    t0_s: float
    t1_s: float
    kind: str  # "fixed" | "max_pressure"
    program: Program | None = None

    def to_dict(self) -> dict:
        d = {
            "junction_id": self.junction_id,
            "from_min": round(self.t0_s / 60.0, 2),
            "to_min": round(self.t1_s / 60.0, 2),
            "control": "max-pressure" if self.kind == "max_pressure" else "fixed-time",
        }
        if self.program is not None:
            d["program"] = self.program.to_dict()
        return d


@dataclass
class Plan:
    name: str
    windows: list[Window] = field(default_factory=list)
    kind: str = "do_nothing"
    description: str = "Keep the current programs (do nothing)."

    def windows_for(self, jid: int) -> list[Window]:
        return sorted((w for w in self.windows if w.junction_id == jid), key=lambda w: w.t0_s)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "kind": self.kind,
            "description": self.description,
            "windows": [w.to_dict() for w in self.windows],
        }


# ---------------------------------------------------------------------------
# Green tables
# ---------------------------------------------------------------------------


def green_table(program: Program) -> dict[str, np.ndarray]:
    """Per movement label: a bool per second of the cycle (True = green)."""
    cycle = max(1, program.cycle_sec)
    out: dict[str, np.ndarray] = {m: np.zeros(cycle, dtype=bool) for m in program.labels}
    cursor = 0
    for green, movements in program.phases:
        a, b = min(cursor, cycle), min(cursor + max(0, green), cycle)
        for m in movements:
            out[m][a:b] = True
        cursor += max(0, green)
    return out


def green_start(program: Program, label: str) -> int:
    """Cycle position where the first phase serving ``label`` turns green."""
    cursor = 0
    for green, movements in program.phases:
        if label in movements:
            return cursor
        cursor += green
    return 0


def step_greens(program: Program, label: str, epoch0: int, t0_s: float, n_steps: int, dt: float) -> np.ndarray:
    """Green fraction of each step [t, t+dt) for one movement (0..1)."""
    tbl = green_table(program).get(label)
    if tbl is None:
        return np.zeros(n_steps)
    sub = max(1, int(round(dt)))
    secs = epoch0 + int(round(t0_s)) + np.arange(n_steps * sub)
    pos = (secs - program.offset_sec) % program.cycle_sec
    return tbl[pos].reshape(n_steps, sub).mean(axis=1)


# ---------------------------------------------------------------------------
# Program builders (pure)
# ---------------------------------------------------------------------------


def extend_green(program: Program, label: str, seconds: int, *, floor_s: int = P.MIN_GREEN_S) -> Program | None:
    """``label`` gets ``seconds`` more green, taken from the other phases.

    The cycle and offset stay as they are (as in the platform's own
    band->plan writer), so the junction's coordination with its neighbours
    is not broken. Other phases give green from the last phase backwards and
    never drop below ``floor_s``. None when nothing can be moved.
    """
    phases = list(program.phases)
    idx = [i for i, (_, ms) in enumerate(phases) if label in ms]
    if not idx or seconds <= 0:
        return None
    greens = [g for g, _ in phases]
    collected = 0
    for i in range(len(phases) - 1, -1, -1):
        if i in idx or collected >= seconds:
            continue
        give = min(max(0, greens[i] - floor_s), seconds - collected)
        greens[i] -= give
        collected += give
    if collected <= 0:
        return None
    greens[idx[0]] += collected
    sign = "+" if collected > 0 else ""
    return program.with_greens(greens, source=f"twin proposal ({label} {sign}{collected} s)")


def green_wave_offsets(
    net: Network,
    junction_ids: list[int],
    programs: dict[int, Program],
    speed_kmh: float,
) -> dict[int, Program] | None:
    """Offsets for a green wave along ``junction_ids`` (in travel order).

    The first junction keeps its offset; each next one's green for the
    corridor movement starts when a platoon released at the start of the
    previous green arrives at ``speed_kmh``. All junctions share one cycle:
    when cycles differ, every program is stretched to the longest cycle
    with its greens scaled in proportion. None when fewer than two
    signalised junctions are on the path or a hop has no link.
    """
    ids = [j for j in junction_ids if j in programs]
    if len(ids) < 2 or speed_kmh <= 0:
        return None
    cycle = max(programs[j].cycle_sec for j in ids)
    out: dict[int, Program] = {}
    for j in ids:
        prog = programs[j]
        if prog.cycle_sec != cycle:
            scale = (cycle - prog.lost_sec) / max(1, prog.cycle_sec - prog.lost_sec)
            greens = [int(round(g * scale)) for g, _ in prog.phases]
            prog = Program(cycle, prog.offset_sec, tuple((g, ms) for g, (_, ms) in zip(greens, prog.phases)), prog.source)
        out[j] = prog
    # movement label each junction gives the corridor's arriving link
    first = ids[0]
    offset = out[first].offset_sec
    result = {first: out[first].with_offset(offset, "twin proposal (green wave)")}
    prev = first
    full = [j for j in junction_ids]
    for j in ids[1:]:
        # travel time along the chain of links from prev to j
        i0, i1 = full.index(prev), full.index(j)
        tt = 0.0
        arriving = None
        for a, b in zip(full[i0:i1], full[i0 + 1:i1 + 1]):
            li = net.link_between(a, b)
            if li is None:
                return None
            tt += net.links[li].length_m / (speed_kmh / 3.6)
            arriving = li
        jn = net.junctions[j]
        jp = net.junctions[prev]
        lab_j = jn.approach_label.get(arriving, "through") if arriving is not None else "through"
        # the label the corridor uses leaving prev: the approach that feeds prev along the chain
        k = full.index(prev)
        lab_prev = "through"
        if k > 0:
            li_prev = net.link_between(full[k - 1], prev)
            if li_prev is not None:
                lab_prev = jp.approach_label.get(li_prev, "through")
        start_prev = green_start(out[prev], lab_prev)
        start_j = green_start(out[j], lab_j)
        offset_j = int(round(result[prev].offset_sec + start_prev + tt - start_j)) % cycle
        result[j] = out[j].with_offset(offset_j, "twin proposal (green wave)")
        prev = j
    return result


def validate_plan(net: Network, plan: Plan) -> None:
    for w in plan.windows:
        if w.junction_id not in net.junctions:
            raise NetworkError(f"unknown junction {w.junction_id}")
        j = net.junctions[w.junction_id]
        if not j.signalised:
            raise NetworkError(f"junction {w.junction_id} has no signal in the twin ({j.control})")
        if w.t1_s <= w.t0_s:
            raise NetworkError("a window must end after it starts")
        if w.kind == "fixed":
            if w.program is None:
                raise NetworkError("a fixed-time window needs a program")
            w.program.validate()
            have = set(j.program.labels) if j.program else set()
            if not set(w.program.labels) <= have | {"through", "cross"}:
                raise NetworkError(f"program movements {w.program.labels} do not match junction {w.junction_id}")
        elif w.kind != "max_pressure":
            raise NetworkError(f"unknown window kind {w.kind!r}")


# ---------------------------------------------------------------------------
# Max-pressure, cyclic form (Varaiya 2013; Le et al. 2015)
# ---------------------------------------------------------------------------


def allocate_greens(program: Program, pressures: list[float], *, min_green: int = P.MIN_GREEN_S) -> list[int]:
    """Split the program's usable green in proportion to phase pressure.

    The cycle, phase order, offset and lost time stay as in ``program``;
    every phase keeps at least ``min_green``. With no positive pressure the
    program's own split is kept.
    """
    n = len(program.phases)
    usable = program.cycle_sec - program.lost_sec
    p = [max(0.0, float(x)) for x in pressures]
    if n == 0 or sum(p) <= 1e-9 or usable < n * min_green:
        return [g for g, _ in program.phases]
    flex = usable - n * min_green
    raw = [min_green + flex * x / sum(p) for x in p]
    out = [int(round(g)) for g in raw]
    out[int(max(range(n), key=lambda i: raw[i]))] += usable - sum(out)
    return out


@dataclass
class MaxPressureState:
    """One junction under cyclic max-pressure in one candidate run.

    During each cycle the twin samples every phase's pressure (every
    ``MP_SAMPLE_S``); at the start of the next cycle (the platform's phase
    clock: position 0 of ``(epoch - offset) mod cycle``) the green split is
    moved towards the split proportional to the cycle-average pressure, by
    at most ``MP_MAX_STEP_S`` per phase per cycle and not at all within
    ``MP_DEADBAND_S``, so the controller does not oscillate. A phase's
    pressure is ``sum over its approaches of sat_flow * (occupancy upstream
    - turning-weighted occupancy downstream)``. Cycle, phase order, offset
    and lost time are the base program's, so neighbours stay coordinated
    and the comparison with fixed time is fair (same lost time per cycle).
    """

    k: int
    junction_id: int
    t0_s: float
    t1_s: float
    program: Program
    greens: list[int] = field(default_factory=list)
    cycle_index: int | None = None
    acc: list[float] = field(default_factory=list)
    samples: int = 0
    history: list[list[int]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.greens:
            self.greens = [g for g, _ in self.program.phases]
        self.acc = [0.0] * len(self.program.phases)

    def active(self, t: float) -> bool:
        return self.t0_s <= t < self.t1_s

    def step(self, epoch_s: int, dt: float, pressure_fn) -> dict[str, float]:
        """Green fraction per movement label for the step [epoch, epoch+dt)."""
        cyc = self.program.cycle_sec
        rel = epoch_s - self.program.offset_sec
        idx = rel // cyc
        if rel % P.MP_SAMPLE_S < dt:
            for i, p in enumerate(pressure_fn()):
                self.acc[i] += p
            self.samples += 1
        if idx != self.cycle_index:
            if self.cycle_index is not None and self.samples:
                avg = [a / self.samples for a in self.acc]
                target = allocate_greens(self.program, avg)
                usable = cyc - self.program.lost_sec
                # move towards the pressure split by at most MP_MAX_STEP_S per phase per cycle
                stepped = [
                    g if abs(t - g) <= P.MP_DEADBAND_S else g + max(-P.MP_MAX_STEP_S, min(P.MP_MAX_STEP_S, t - g))
                    for t, g in zip(target, self.greens)
                ]
                new = [max(P.MIN_GREEN_S, int(round(b))) for b in stepped]
                new[int(max(range(len(new)), key=lambda i: stepped[i]))] += usable - sum(new)
                self.greens = new
                if len(self.history) < 200:
                    self.history.append(list(self.greens))
            self.acc = [0.0] * len(self.program.phases)
            self.samples = 0
            self.cycle_index = idx
        prog = self.program.with_greens(self.greens, self.program.source)
        tbl = green_table(prog)
        sub = max(1, int(round(dt)))
        pos = (epoch_s + np.arange(sub) - prog.offset_sec) % cyc
        return {m: float(v[pos].mean()) for m, v in tbl.items()}
