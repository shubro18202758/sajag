"""Max-pressure: the split rule, and the controller in the twin."""

from __future__ import annotations

import pytest

from conftest import crossroad_network, manual_demand
from sajag_twin import params as P
from sajag_twin.ctm import simulate
from sajag_twin.network import Program
from sajag_twin.signals import MaxPressureState, Plan, Window, allocate_greens

EPOCH = 1_800_000_000


def test_allocate_greens_is_proportional_with_minimum_green():
    prog = Program(110, 0, ((50, ("through",)), (42, ("cross",))))
    usable = 110 - 18
    g = allocate_greens(prog, [3.0, 1.0])
    assert sum(g) == usable
    assert g[0] == pytest.approx(P.MIN_GREEN_S + (usable - 2 * P.MIN_GREEN_S) * 0.75, abs=1)
    g = allocate_greens(prog, [1.0, 0.0])
    assert g[1] == P.MIN_GREEN_S and sum(g) == usable
    assert allocate_greens(prog, [0.0, -2.0]) == [50, 42]  # no pressure: keep the program's split


def test_controller_keeps_cycle_offset_and_moves_at_most_four_seconds():
    prog = Program(90, 13, ((36, ("through",)), (36, ("cross",))))
    m = MaxPressureState(0, 5, 0.0, 3600.0, prog)
    calls = []

    def pressure():
        calls.append(1)
        return [10.0, 1.0]

    # walk two full cycles from a cycle boundary (epoch with pos 0)
    e0 = 13 + 90 * 1000
    greens_seen = []
    for t in range(0, 3 * 90, 2):
        m.step(e0 + t, 2.0, pressure)
        greens_seen.append(tuple(m.greens))
    assert calls, "pressure is sampled during the cycle"
    hist = m.history
    assert hist and hist[0][0] - 36 <= P.MP_MAX_STEP_S and hist[0][0] > 36
    for a, b in zip([[36, 36]] + hist, hist):
        assert abs(b[0] - a[0]) <= P.MP_MAX_STEP_S
        assert sum(b) == 90 - 18


def test_max_pressure_moves_green_to_the_loaded_approach(compile_dict):
    # a wrong split: the loaded through road gets 20 s, the light cross road 52 s
    wrong = {"cycle_sec": 90, "offset_sec": 0,
             "phases": [{"green_sec": 20, "movements": ["through"]}, {"green_sec": 52, "movements": ["cross"]}]}
    cp = compile_dict(crossroad_network(program=wrong))
    j = cp.net.junctions[5]
    assert j.control == "programmed"
    through_in = [i for i, lab in j.approach_label.items() if lab == "through"]
    cross_in = [i for i, lab in j.approach_label.items() if lab == "cross"]
    assert len(through_in) == 2 and len(cross_in) == 2
    # entries on the far end of each arm, heading to the centre
    entries = {i: 900.0 for i in through_in}
    entries.update({i: 150.0 for i in cross_in})
    dem = manual_demand(cp, entries, minutes=60)
    plans = [Plan("fixed"), Plan("mp", [Window(5, 0.0, 3600.0, "max_pressure")])]
    res = simulate(cp, dem, plans, t_start_s=0.0, duration_s=40 * 60, epoch0=EPOCH)
    hist = next(iter(res.mp_splits.values()))
    assert hist[-1][0] > 20 + 10  # through green has grown well past 20 s
    assert all(g >= P.MIN_GREEN_S for h in hist for g in h)
    assert res.link_delay_vs[1].sum() < 0.8 * res.link_delay_vs[0].sum()
