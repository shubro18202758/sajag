"""Webster's optimal fixed-time cycle and green split (Webster 1958).

For a junction with phases p, each with a critical flow ratio
``y_p = max(q/s)`` over the approaches the phase serves, and total lost
time ``L`` per cycle:

    C0 = (1.5 L + 5) / (1 - Y),   Y = sum_p y_p
    g_p = (C0 - L) * y_p / Y      (effective green)

C0 is clamped to [MIN_CYCLE_S, MAX_CYCLE_S]; at Y >= 0.95 the junction is
oversaturated, the formula breaks down, and the maximum cycle is used with
greens in proportion to y (flagged ``oversaturated``).

``webster_delay`` is Webster's average delay per vehicle on one approach,
used by the tests to show that C0 sits at (or very near) the delay minimum.
"""

from __future__ import annotations

from dataclasses import dataclass

from sajag_twin import params as P
from sajag_twin.network import Program

__all__ = ["WebsterResult", "webster", "webster_cycle", "webster_delay"]


def webster_cycle(lost_s: float, Y: float) -> float:
    """Unclamped optimal cycle (s); inf when Y >= 1."""
    if Y >= 1.0:
        return float("inf")
    return (1.5 * lost_s + 5.0) / (1.0 - Y)


def webster_delay(cycle: float, green: float, q: float, s: float) -> float:
    """Webster's average delay per vehicle (s) on one approach.

    ``q`` and ``s`` in veh/s, ``green`` effective green (s). Uniform term +
    random term - empirical correction. inf when the approach is at or over
    capacity.
    """
    lam = green / cycle
    x = q / (lam * s) if lam > 0 else float("inf")
    if x >= 1.0 or q <= 0:
        return float("inf") if q > 0 else 0.0
    d1 = cycle * (1 - lam) ** 2 / (2 * (1 - lam * x))
    d2 = x * x / (2 * q * (1 - x))
    d3 = 0.65 * (cycle / (q * q)) ** (1.0 / 3.0) * x ** (2 + 5 * lam)
    return d1 + d2 - d3


@dataclass
class WebsterResult:
    program: Program
    cycle_raw_s: float
    Y: float
    y: dict[str, float]
    lost_s: int
    oversaturated: bool
    flows: dict[str, dict]

    def to_dict(self) -> dict:
        return {
            "program": self.program.to_dict(),
            "cycle_formula_s": None if self.cycle_raw_s == float("inf") else round(self.cycle_raw_s, 1),
            "Y": round(self.Y, 3),
            "critical_flow_ratio": {k: round(v, 3) for k, v in self.y.items()},
            "lost_time_s": self.lost_s,
            "oversaturated": self.oversaturated,
            "flows_used": self.flows,
        }


def webster(program: Program, critical: dict[str, tuple[float, float]], *, min_green: int = P.MIN_GREEN_S) -> WebsterResult:
    """Webster timing for ``program``'s phases.

    ``critical`` maps a movement label to ``(q, s)`` (PCU/h) of its critical
    approach. The offset and the phase order stay as they are; only the
    cycle and the greens change. Lost time is the program's own (the part
    of the cycle no green covers), or 4 s per phase when it has none.
    """
    lost = program.lost_sec or 4 * len(program.phases)
    y_phase = []
    for _, ms in program.phases:
        y_phase.append(max((critical[m][0] / critical[m][1]) for m in ms if m in critical and critical[m][1] > 0) if any(m in critical for m in ms) else 0.0)
    Y = sum(y_phase)
    raw = webster_cycle(lost, Y)
    over = Y >= 0.95
    if over or raw == float("inf"):
        C = P.MAX_CYCLE_S
    else:
        C = int(round(min(P.MAX_CYCLE_S, max(P.MIN_CYCLE_S, raw))))
    usable = C - lost
    if Y <= 0:
        greens = [usable // max(1, len(program.phases))] * len(program.phases)
    else:
        greens = [usable * yp / Y for yp in y_phase]
    # minimum green, then hand the remainder back in proportion
    greens = [max(float(min_green), g) for g in greens]
    excess = sum(greens) - usable
    if excess > 0:
        flex = [g - min_green for g in greens]
        tot = sum(flex)
        if tot > 0:
            greens = [g - excess * f / tot for g, f in zip(greens, flex)]
    gi = [int(round(g)) for g in greens]
    gi[0] += usable - sum(gi)  # rounding remainder to the first phase
    prog = Program(
        cycle_sec=int(C),
        offset_sec=program.offset_sec % int(C),
        phases=tuple((g, ms) for g, (_, ms) in zip(gi, program.phases)),
        source="twin Webster baseline (MODELLED)",
    )
    labels_y = {}
    for (_, ms), yp in zip(program.phases, y_phase):
        labels_y["+".join(ms)] = yp
    flows = {m: {"q_pcu_h": round(q, 0), "s_pcu_h": round(s, 0)} for m, (q, s) in critical.items()}
    return WebsterResult(prog, raw, Y, labels_y, int(lost), over, flows)
