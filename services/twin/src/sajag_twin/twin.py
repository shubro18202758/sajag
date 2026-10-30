"""The twin: one compiled network plus the helpers every endpoint shares."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import datetime

import numpy as np

from sajag_twin import params as P
from sajag_twin.ctm import Compiled, RunResult, State, compile_network, simulate
from sajag_twin.demand import Demand, Forecast, build_demand
from sajag_twin.metrics import Focus, candidate_metrics, compare, series_for
from sajag_twin.network import Network, Program, load_network
from sajag_twin.oracle_client import OracleClient
from sajag_twin.signals import Plan, Window, validate_plan
from sajag_twin.webster import WebsterResult, webster

__all__ = ["Scenario", "Twin"]


@dataclass
class Scenario:
    demand: Demand
    epoch0: int  # epoch of the demand origin (start of warm-up)
    warm: State
    horizon_s: float
    warm_elapsed_s: float


class Twin:
    def __init__(self, net: Network, oracle: OracleClient | None = None, dt: float = P.DT_S):
        self.net = net
        self.cp: Compiled = compile_network(net, dt)
        self.oracle = oracle or OracleClient(None)
        self._lock = threading.Lock()  # numpy runs are CPU-bound; one at a time

    @classmethod
    def from_path(cls, path: str | None, oracle: OracleClient | None = None) -> "Twin":
        return cls(load_network(path), oracle)

    # -- demand -----------------------------------------------------------
    def bbox(self) -> tuple[float, float, float, float]:
        lons = [j.lon for j in self.net.junctions.values()]
        lats = [j.lat for j in self.net.junctions.values()]
        pad = 0.01
        return (min(lons) - pad, min(lats) - pad, max(lons) + pad, max(lats) + pad)

    def build_demand(
        self,
        start: datetime,
        horizon_min: float,
        *,
        mode: str = "auto",
        forecasts: list[Forecast] | None = None,
        scale: float = 1.0,
    ) -> Demand:
        live = None
        if mode in ("auto", "live") and self.oracle.enabled:
            live = self.oracle.snapshot(self.bbox())
        dem = build_demand(
            self.cp,
            start=start,
            horizon_min=horizon_min,
            live_ci=live.congestion if live else None,
            live_label=live.label if live else "LIVE",
            forecasts=forecasts,
            scale=scale,
        )
        if mode == "live" and dem.label == "SIMULATED":
            dem.notes.append("Live state was requested but is not available; SIMULATED profile used.")
        return dem

    def scenario(self, demand: Demand, horizon_min: float) -> Scenario:
        epoch0 = int(demand.start.timestamp()) - int(demand.horizon_origin_s)
        t = time.perf_counter()
        with self._lock:
            warm = simulate(self.cp, demand, [Plan("do nothing")], t_start_s=0.0, duration_s=demand.horizon_origin_s, epoch0=epoch0)
        return Scenario(demand, epoch0, warm.final_state, horizon_min * 60.0, time.perf_counter() - t)  # type: ignore[arg-type]

    def run(self, sc: Scenario, plans: list[Plan], demand_scale: np.ndarray | None = None) -> RunResult:
        for p in plans:
            validate_plan(self.net, p)
        with self._lock:
            return simulate(
                self.cp,
                sc.demand,
                plans,
                t_start_s=sc.demand.horizon_origin_s,
                duration_s=sc.horizon_s,
                epoch0=sc.epoch0,
                state=sc.warm,
                demand_scale=demand_scale,
            )

    # -- per-junction views ----------------------------------------------
    def critical_flows(self, demand: Demand, jid: int) -> dict[str, tuple[float, float]]:
        """Per movement label: (q, s) PCU/h of the critical approach at the horizon start."""
        j = self.net.junctions[jid]
        ref = demand.target_pcu_h[min(int(round(demand.horizon_origin_s / 60.0)), demand.minutes - 1)]
        crit: dict[str, tuple[float, float]] = {}
        for li, lab in j.approach_label.items():
            q, s = float(ref[li]), float(self.net.links[li].sat_pcu_h)
            if lab not in crit or q / s > crit[lab][0] / crit[lab][1]:
                crit[lab] = (q, s)
        for x in range(self.cp.X):
            if int(self.cp.vx_junction[x]) == jid:
                m = min(int(round(demand.horizon_origin_s / 60.0)), demand.minutes - 1)
                q = float(demand.lamx[m, x]) * 3600.0 / self.cp.dt
                s = float(self.cp.vx_qcap[x]) * 3600.0 / self.cp.dt
                if "cross" not in crit or q / s > crit["cross"][0] / crit["cross"][1]:
                    crit["cross"] = (q, s)
        return crit

    def webster_for(self, demand: Demand, jid: int) -> WebsterResult:
        j = self.net.junctions[jid]
        assert j.program is not None
        return webster(j.program, self.critical_flows(demand, jid))

    def approach_vc(self, demand: Demand, jid: int) -> dict[str, float]:
        """Peak v/c over the horizon of each movement label's critical approach."""
        j = self.net.junctions[jid]
        h0 = int(round(demand.horizon_origin_s / 60.0))
        out: dict[str, float] = {}
        for li, lab in j.approach_label.items():
            cap = self.net.links[li].sat_pcu_h * (j.program.green_ratio(lab) if j.program else 1.0)
            vc = float(demand.target_pcu_h[h0:, li].max()) / max(1.0, cap)
            out[lab] = max(out.get(lab, 0.0), vc)
        return out

    def metrics(self, res: RunResult, focus: Focus) -> list[dict]:
        return [candidate_metrics(self.cp, res, k, focus) for k in range(res.K)]

    def describe(self) -> dict:
        d = self.net.summary()
        d.update(self.cp.summary())
        return d


def fixed_window(jid: int, prog: Program, minutes: float) -> Window:
    return Window(jid, 0.0, minutes * 60.0, "fixed", prog)


def mp_window(jid: int, minutes: float) -> Window:
    return Window(jid, 0.0, minutes * 60.0, "max_pressure", None)


__all__ += ["compare", "series_for", "fixed_window", "mp_window"]
