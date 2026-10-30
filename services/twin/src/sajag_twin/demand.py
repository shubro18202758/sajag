"""Demand for the twin: a deterministic Mumbai profile, or the live state.

Every link gets a *target flow* for each minute of the run:

    target = v/c * time-of-day * directional factor * effective capacity

where effective capacity is the link's saturation flow times the green
share of the movement serving it at its downstream signal (1 elsewhere).

* **SIMULATED** (default): v/c from :data:`params.PEAK_VC` by road class and
  the assumed weekday profile below. It is an assumption, not a measurement.
* **LIVE / EMULATED**: the traffic-oracle's latest congestion index per
  segment (read-only GET) is read as a v/c proxy for the first minute and
  then follows the same time-of-day shape. The label is EMULATED when the
  oracle marks its rows synthetic.

Turning ratios at each junction weight straight-on above turns and favour
busier exits; a fixed share leaves to side streets. The side-street
entry rate of each link is then chosen so the link's flow matches its
target in steady state: ``entry = max(0, target - inflow from upstream)``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import numpy as np

from sajag_twin import params as P
from sajag_twin.ctm import Compiled

__all__ = ["Demand", "Forecast", "IST", "build_demand", "tod_factor"]

IST = timezone(timedelta(hours=5, minutes=30))

#: Assumed weekday time-of-day profile (IST hour -> factor; 1.0 = evening
#: peak). SIMULATED: a plausible shape (office hours around 10:00-18:00,
#: evening peak 17:30-19:30), not a count.
_TOD_POINTS: list[tuple[float, float]] = [
    (0.0, 0.25), (5.0, 0.25), (7.0, 0.55), (9.0, 0.85), (10.5, 0.95), (12.0, 0.85),
    (14.0, 0.80), (16.0, 0.88), (17.5, 1.00), (19.5, 1.00), (21.0, 0.80), (22.5, 0.50),
    (24.0, 0.25),
]


def tod_factor(hour: float) -> float:
    h = hour % 24.0
    for (h0, f0), (h1, f1) in zip(_TOD_POINTS, _TOD_POINTS[1:]):
        if h0 <= h <= h1:
            return f0 + (f1 - f0) * (h - h0) / (h1 - h0)
    return _TOD_POINTS[-1][1]


def _dir_weight(hour: float) -> float:
    """+1 in the evening peak (outbound heavier), -1 in the morning, 0 between."""
    h = hour % 24.0

    def bump(c: float, half: float) -> float:
        return max(0.0, 1.0 - abs(h - c) / half)

    return bump(18.5, 2.5) - bump(10.0, 2.5)


@dataclass(frozen=True)
class Forecast:
    """A forecast crossing passed in a request: the approaches of a junction
    (or a set of segments) reach ``vc`` in ``in_min`` minutes."""

    vc: float
    in_min: float
    junction_id: int | None = None
    segment_ids: tuple[int, ...] = ()
    source: str = "forecast"


@dataclass
class Demand:
    beta: np.ndarray  # (M,)
    lam: np.ndarray  # (minutes, L) PCU per step entering each link from side streets
    lamx: np.ndarray  # (minutes, X) PCU per step arriving on virtual cross streets
    target_pcu_h: np.ndarray  # (minutes, L)
    n0: np.ndarray  # (C,)
    horizon_origin_s: float  # where the measured horizon starts (end of warm-up)
    start: datetime
    source: str  # simulated-profile | live | emulated-feed
    label: str  # SIMULATED | LIVE | EMULATED
    coverage: float = 0.0
    notes: list[str] = field(default_factory=list)

    @property
    def minutes(self) -> int:
        return int(self.lam.shape[0])

    def scaled(self, factor: float) -> "Demand":
        return Demand(
            self.beta, self.lam * factor, self.lamx * factor, self.target_pcu_h * factor, self.n0 * min(1.0, factor),
            self.horizon_origin_s, self.start, self.source, self.label, self.coverage, list(self.notes),
        )

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "label": self.label,
            "start_ist": self.start.astimezone(IST).isoformat(timespec="minutes"),
            "warmup_min": round(self.horizon_origin_s / 60.0, 1),
            "live_coverage": round(self.coverage, 3),
            "tod_factor_at_start": round(tod_factor(_hour(self.start)), 3),
            "notes": list(self.notes),
        }


def _hour(t: datetime) -> float:
    lt = t.astimezone(IST)
    return lt.hour + lt.minute / 60.0 + lt.second / 3600.0


def effective_capacity(cp: Compiled) -> np.ndarray:
    """PCU/h each link can discharge at its downstream end under the base program."""
    net = cp.net
    cap = np.array([l.sat_pcu_h for l in net.links])
    for jid in net.signalised_ids:
        j = net.junctions[jid]
        for i, lab in j.approach_label.items():
            cap[i] *= j.program.green_ratio(lab)  # type: ignore[union-attr]
    return cap


def build_demand(
    cp: Compiled,
    *,
    start: datetime,
    horizon_min: float,
    warmup_min: float = P.WARMUP_MIN,
    live_ci: dict[int, float] | None = None,
    live_label: str = "LIVE",
    forecasts: list[Forecast] | None = None,
    scale: float = 1.0,
) -> Demand:
    net = cp.net
    L = cp.L
    total_min = int(math.ceil(warmup_min + horizon_min)) + 1
    t0 = start - timedelta(minutes=warmup_min)
    cap_eff = effective_capacity(cp)
    vc_class = np.array([P.PEAK_VC.get(l.road_class, 0.6) for l in net.links])
    cbd = np.array([l.cbd_sign for l in net.links])
    notes: list[str] = []

    # live v/c (first minute) where the oracle covers a segment
    coverage = 0.0
    vc_live = np.full(L, np.nan)
    source, label = "simulated-profile", "SIMULATED"
    if live_ci:
        segs = {l.segment_id for l in net.links}
        hit = {s: ci for s, ci in live_ci.items() if s in segs}
        coverage = len(hit) / max(1, len(segs))
        if coverage >= P.LIVE_MIN_COVERAGE:
            for l in net.links:
                if l.segment_id in hit:
                    vc_live[l.idx] = float(np.clip(hit[l.segment_id] * P.LIVE_CI_TO_VC, P.LIVE_VC_MIN, P.LIVE_VC_MAX))
            source = "live" if live_label == "LIVE" else "emulated-feed"
            label = live_label
            notes.append(
                f"Live congestion index read as a v/c proxy on {len(hit)} of {len(segs)} segments; "
                "the rest follow the simulated profile."
            )
        else:
            notes.append(f"Live state covers {coverage:.0%} of segments; the simulated profile is used.")
    if label == "SIMULATED":
        notes.append("Demand is the assumed Mumbai weekday profile (SIMULATED), not counts.")

    hours = np.array([_hour(t0 + timedelta(minutes=m)) for m in range(total_min)])
    tod = np.array([tod_factor(h) for h in hours])
    dirw = np.array([_dir_weight(h) for h in hours])
    # (minutes, L)
    vc = np.repeat(vc_class[None, :], total_min, axis=0) * tod[:, None]
    vc = vc * (1.0 + P.DIRECTIONAL_SPLIT * dirw[:, None] * cbd[None, :])
    if label != "SIMULATED":
        tod_ref = tod_factor(_hour(start))
        live_rows = np.isfinite(vc_live)
        vc[:, live_rows] = vc_live[live_rows][None, :] * (tod[:, None] / max(1e-6, tod_ref))
    for fc in forecasts or []:
        # junction only: all its approaches; segments only: both directions;
        # both: the junction's approaches on those segments
        seg_links = set()
        for sid in fc.segment_ids:
            seg_links |= set(net.links_of_segment(sid))
        if fc.junction_id is not None and fc.junction_id in net.junctions:
            links = set(net.junctions[fc.junction_id].in_links)
            if seg_links:
                links &= seg_links
        else:
            links = seg_links
        if not links:
            continue
        idx = np.array(sorted(links))
        m_start = int(round(warmup_min))
        ramp = np.clip((np.arange(total_min) - m_start) / max(1.0, fc.in_min), 0.0, 1.0)
        now_vc = vc[m_start, idx]
        target = np.maximum(now_vc, fc.vc)
        vc[:, idx] = vc[:, idx] + (target - now_vc)[None, :] * ramp[:, None]
        notes.append(
            f"Forecast applied: {len(idx)} approach link(s) ramp to v/c {fc.vc:.2f} in {fc.in_min:.0f} min ({fc.source})."
        )
    target = vc * cap_eff[None, :] * scale  # PCU/h

    # turning ratios from the reference minute (start of the measured horizon)
    ref = target[min(int(round(warmup_min)), total_min - 1)]
    beta = balance_turns(cp, ref)

    # transfer matrix M[a, b] = beta(a->b); entry = max(0, target - inflow)
    Mt = np.zeros((L, L))
    ns = cp.mv_out >= 0
    np.add.at(Mt, (cp.mv_in[ns], cp.mv_out[ns]), beta[ns])
    inflow = target @ Mt
    entry = np.maximum(0.0, target - inflow)  # PCU/h
    lam = entry * cp.dt / 3600.0

    # virtual cross streets: v/c of the cross street under the base program
    X = cp.X
    lamx = np.zeros((total_min, X))
    for x in range(X):
        jid = int(cp.vx_junction[x])
        gr = net.junctions[jid].program.green_ratio("cross")  # type: ignore[union-attr]
        sat = float(cp.vx_qcap[x]) / cp.dt * 3600.0
        lamx[:, x] = P.VIRTUAL_CROSS_VC * tod * sat * gr * scale * cp.dt / 3600.0
    if X:
        notes.append(f"{X} crossing(s) have a virtual cross street (cross road not in the network).")

    # initial state: free-flow density of the realised steady flow
    try:
        flow0 = np.linalg.solve(np.eye(L) - Mt.T, entry[0])
    except np.linalg.LinAlgError:
        flow0 = target[0]
    flow0 = np.clip(flow0, 0.0, None)
    vf = np.array([max(5.0, l.vf_kmh) for l in net.links])  # km/h
    k_ff = flow0 / vf / 1000.0  # PCU per m
    n0 = k_ff[cp.cell_link] * cp.dx
    ncrit = cp.qcap / cp.vr
    n0 = np.minimum(n0, ncrit)

    return Demand(
        beta=beta,
        lam=lam,
        lamx=lamx,
        target_pcu_h=target,
        n0=n0,
        horizon_origin_s=float(warmup_min * 60.0),
        start=start,
        source=source,
        label=label,
        coverage=coverage,
        notes=notes,
    )


def balance_turns(cp: Compiled, ref: np.ndarray, iters: int = 60) -> np.ndarray:
    """Turning ratios consistent with the target flows ``ref`` (PCU/h).

    Per junction, a turning-flow matrix T[a, b] (arriving link a -> leaving
    link b) is fitted by biproportional (Furness) balancing from the seed
    weights (straight 1.0, turn 0.6, no U-turn), so that row sums are the
    arriving flow less the side-street exit share and column sums are the
    leaving flow (scaled to the smaller total; the difference enters or
    leaves through side streets). In steady state every link then carries
    its target flow, so a small mismatch is not amplified by the traffic
    that circulates through the network.
    """
    net = cp.net
    L = cp.L
    beta = np.zeros(cp.M)
    by_junction: dict[int, list[int]] = {}
    for m in range(cp.M):
        by_junction.setdefault(int(cp.mv_junction[m]), []).append(m)
    for jid, mvs in by_junction.items():
        j = net.junctions[jid]
        exits = [m for m in mvs if cp.mv_out[m] >= 0]
        if not exits:
            for m in mvs:
                beta[m] = 1.0
            continue
        ins = sorted({int(cp.mv_in[m]) for m in mvs})
        outs = sorted({int(cp.mv_out[m]) for m in exits})
        ri = {a: i for i, a in enumerate(ins)}
        ci = {b: i for i, b in enumerate(outs)}
        seed = np.zeros((len(ins), len(outs)))
        for m in exits:
            w = P.STRAIGHT_WEIGHT if cp.mv_turn_deg[m] < P.STRAIGHT_MAX_DEG else P.TURN_WEIGHT
            seed[ri[int(cp.mv_in[m])], ci[int(cp.mv_out[m])]] = w
        exit_share = P.SIDE_STREET_EXIT_SHARE
        if j.control == "uncontrolled" and len(j.legs) == 2:
            exit_share = P.SIDE_STREET_EXIT_SHARE / 3.0  # a plain continuation loses less
        row_t = np.array([(1.0 - exit_share) * max(1.0, ref[a]) for a in ins])
        col_t = np.array([max(1.0, ref[b]) for b in outs])
        total = min(row_t.sum(), col_t.sum())
        row_t *= total / row_t.sum()
        col_t *= total / col_t.sum()
        T = seed.copy()
        for _ in range(iters):
            rs = T.sum(axis=1)
            T *= np.where(rs > 0, row_t / np.maximum(rs, 1e-12), 0.0)[:, None]
            cs = T.sum(axis=0)
            T *= np.where(cs > 0, col_t / np.maximum(cs, 1e-12), 0.0)[None, :]
        # rows may now exceed their targets slightly; never let them exceed the arriving flow
        rs = T.sum(axis=1)
        cap = np.array([(1.0 - 1e-6) * max(1.0, ref[a]) for a in ins])
        T *= np.minimum(1.0, cap / np.maximum(rs, 1e-12))[:, None]
        for m in mvs:
            a = int(cp.mv_in[m])
            fa = max(1.0, ref[a])
            if cp.mv_out[m] >= 0:
                beta[m] = T[ri[a], ci[int(cp.mv_out[m])]] / fa
        for m in mvs:
            if cp.mv_out[m] < 0:
                a = int(cp.mv_in[m])
                beta[m] = max(0.0, 1.0 - T[ri[a]].sum() / max(1.0, ref[a]))
    del L
    return beta


def parse_start(value: str | None, now: datetime | None = None) -> datetime:
    """'HH:MM' (IST, today), an ISO datetime, or None (now)."""
    now = now or datetime.now(tz=IST)
    if not value:
        return now.astimezone(IST).replace(second=0, microsecond=0)
    v = value.strip()
    if len(v) <= 5 and ":" in v:
        hh, mm = v.split(":", 1)
        base = now.astimezone(IST)
        return base.replace(hour=int(hh) % 24, minute=int(mm) % 60, second=0, microsecond=0)
    dt = datetime.fromisoformat(v)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=IST)
    return dt
