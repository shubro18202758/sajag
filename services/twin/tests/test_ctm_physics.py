"""Textbook checks of the cell-transmission model.

* a queue forms at a lane-drop bottleneck and discharges at the
  bottleneck's capacity, and the exit flow equals that capacity;
* the queue's tail moves upstream at the Lighthill-Whitham-Richards shock
  speed (q_u - q_b) / (k_u - k_b);
* free flow carries a platoon at the free-flow speed (exact when vf*dt = dx);
* a fixed-time signal discharges at saturation flow x green share;
* vehicles are conserved.
"""

from __future__ import annotations

import numpy as np
import pytest

from conftest import line_network, manual_demand
from sajag_twin.ctm import State, simulate
from sajag_twin.signals import Plan, step_greens
from sajag_twin.network import Program

EPOCH = 1_800_000_000  # a cycle-aligned-enough epoch for the phase clock


def run(cp, dem, seconds, state=None, t0=0.0, plans=None):
    return simulate(cp, dem, plans or [Plan("x")], t_start_s=t0, duration_s=seconds, epoch0=EPOCH, state=state)


def test_bottleneck_queue_forms_and_discharges_at_capacity(compile_dict):
    # 2-lane primary (3600 PCU/h) drops to 1 lane (1800 PCU/h)
    cp = compile_dict(line_network(lengths=(3000.0, 1000.0), lanes=(2, 1), speeds=(36, 36)))
    dem = manual_demand(cp, {0: 2700.0}, minutes=40)
    warm = run(cp, dem, 8 * 60)
    res = run(cp, dem, 10 * 60, state=warm.final_state, t0=8 * 60)
    q_in = res.link_out_veh[0, 0] / (10 / 60)  # PCU/h passing the bottleneck
    q_exit = res.exited_veh[0] / (10 / 60)
    assert q_in == pytest.approx(1800.0, rel=0.02)
    assert q_exit == pytest.approx(1800.0, rel=0.03)
    # the queue grows on the upstream link and none forms downstream
    s = res.series_link_queue_m[0]
    assert s[-1, 0] > s[0, 0] > 100.0
    assert res.link_max_queue_m[0, 1] < 5.0


def test_shockwave_speed_matches_lwr(compile_dict):
    cp = compile_dict(line_network(lengths=(3000.0, 1000.0), lanes=(2, 1), speeds=(36, 36)))
    q_u, q_b = 2700.0, 1800.0  # PCU/h, both lanes
    dem = manual_demand(cp, {0: q_u}, minutes=40)
    vf = 36.0
    kj_total = 140.0 * 2
    w = 1800.0 / (140.0 - 1800.0 / vf)  # km/h, per-lane triangular FD
    k_u = q_u / vf
    k_b = kj_total - q_b / w
    expected = (q_u - q_b) / (k_u - k_b) / 3.6  # m/s, negative = upstream
    first, last = cp.first[0], cp.last[0]
    pos = np.cumsum(cp.dx[first:last + 1]) - cp.dx[first:last + 1] / 2
    thr = (k_u + k_b) / 2 / 1000.0  # PCU per m (both lanes)

    def tail(state: State) -> float:
        dens = state.n[0, first:last + 1] / cp.dx[first:last + 1]
        congested = np.nonzero(dens > thr)[0]
        return float(pos[congested[0]]) if congested.size else float(pos[-1])

    # start in the upstream steady state, so the queue starts forming at t = 0
    dem.n0[first:last + 1] = k_u / 1000.0 * cp.dx[first:last + 1]
    st, t, times, tails = None, 0.0, [], []
    for _ in range(12):
        r = run(cp, dem, 60, state=st, t0=t)
        st, t = r.final_state, t + 60
        times.append(t)
        tails.append(tail(st))
    tt, xx = np.array(times[2:]), np.array(tails[2:])
    assert xx[-1] < xx[0] - 500.0  # the tail has moved well upstream
    slope = np.polyfit(tt, xx, 1)[0]
    assert expected < 0
    assert slope == pytest.approx(expected, rel=0.10)


def test_free_flow_platoon_travels_at_free_flow_speed(compile_dict):
    # 72 km/h = 20 m/s; dt 2 s -> 40 m cells, vf*dt/dx = 1: exact advection
    cp = compile_dict(line_network(lengths=(2000.0,), lanes=(2,), speeds=(72,)))
    assert np.allclose(cp.vr, 1.0)
    dem = manual_demand(cp, {0: 600.0}, minutes=10)
    dem.lam[1:, :] = 0.0  # one minute of entries: 10 PCU
    a = run(cp, dem, 90)
    assert a.exited_veh[0] == pytest.approx(0.0, abs=1e-9)  # 2000 m at 20 m/s takes 100 s
    b = run(cp, dem, 80, state=a.final_state, t0=90)
    assert a.exited_veh[0] + b.exited_veh[0] == pytest.approx(10.0, rel=1e-6)


@pytest.mark.parametrize("demand, expected", [(3000.0, 1800.0), (1200.0, 1200.0)])
def test_signal_discharges_at_saturation_times_green_share(compile_dict, demand, expected):
    prog = {"cycle_sec": 60, "offset_sec": 0,
            "phases": [{"green_sec": 30, "movements": ["through"]}, {"green_sec": 24, "movements": ["cross"]}]}
    cp = compile_dict(line_network(lengths=(1500.0, 1000.0), lanes=(2, 2), programs={"2": prog},
                                   names={2: "Test crossing"}))
    j = cp.net.junctions[2]
    assert j.control == "programmed" and j.virtual_cross
    dem = manual_demand(cp, {0: demand}, minutes=40)
    warm = run(cp, dem, 6 * 60)
    res = run(cp, dem, 20 * 60, state=warm.final_state, t0=6 * 60)
    q = res.link_out_veh[0, 0] / (20 / 60)
    assert q == pytest.approx(expected, rel=0.03)


def test_green_fraction_follows_the_platform_phase_clock():
    prog = Program(110, 94, ((50, ("through",)), (42, ("cross",))))
    # epoch e: pos = (e - offset) mod cycle; through is green for pos in [0, 50)
    g = step_greens(prog, "through", epoch0=94, t0_s=0, n_steps=55, dt=2.0)
    assert g[:25].tolist() == [1.0] * 25 and g[25:55].sum() == 0.0
    c = step_greens(prog, "cross", epoch0=94, t0_s=0, n_steps=55, dt=2.0)
    assert c[25:46].tolist() == [1.0] * 21 and c[46:].sum() == 0.0  # 92..110 is lost time
    assert step_greens(prog, "through", 94, 0, 55, 2.0).mean() == pytest.approx(50 / 110)


def test_vehicles_are_conserved(compile_dict):
    prog = {"cycle_sec": 80, "offset_sec": 7,
            "phases": [{"green_sec": 40, "movements": ["through"]}, {"green_sec": 30, "movements": ["cross"]}]}
    cp = compile_dict(line_network(lengths=(800.0, 1200.0, 600.0), lanes=(2, 1, 2), programs={"2": prog},
                                   names={2: "Test crossing"}))
    dem = manual_demand(cp, {0: 2500.0, 1: 300.0}, minutes=30, vx_pcu_h=400.0)
    res = run(cp, dem, 20 * 60)
    st = res.final_state
    inside = st.n.sum() + st.srcq.sum() + st.vxq.sum()
    steps_per_min = 60.0 / cp.dt  # lam / lamx are PCU per step, one row per minute
    arrived = (dem.lam[:20].sum() + dem.lamx[:20].sum()) * steps_per_min
    assert arrived == pytest.approx(inside + res.exited_veh[0], rel=1e-9)


def test_batched_candidates_match_single_runs(compile_dict):
    prog = {"cycle_sec": 60, "offset_sec": 0,
            "phases": [{"green_sec": 30, "movements": ["through"]}, {"green_sec": 24, "movements": ["cross"]}]}
    cp = compile_dict(line_network(lengths=(1500.0, 1000.0), lanes=(2, 2), programs={"2": prog},
                                   names={2: "Test crossing"}))
    from sajag_twin.signals import Window
    alt = Program(60, 0, ((40, ("through",)), (14, ("cross",))))
    plans = [Plan("a"), Plan("b", [Window(2, 0, 600, "fixed", alt)])]
    dem = manual_demand(cp, {0: 2600.0}, minutes=20, vx_pcu_h=300.0)
    both = run(cp, dem, 600, plans=plans)
    one = run(cp, dem, 600, plans=[plans[1]])
    assert both.link_delay_vs[1].sum() == pytest.approx(one.link_delay_vs[0].sum(), rel=1e-9)
    assert both.link_delay_vs[1].sum() < both.link_delay_vs[0].sum()  # more green for the loaded approach
