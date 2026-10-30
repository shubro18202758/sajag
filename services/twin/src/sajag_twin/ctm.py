"""Cell-transmission model (Daganzo 1994/1995) over the whole network, in numpy.

Each directed link is cut into cells no shorter than one free-flow step
(``dx >= vf * dt``, the CFL condition). Each cell holds ``n`` PCU and has

* a flow capacity per step ``Q = sat * lanes * dt``;
* a holding capacity ``N = k_jam * lanes * dx``;
* a sending function ``S = min(n * vf*dt/dx, Q)``;
* a receiving function ``R = min(Q, (w*dt/dx) * (N - n))`` with the
  backward wave speed ``w = q_max / (k_jam - k_crit)`` (triangular
  fundamental diagram).

Inside a link the flow between neighbouring cells is ``min(S_up, R_down)``.
At a junction the last cell of every arriving link sends to the first
cells of the leaving links through *movements* with turning ratios, plus a
sink (traffic leaving to unmodelled side streets):

1. a signal caps an approach at ``Q * g``, ``g`` the green fraction of the
   step for the movement serving that approach;
2. demand for a leaving link larger than its receiving capacity is scaled
   down in proportion (merge);
3. first-in-first-out at the diverge (Daganzo's diverge rule), relaxed by
   lane count: a blocked movement holds back ``1/lanes`` of the approach
   (a single-lane approach is held back as a whole), and no movement ever
   sends more than its own exit can take.

Side-street traffic enters every link through a point queue at its first
cell (it yields to the junction flow), and a crossing whose cross road is
not in the network gets a point-queue *virtual* cross street served by the
cross phase.

The engine runs ``K`` candidate plans at once: every state array has a
leading candidate axis, so a ranking of 15 plans costs about as much
Python overhead as one.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from sajag_twin import params as P
from sajag_twin.network import Network, angle_diff
from sajag_twin.signals import MaxPressureState, Plan, step_greens

__all__ = ["Compiled", "RunResult", "compile_network", "simulate"]


@dataclass
class Compiled:
    net: Network
    dt: float
    # cells
    C: int
    cell_link: np.ndarray
    dx: np.ndarray
    vr: np.ndarray
    wr: np.ndarray
    qcap: np.ndarray
    ncap: np.ndarray
    first: np.ndarray
    last: np.ndarray
    up: np.ndarray
    dn: np.ndarray
    # movements, sorted by arriving link
    mv_in: np.ndarray
    mv_out: np.ndarray  # leaving link, -1 = sink
    mv_junction: np.ndarray
    mv_turn_deg: np.ndarray
    mv_start: np.ndarray  # first movement of each link (every link has >= 1)
    # signals
    groups: list[tuple[int, str]]
    approach_group: np.ndarray  # per link; len(groups) = always green
    # virtual cross streets
    vx_junction: np.ndarray
    vx_group: np.ndarray
    vx_qcap: np.ndarray  # PCU per step at full green
    # sensors (max-pressure): per link, cells within MP_SENSOR_M of its end / start
    sens_end: list[np.ndarray] = field(default_factory=list)
    sens_start: list[np.ndarray] = field(default_factory=list)

    @property
    def L(self) -> int:
        return len(self.net.links)

    @property
    def M(self) -> int:
        return len(self.mv_in)

    @property
    def X(self) -> int:
        return len(self.vx_junction)

    def summary(self) -> dict:
        return {
            "cells": self.C,
            "directed_links": self.L,
            "movements": self.M,
            "signal_groups": len(self.groups),
            "virtual_cross_streets": self.X,
            "dt_s": self.dt,
            "mean_cell_m": round(float(self.dx.mean()), 1),
        }


def compile_network(net: Network, dt: float = P.DT_S) -> Compiled:
    links = net.links
    L = len(links)
    cell_link, dx, vr, wr, qcap, ncap = [], [], [], [], [], []
    first = np.zeros(L, dtype=np.int64)
    last = np.zeros(L, dtype=np.int64)
    up, dn = [], []
    sens_end, sens_start = [], []
    for l in links:
        vf = max(5.0, l.vf_kmh) / 3.6  # m/s
        min_len = max(vf * dt, P.MIN_CELL_M)
        n = max(1, int(l.length_m // min_len))
        d = l.length_m / n
        q_lane = l.sat_pcu_h_lane / 3600.0  # PCU/s/lane
        kj = l.jam_pcu_km_lane / 1000.0  # PCU/m/lane
        kc = q_lane / vf
        w = q_lane / max(1e-9, kj - kc)
        c0 = len(dx)
        first[l.idx] = c0
        last[l.idx] = c0 + n - 1
        for c in range(n):
            cell_link.append(l.idx)
            dx.append(d)
            vr.append(min(1.0, vf * dt / d))
            wr.append(min(1.0, w * dt / d))
            qcap.append(q_lane * l.lanes * dt)
            ncap.append(kj * l.lanes * d)
            if c < n - 1:
                up.append(c0 + c)
                dn.append(c0 + c + 1)
        k_s = max(1, int(np.ceil(P.MP_SENSOR_M / d)))
        sens_end.append(np.arange(c0 + max(0, n - k_s), c0 + n))
        sens_start.append(np.arange(c0, c0 + min(n, k_s)))

    # movements
    mv_in, mv_out, mv_j, mv_turn = [], [], [], []
    for l in links:
        j = net.junctions[l.to_j]
        leg_in = j.leg_of(l.segment_id)
        heading_in = ((leg_in.bearing_deg if leg_in else 0.0) + 180.0) % 360.0
        exits = [b for b in j.out_links if links[b].segment_id != l.segment_id]
        if j.control == "boundary" or not j.out_links:
            exits = []
        elif not exits:
            exits = list(j.out_links)  # U-turn is the only way on
        for b in exits:
            leg_out = j.leg_of(links[b].segment_id)
            mv_in.append(l.idx)
            mv_out.append(b)
            mv_j.append(j.junction_id)
            mv_turn.append(angle_diff(heading_in, leg_out.bearing_deg if leg_out else heading_in))
        mv_in.append(l.idx)
        mv_out.append(-1)
        mv_j.append(j.junction_id)
        mv_turn.append(0.0)
    mv_in_a = np.asarray(mv_in, dtype=np.int64)
    order = np.argsort(mv_in_a, kind="stable")
    mv_in_a = mv_in_a[order]
    mv_out_a = np.asarray(mv_out, dtype=np.int64)[order]
    mv_j_a = np.asarray(mv_j, dtype=np.int64)[order]
    mv_turn_a = np.asarray(mv_turn, dtype=np.float64)[order]
    mv_start = np.searchsorted(mv_in_a, np.arange(L))

    # signal groups: one per (junction, movement label)
    groups: list[tuple[int, str]] = []
    gidx: dict[tuple[int, str], int] = {}
    for jid in net.signalised_ids:
        for lab in net.junctions[jid].program.labels:  # type: ignore[union-attr]
            gidx[(jid, lab)] = len(groups)
            groups.append((jid, lab))
    ones = len(groups)
    approach_group = np.full(L, ones, dtype=np.int64)
    vx_j, vx_g, vx_q = [], [], []
    for jid in net.signalised_ids:
        j = net.junctions[jid]
        for i, lab in j.approach_label.items():
            approach_group[i] = gidx.get((jid, lab), ones)
        if j.virtual_cross and (jid, "cross") in gidx:
            vx_j.append(jid)
            vx_g.append(gidx[(jid, "cross")])
            vx_q.append(P.SAT_FLOW_PCU_H_LANE[P.VIRTUAL_CROSS_CLASS] * P.VIRTUAL_CROSS_LANES / 3600.0 * dt)

    return Compiled(
        net=net,
        dt=float(dt),
        C=len(dx),
        cell_link=np.asarray(cell_link, dtype=np.int64),
        dx=np.asarray(dx),
        vr=np.asarray(vr),
        wr=np.asarray(wr),
        qcap=np.asarray(qcap),
        ncap=np.asarray(ncap),
        first=first,
        last=last,
        up=np.asarray(up, dtype=np.int64),
        dn=np.asarray(dn, dtype=np.int64),
        mv_in=mv_in_a,
        mv_out=mv_out_a,
        mv_junction=mv_j_a,
        mv_turn_deg=mv_turn_a,
        mv_start=mv_start.astype(np.int64),
        groups=groups,
        approach_group=approach_group,
        vx_junction=np.asarray(vx_j, dtype=np.int64),
        vx_group=np.asarray(vx_g, dtype=np.int64),
        vx_qcap=np.asarray(vx_q, dtype=np.float64),
        sens_end=sens_end,
        sens_start=sens_start,
    )


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------


@dataclass
class State:
    n: np.ndarray  # (K, C)
    srcq: np.ndarray  # (K, L)
    vxq: np.ndarray  # (K, X)

    def take(self, K: int) -> "State":
        """Broadcast a 1-candidate state to K candidates."""
        return State(
            np.repeat(self.n[:1], K, axis=0).copy(),
            np.repeat(self.srcq[:1], K, axis=0).copy(),
            np.repeat(self.vxq[:1], K, axis=0).copy(),
        )


@dataclass
class RunResult:
    K: int
    steps: int
    dt: float
    link_delay_vs: np.ndarray  # (K, L) veh-s of delay in the link's cells
    link_entry_delay_vs: np.ndarray  # (K, L) veh-s waiting to enter from side streets
    link_max_queue_m: np.ndarray  # (K, L)
    link_mean_queue_m: np.ndarray  # (K, L)
    link_spill_s: np.ndarray  # (K, L) seconds the queue reached the link's upstream end
    link_out_veh: np.ndarray  # (K, L) PCU that left the link at its junction
    vx_delay_vs: np.ndarray  # (K, X)
    vx_max_queue_m: np.ndarray  # (K, X)
    vx_out_veh: np.ndarray  # (K, X)
    exited_veh: np.ndarray  # (K,)
    entered_veh: np.ndarray  # (K,)
    series_t_min: np.ndarray  # (T,)
    series_link_queue_m: np.ndarray  # (K, T, L)
    series_vx_queue_m: np.ndarray  # (K, T, X)
    series_delayed_veh: np.ndarray  # (K, T)
    mp_splits: dict = field(default_factory=dict)
    final_state: State | None = None
    elapsed_s: float = 0.0


def _greens_matrix(cp: Compiled, plans: list[Plan], epoch0: int, t_start: float, steps: int) -> np.ndarray:
    """(K, steps, G+1) green fractions of every group; the last column is 1."""
    K, G = len(plans), len(cp.groups)
    out = np.ones((K, steps, G + 1))
    dt = cp.dt
    base_cache: dict[tuple[int, str], np.ndarray] = {}
    for gi, (jid, lab) in enumerate(cp.groups):
        prog = cp.net.junctions[jid].program
        base_cache[(jid, lab)] = step_greens(prog, lab, epoch0, t_start, steps, dt)  # type: ignore[arg-type]
        out[:, :, gi] = base_cache[(jid, lab)]
    for k, plan in enumerate(plans):
        for w in plan.windows:
            if w.kind != "fixed" or w.program is None:
                continue
            s0 = max(0, int(round((w.t0_s - t_start) / dt)))
            s1 = min(steps, int(round((w.t1_s - t_start) / dt)))
            if s1 <= s0:
                continue
            for gi, (jid, lab) in enumerate(cp.groups):
                if jid != w.junction_id:
                    continue
                g = step_greens(w.program, lab, epoch0, t_start + s0 * dt, s1 - s0, dt)
                out[k, s0:s1, gi] = g
    return out


def _bincount2(idx_flat: np.ndarray, vals: np.ndarray, K: int, n: int) -> np.ndarray:
    return np.bincount(idx_flat, weights=vals.ravel(), minlength=K * n).reshape(K, n)


def simulate(
    cp: Compiled,
    demand,  # demand.Demand
    plans: list[Plan],
    *,
    t_start_s: float,
    duration_s: float,
    epoch0: int,
    state: State | None = None,
    demand_scale: np.ndarray | None = None,
    series_every_s: float = 60.0,
) -> RunResult:
    """Run ``len(plans)`` candidates from ``state`` over [t_start, t_start + duration).

    ``t_start_s`` is measured from the demand's time origin (the start of the
    warm-up); plan windows are relative to ``demand.horizon_origin_s``.
    """
    import time as _time

    t_wall = _time.perf_counter()
    K = len(plans)
    L, X, dt = cp.L, cp.X, cp.dt
    steps = int(round(duration_s / dt))
    origin = demand.horizon_origin_s
    # plan windows are relative to the horizon origin: shift into run time
    shifted = [
        Plan(p.name, [type(w)(w.junction_id, w.t0_s + origin, w.t1_s + origin, w.kind, w.program) for w in p.windows], p.kind, p.description)
        for p in plans
    ]
    G1 = _greens_matrix(cp, shifted, epoch0, t_start_s, steps)
    scale = np.ones(K) if demand_scale is None else np.asarray(demand_scale, dtype=np.float64)

    if state is None:
        st = State(np.repeat(demand.n0[None, :], K, axis=0).copy(), np.zeros((K, L)), np.zeros((K, X)))
    elif state.n.shape[0] != K:
        st = state.take(K)
    else:
        st = State(state.n.copy(), state.srcq.copy(), state.vxq.copy())
    n, srcq, vxq = st.n, st.srcq, st.vxq

    vr, wr, qcap, ncap = cp.vr, cp.wr, cp.qcap, cp.ncap
    up, dn, first, last = cp.up, cp.dn, cp.first, cp.last
    beta = demand.beta
    mv_in, mv_out = cp.mv_in, cp.mv_out
    ns_mask = mv_out >= 0
    ns_idx = np.nonzero(ns_mask)[0]
    sink_idx = np.nonzero(~ns_mask)[0]
    mv_out_ns = mv_out[ns_mask]
    flat_ns = (mv_out_ns[None, :] + L * np.arange(K)[:, None]).ravel()
    flat_in = (mv_in[None, :] + L * np.arange(K)[:, None]).ravel()
    fifo_theta = np.array([1.0 / max(1, l.lanes) for l in cp.net.links])[None, :]
    link_starts = first  # cells are contiguous per link, in link order
    qcap_last = qcap[last]
    jam_lane_m = np.array([l.jam_pcu_km_lane / 1000.0 * l.lanes for l in cp.net.links])
    vx_jam_m = P.JAM_DENSITY_PCU_KM_LANE / 1000.0 * P.VIRTUAL_CROSS_LANES

    # max-pressure controllers
    mps: list[MaxPressureState] = []
    for k, plan in enumerate(shifted):
        for w in plan.windows:
            if w.kind == "max_pressure":
                prog = cp.net.junctions[w.junction_id].program
                mps.append(MaxPressureState(k, w.junction_id, w.t0_s, w.t1_s, prog))  # type: ignore[arg-type]
    gindex = {g: i for i, g in enumerate(cp.groups)}
    mp_meta = {}
    for jid in {m.junction_id for m in mps}:
        j = cp.net.junctions[jid]
        per_label: dict[str, list] = {}
        for a, lab in j.approach_label.items():
            outs = [(int(m), int(mv_out[m])) for m in range(cp.mv_start[a], cp.mv_start[a + 1] if a + 1 < L else len(mv_in)) if mv_out[m] >= 0]
            per_label.setdefault(lab, []).append((a, outs))
        vx = [x for x in range(X) if int(cp.vx_junction[x]) == jid]
        mp_meta[jid] = (per_label, vx)

    ncrit_all = qcap / vr  # PCU a cell holds at critical density (moving at capacity)

    def _occ(nk: np.ndarray, cells: np.ndarray) -> float:
        """Queue on the sensor cells: PCU above critical density, as a share of the room above it."""
        excess = np.maximum(0.0, nk[cells] - ncrit_all[cells]).sum()
        return float(excess / max(1e-9, (ncap[cells] - ncrit_all[cells]).sum()))

    def _pressures(m: MaxPressureState, nk: np.ndarray, vxk: np.ndarray) -> list[float]:
        per_label, vxs = mp_meta[m.junction_id]
        out = []
        for _, ms in m.program.phases:
            p = 0.0
            for lab in ms:
                for a, outs in per_label.get(lab, []):
                    down = sum(beta[mi] * _occ(nk, cp.sens_start[b]) for mi, b in outs)
                    p += cp.net.links[a].sat_pcu_h * (_occ(nk, cp.sens_end[a]) - down)
                if lab == "cross":
                    for x in vxs:
                        p += cp.vx_qcap[x] / dt * 3600.0 * (vxk[x] * dt / max(1e-9, vx_jam_m * P.VIRTUAL_CROSS_STORAGE_M))
            out.append(p)
        return out

    rec_every = max(1, int(round(series_every_s / dt)))
    T = steps // rec_every
    s_link_q = np.zeros((K, T, L))
    s_vx_q = np.zeros((K, T, X))
    s_delayed = np.zeros((K, T))

    link_delay = np.zeros((K, L))
    entry_delay = np.zeros((K, L))
    link_maxq = np.zeros((K, L))
    link_sumq = np.zeros((K, L))
    link_spill = np.zeros((K, L))
    link_out = np.zeros((K, L))
    vx_delay = np.zeros((K, X))
    vx_maxq = np.zeros((K, X))
    vx_out = np.zeros((K, X))
    exited = np.zeros(K)
    entered = np.zeros(K)
    out_c = np.zeros((K, cp.C))
    spill_thr = 0.25 * ncap[first]

    for s in range(steps):
        t = t_start_s + s * dt
        minute = min(int(t // 60.0), demand.lam.shape[0] - 1)
        g = G1[:, s, :]
        if mps:
            for m in mps:
                if not m.active(t):
                    continue
                fr = m.step(epoch0 + int(round(t)), dt, lambda m=m: _pressures(m, n[m.k], vxq[m.k]))
                for lab, frac in fr.items():
                    gi = gindex.get((m.junction_id, lab))
                    if gi is not None:
                        g[m.k, gi] = frac
        S_ = np.minimum(n * vr, qcap)
        R_ = np.minimum(qcap, wr * (ncap - n))
        y_int = np.minimum(S_[:, up], R_[:, dn])
        ga = g[:, cp.approach_group]
        Sa = np.minimum(S_[:, last], qcap_last * ga)
        d = Sa[:, mv_in] * beta
        Rb = R_[:, first]
        Db = _bincount2(flat_ns, d[:, ns_idx], K, L)
        fb = np.where(Db > Rb, Rb / np.maximum(Db, 1e-12), 1.0)
        fm = np.ones_like(d)
        fm[:, ns_idx] = fb[:, mv_out_ns]
        # partial FIFO: a blocked movement holds back 1/lanes of the approach
        phi = 1.0 - fifo_theta * (1.0 - np.minimum.reduceat(fm, cp.mv_start, axis=1))
        y_m = d * np.minimum(phi[:, mv_in], fm)
        J_out = _bincount2(flat_in, y_m, K, L)
        J_in = _bincount2(flat_ns, y_m[:, ns_idx], K, L)
        supply = np.maximum(0.0, Rb - J_in)
        srcq += demand.lam[minute][None, :] * scale[:, None]
        y_src = np.minimum(srcq, supply)
        srcq -= y_src
        if X:
            vxq += demand.lamx[minute][None, :] * scale[:, None]
            y_x = np.minimum(vxq, cp.vx_qcap[None, :] * g[:, cp.vx_group])
            vxq -= y_x
            vx_out += y_x
            exited += y_x.sum(axis=1)
        # delay: PCU in a cell that free flow would have moved on
        out_c[:, up] = y_int
        out_c[:, last] = J_out
        delayed = np.maximum(0.0, n - out_c / vr)
        dl = np.add.reduceat(delayed, link_starts, axis=1)
        link_delay += dl * dt
        entry_delay += srcq * dt
        qm = dl / jam_lane_m
        np.maximum(link_maxq, qm, out=link_maxq)
        link_sumq += qm
        link_spill += (delayed[:, first] > spill_thr) * dt
        link_out += J_out
        exited += y_m[:, sink_idx].sum(axis=1)
        entered += y_src.sum(axis=1)
        if X:
            vx_delay += vxq * dt
            vqm = vxq / vx_jam_m
            np.maximum(vx_maxq, vqm, out=vx_maxq)
        # update
        n[:, up] -= y_int
        n[:, dn] += y_int
        n[:, last] -= J_out
        n[:, first] += J_in + y_src
        if (s + 1) % rec_every == 0:
            ti = (s + 1) // rec_every - 1
            if ti < T:
                s_link_q[:, ti, :] = qm
                if X:
                    s_vx_q[:, ti, :] = vxq / vx_jam_m
                s_delayed[:, ti] = dl.sum(axis=1) + srcq.sum(axis=1) + (vxq.sum(axis=1) if X else 0.0)

    res = RunResult(
        K=K,
        steps=steps,
        dt=dt,
        link_delay_vs=link_delay,
        link_entry_delay_vs=entry_delay,
        link_max_queue_m=link_maxq,
        link_mean_queue_m=link_sumq / max(1, steps),
        link_spill_s=link_spill,
        link_out_veh=link_out,
        vx_delay_vs=vx_delay,
        vx_max_queue_m=vx_maxq,
        vx_out_veh=vx_out,
        exited_veh=exited,
        entered_veh=entered,
        series_t_min=(np.arange(T) + 1) * rec_every * dt / 60.0 + (t_start_s - origin) / 60.0,
        series_link_queue_m=s_link_q,
        series_vx_queue_m=s_vx_q,
        series_delayed_veh=s_delayed,
        mp_splits={(m.k, m.junction_id): m.history for m in mps},
        final_state=State(n, srcq, vxq),
    )
    res.elapsed_s = _time.perf_counter() - t_wall
    return res

