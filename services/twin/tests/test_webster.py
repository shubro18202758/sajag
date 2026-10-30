"""Webster's formula: textbook values, clamping, minimum green, delay optimum."""

from __future__ import annotations

import numpy as np
import pytest

from sajag_twin import params as P
from sajag_twin.network import Program
from sajag_twin.webster import webster, webster_cycle, webster_delay


def two_phase(cycle=110, g1=50, g2=42) -> Program:
    return Program(cycle, 17, ((g1, ("through",)), (g2, ("cross",))))


def test_cycle_formula_textbook_values():
    # C0 = (1.5 L + 5) / (1 - Y)
    assert webster_cycle(10, 0.6) == pytest.approx(50.0)
    assert webster_cycle(18, 0.7) == pytest.approx(32.0 / 0.3)
    assert webster_cycle(12, 0.5) == pytest.approx(46.0)
    assert webster_cycle(10, 1.0) == float("inf")


def test_webster_program_cycle_and_split():
    # lost time 18 s (110 - 50 - 42); y = 0.42 and 0.28 -> Y = 0.70
    crit = {"through": (0.42 * 3600, 3600.0), "cross": (0.28 * 1600, 1600.0)}
    r = webster(two_phase(), crit)
    assert r.lost_s == 18
    assert r.Y == pytest.approx(0.70)
    assert r.cycle_raw_s == pytest.approx(106.67, abs=0.01)
    p = r.program
    assert p.cycle_sec == 107
    assert sum(g for g, _ in p.phases) == 107 - 18
    # greens in proportion to y: 89 * 0.6 = 53.4, 89 * 0.4 = 35.6
    assert p.phases[0][0] == pytest.approx(53, abs=1)
    assert p.phases[1][0] == pytest.approx(36, abs=1)
    assert p.offset_sec == 17 and [m for _, m in p.phases] == [("through",), ("cross",)]
    assert not r.oversaturated


def test_webster_clamps_and_flags_oversaturation():
    low = webster(two_phase(), {"through": (300.0, 3600.0), "cross": (100.0, 1600.0)})
    assert low.program.cycle_sec == P.MIN_CYCLE_S
    over = webster(two_phase(), {"through": (0.6 * 3600, 3600.0), "cross": (0.4 * 1600, 1600.0)})
    assert over.oversaturated and over.program.cycle_sec == P.MAX_CYCLE_S
    assert sum(g for g, _ in over.program.phases) == P.MAX_CYCLE_S - 18


def test_minimum_green_is_kept():
    r = webster(two_phase(), {"through": (0.75 * 3600, 3600.0), "cross": (0.01 * 1600, 1600.0)})
    assert min(g for g, _ in r.program.phases) >= P.MIN_GREEN_S
    assert sum(g for g, _ in r.program.phases) == r.program.cycle_sec - 18


def test_webster_cycle_sits_at_the_delay_minimum():
    """Total Webster delay over cycles 40..200 s is lowest near C0 (the curve is flat around it)."""
    lost = 12.0
    s = np.array([3600.0, 1800.0]) / 3600.0  # veh/s
    y = np.array([0.35, 0.25])
    q = y * s
    Y = y.sum()
    c0 = webster_cycle(lost, Y)

    def total_delay(c: float) -> float:
        greens = (c - lost) * y / Y
        return float(sum(qi * webster_delay(c, g, qi, si) for qi, g, si in zip(q, greens, s)))

    cycles = np.arange(40, 201)
    delays = np.array([total_delay(c) for c in cycles])
    best = cycles[int(np.argmin(delays))]
    assert 0.75 * c0 <= best <= 1.5 * c0
    assert total_delay(c0) <= 1.05 * delays.min()
