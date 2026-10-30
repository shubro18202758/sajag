"""The wargame (C-U): each COA against how the city's traffic reacts — an outcome DISTRIBUTION, not a point.

Two methods, labelled on every outcome and on ``provenance.wargame_method``:

* ``"twin+cascade"`` — the closure and diversion COAs run on Sajag's seeded corridor twin, **unchanged**
  (``simulation/router.py`` ``simulate_twin``, in-process, holding the C7 shared twin gate exactly as the HTTP
  route's dependency does) over the event's route segments with the COA's ``closure_policy`` (``full_closure``,
  horizon ≤ 60, ≤ 20 replications, the DSS seed).  The twin measures a closure PASS (its convoy-style rolling
  closure lasts the time to traverse the route); the DSS projects each replication to the COA's own closure time
  by the point-queue law (a full closure's delay grows with the square of its duration) and says so.  The COAs
  the twin cannot express (lane loss, advisories, dispatches, signal priority) keep the seeded surrogate's
  disruption.  EVERY COA's spillover, neighbourhoods, parallel routes, affected segments and 108 delay come from
  the DSS-layer cascade (``cascade.py``).
* ``"surrogate"`` — when the twin or the road graph is unavailable (or the subject has no road): the PoC's seeded
  Monte-Carlo surrogate (240 replications, ``prototype/dss.py`` ``wargame``) for everything, ported so the seeded
  run reproduces the PoC's numbers on its segment model.

The surrogate is written for the PoC's three-lane reference carriageway; on a road with ``L`` lanes it counts a
blocked lane as ``3/L`` reference lanes and scales its demand-normalised constants by ``demand / 2800`` — the
identity on the PoC's segment.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import numpy as np
import structlog

from traffic_oracle.decision_support.cascade import CascadeNetwork, CascadeOutcome, run_cascade
from traffic_oracle.decision_support.coa import CoaDraft

logger = structlog.get_logger(__name__)

__all__ = [
    "SURROGATE_REPLICATIONS",
    "TWIN_MAX_HORIZON_MIN",
    "TWIN_REPLICATIONS",
    "SegmentModel",
    "WargameResult",
    "resolve_lanes",
    "surrogate",
    "surrogate_wargame",
    "twin_cascade_wargame",
    "twin_disruption",
]

SURROGATE_REPLICATIONS = 240
TWIN_REPLICATIONS = 20
TWIN_MAX_HORIZON_MIN = 60
#: the PoC's reference carriageway and demand (its 2600 / 1500 normalisers are relative to these)
REFERENCE_LANES = 3
REFERENCE_DEMAND_VEH_H = 2800.0
DISRUPTION_SCALE_VH = 2600.0
SPILLOVER_SCALE_VH = 1500.0
SIGNAL_PRIORITY_FACTOR = 0.82

SURROGATE_METHOD = (
    "DSS Monte-Carlo surrogate (SIMULATED, %d replications, seeded); the per-COA demand, capacity and "
    "clearance draws of the PoC wargame on %s"
)


@dataclass(frozen=True)
class SegmentModel:
    """The arterial the wargame plays on (the PoC's ``SEGMENTS`` entry), from the twin's network, a fixture,
    or — for an area-level report — a notional arterial, labelled by ``source``."""

    segment_id: int | None
    name: str
    road_class: str
    lanes: int
    base_demand_veh_h: float
    free_speed_kmh: float
    length_km: float
    parallel_routes: tuple[str, ...] = ()
    neighbours: tuple[str, ...] = ()
    source: str = "twin-network"

    @property
    def demand_ratio(self) -> float:
        return max(self.base_demand_veh_h, 1.0) / REFERENCE_DEMAND_VEH_H

    @property
    def disruption_scale(self) -> float:
        return DISRUPTION_SCALE_VH * self.demand_ratio

    @property
    def spillover_scale(self) -> float:
        return SPILLOVER_SCALE_VH * self.demand_ratio

    def lane_equivalents(self, lanes_blocked: int) -> float:
        """Blocked lanes counted on the PoC's three-lane reference carriageway."""
        return lanes_blocked * REFERENCE_LANES / max(1, self.lanes)

    @classmethod
    def from_doc(cls, doc: dict[str, Any]) -> SegmentModel:
        return cls(
            segment_id=doc.get("segment_id"),
            name=str(doc["name"]),
            road_class=str(doc.get("road_class", "primary")),
            lanes=int(doc["lanes"]),
            base_demand_veh_h=float(doc["base_demand_veh_h"]),
            free_speed_kmh=float(doc.get("free_speed_kmh", 50)),
            length_km=float(doc.get("length_km", 1.0)),
            parallel_routes=tuple(doc.get("parallel_routes") or ()),
            neighbours=tuple(doc.get("neighbours") or ()),
            source=str(doc.get("source", "fixture")),
        )


def resolve_lanes(lanes_blocked: int | str, lanes: int) -> int:
    if lanes_blocked == "all":
        return max(1, lanes)
    return min(int(lanes_blocked), max(1, lanes))


@dataclass
class WargameResult:
    outcomes: dict[str, dict[str, Any]]
    sim_runs: list[dict[str, Any]]
    method: str
    notes: list[str] = field(default_factory=list)
    #: live closures the cascade's reassignment was computed without (``twin+cascade`` only), and those of them
    #: that lie on an alternative the reassignment would otherwise use
    closures_excluded: tuple[int, ...] = ()
    closures_on_alternatives: tuple[int, ...] = ()


def surrogate(
    draft: CoaDraft,
    seg: SegmentModel,
    *,
    seed: int,
    ambulance_eta_sec: float | None,
    reps: int = SURROGATE_REPLICATIONS,
) -> dict[str, Any]:
    """The PoC's ``wargame()``: seeded demand, clearance-duration and capacity draws → disruption and spillover
    distributions (mean + SAMPLED p90, so p90/mean varies per COA), the touched neighbourhoods, the response time
    and the 108 impact.  Returns a C-U ``predicted_outcome`` plus the raw ``_metrics``."""
    eff = draft.effects
    rng = np.random.default_rng(int(seed) + draft.index * 7919)
    lanes = max(1, seg.lanes)
    lb = resolve_lanes(eff.lanes_blocked, lanes)
    lane_eq = seg.lane_equivalents(lb)
    dur_h = eff.active_min / 60.0
    mean_demand = seg.base_demand_veh_h
    base_cap = max(0.05, (lanes - lb) / lanes) * eff.capacity_factor
    deficit = max(0.0, 1.0 - base_cap)
    n_alt = max(1, len(seg.parallel_routes))
    sig_dur = 0.10 + 0.05 * lane_eq + (0.06 if draft.closure else 0.0)
    disr = np.empty(reps)
    spill = np.empty(reps)
    for r in range(reps):
        demand = mean_demand * rng.normal(1.0, 0.08)
        dur = max(0.05, dur_h * rng.lognormal(0.0, sig_dur))
        cap_noise = rng.normal(1.0, 0.06)
        overflow = max(0.0, demand * deficit * cap_noise)
        disr[r] = overflow * dur * 0.9 + deficit * demand * dur * 0.15
        spill[r] = overflow * dur * 0.6 / (1.0 + 0.4 * (n_alt - 1))
    mean_vh = float(disr.mean())
    p90_vh = float(np.percentile(disr, 90))
    spill_mean = float(spill.mean())
    spill_p90 = float(np.percentile(spill, 90))
    n_nbhd = 0 if lb == 0 else min(len(seg.neighbours), int(round(lane_eq)) + 1)
    resp = None
    if draft.dispatch_108 and ambulance_eta_sec is not None:
        resp = float(ambulance_eta_sec)
        if draft.signal_priority:
            resp = float(int(resp * SIGNAL_PRIORITY_FACTOR))
    # the 108 delay is the COA's OWN 108's (HON-9): a COA that dispatches no 108 has none to delay or speed up —
    # the PoC applied +180 s / -60 s to every closure / signal-priority COA, a 108 or not (the cascade gates it)
    amb_delay = 0
    if draft.dispatch_108:
        if lb >= lanes and not eff.emergency_lane:
            amb_delay = 180
        elif draft.signal_priority:
            amb_delay = -60
    units = draft.responder_units
    resolution = 0.30
    resolution += 0.30 if units >= 1 else 0.0
    resolution += 0.20 if draft.dispatch_108 else 0.0
    resolution += 0.12 if units >= 2 else 0.0
    resolution += 0.08 if eff.advisory else 0.0
    resolution = min(0.97, resolution)
    return {
        "response_time_to_scene_sec": resp,
        "total_disruption_vehicle_hours": {
            "mean": round(mean_vh, 1),
            "p90": round(p90_vh, 1),
            "p90_mean_ratio": round(p90_vh / mean_vh, 3) if mean_vh > 1 else None,
            "replications": reps,
        },
        "cascade": {
            "spillover_vehicle_hours": {"mean": round(spill_mean, 1), "p90": round(spill_p90, 1)},
            "neighbourhoods_touched": list(seg.neighbours[:n_nbhd]),
            "parallel_routes_loaded": list(seg.parallel_routes) if lb else [],
            "affected_segment_ids": [seg.segment_id] if (lb and seg.segment_id) else [],
        },
        "emergency_impact": {"ambulance_delay_sec": amb_delay, "green_corridor_ok": amb_delay <= 0},
        "time_to_effect_sec": eff.time_to_effect_sec,
        "event_resolution_prob": round(resolution, 2),
        "method": SURROGATE_METHOD % (reps, seg.name if seg.source != "area-notional" else
                                      "a notional arterial (area-level report: no road anchor)"),
        "_metrics": {
            "lanes_blocked": lb,
            "deficit": round(deficit, 4),
            "disruption_vh": {"mean": round(mean_vh, 3), "p90": round(p90_vh, 3)},
            "spillover_vh": {"mean": round(spill_mean, 3), "p90": round(spill_p90, 3)},
        },
    }


def _run_row(coa_id: str, method: str, seed: int, metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "coa_id": coa_id,
        "sim_run_id": f"{method}:{coa_id}:{seed}",
        "method": method,
        "seed": int(seed),
        "metrics": metrics,
    }


def surrogate_wargame(
    drafts: Sequence[CoaDraft], seg: SegmentModel, *, seed: int, ambulance_eta_sec: float | None
) -> WargameResult:
    outcomes: dict[str, dict[str, Any]] = {}
    runs: list[dict[str, Any]] = []
    for d in drafts:
        out = surrogate(d, seg, seed=seed, ambulance_eta_sec=ambulance_eta_sec)
        metrics = out.pop("_metrics")
        outcomes[d.coa_id] = out
        runs.append(_run_row(d.coa_id, "surrogate", seed, metrics))
    return WargameResult(outcomes, runs, "surrogate")


async def twin_disruption(
    request: Any,
    route: Sequence[int],
    draft: CoaDraft,
    *,
    seed: int,
    horizon_min: int,
    now: datetime | None = None,
) -> dict[str, Any]:
    """One closure/diversion COA on the seeded corridor twin, unchanged: ``simulate_twin`` in-process, holding
    the C7 shared gate as ``Depends(twin_in_flight)`` does for the HTTP route.  Each replication's closure-pass
    disruption is projected to the COA's closure time (point-queue law, ``(T_coa / T_pass)²``).  The twin departs
    at the generation's ``now`` (the surrogate's time of day too), so a given subject, time and seed reproduce."""
    from traffic_oracle.signals.gate import signal_policy_gate  # noqa: PLC0415 — the twin seam is lazy
    from traffic_oracle.simulation.router import (  # noqa: PLC0415
        ClosurePolicyModel,
        TwinSimRequest,
        simulate_twin,
    )

    closure_sec = float(draft.effects.active_min) * 60.0
    req = TwinSimRequest(
        route_segment_ids=[int(s) for s in route][:64],
        departure_time=now or datetime.now(UTC),
        closure_policy=ClosurePolicyModel(
            advance_closure_sec=int(min(1800, closure_sec)), closure_type="full_closure"
        ),
        horizon_min=max(1, min(TWIN_MAX_HORIZON_MIN, int(horizon_min))),
        n_replications=TWIN_REPLICATIONS,
        seed=int(seed),
    )
    async with signal_policy_gate.shared():
        resp = await simulate_twin(req, request)
    runs = resp.get("runs") or []
    if not runs:
        raise ValueError("the twin returned no replication")
    projected: list[float] = []
    for r in runs:
        t_pass = max(1.0, float(r.get("avg_closure_duration_sec") or 0.0))
        projected.append(float(r["total_disruption_vehicle_hours"]) * (closure_sec / t_pass) ** 2)
    arr = np.array(projected)
    raw = np.array([float(r["total_disruption_vehicle_hours"]) for r in runs])
    mean = float(arr.mean())
    p90 = float(np.percentile(arr, 90))
    route_cov = resp.get("route_coverage") or {}
    return {
        "mean": mean,
        "p90": p90,
        "replications": len(runs),
        "metrics": {
            "route_segment_ids": [int(s) for s in route],
            "closure_policy": resp.get("closure_policy"),
            "horizon_min": resp.get("horizon_min"),
            "replications": len(runs),
            "closure_pass_sec_mean": round(float(np.mean([r.get("avg_closure_duration_sec") or 0 for r in runs])), 1),
            "closure_pass_disruption_vh": {"mean": round(float(raw.mean()), 3),
                                           "p90": round(float(np.percentile(raw, 90)), 3)},
            "projected_disruption_vh": {"mean": round(mean, 3), "p90": round(p90, 3)},
            "projection": "point-queue (T_coa / T_pass)^2",
            "ambulance_delay_sec_mean": round(float(np.mean([r.get("ambulance_delay_sec") or 0 for r in runs])), 1),
            "censored_runs": resp.get("censored_runs"),
            "route_coverage": route_cov,
            "calibrated": resp.get("calibrated"),
            "forecast_coupling": resp.get("forecast_coupling"),
        },
    }


def _why_surrogate(draft: CoaDraft, lanes: int) -> str:
    """Why a COA's disruption comes from the surrogate, naming only what this COA actually has."""
    has: list[str] = []
    if resolve_lanes(draft.effects.lanes_blocked, lanes) > 0:
        has.append("lane loss")
    verbs = set(draft.verbs())
    for verb, words in (("advisory", "advisory"), ("dispatch", "dispatch"), ("signal_hold", "signal priority")):
        if verb in verbs:
            has.append(words)
    if not has:
        return "no closure or diversion, so there is nothing for the twin to run"
    named = has[0] if len(has) == 1 else ", ".join(has[:-1]) + " and " + has[-1]
    return f"no closure or diversion, and the twin cannot express this COA's {named}"


async def twin_cascade_wargame(
    drafts: Sequence[CoaDraft],
    seg: SegmentModel,
    net: CascadeNetwork,
    *,
    request: Any,
    seed: int,
    horizon_min: int,
    ambulance_eta_sec: float | None,
    live_108_segments: Sequence[int] = (),
    twin: Any = None,
    now: datetime | None = None,
) -> WargameResult:
    """Twin for the closure/diversion COAs, the surrogate's disruption for the rest, the cascade for every COA.
    Raises when the twin fails (the caller then falls back to the surrogate for the whole DSS).  ``now`` is the
    generation's time: the twin's departure, matching the surrogate's time-of-day demand."""
    run_twin = twin or twin_disruption
    base = surrogate_wargame(drafts, seg, seed=seed, ambulance_eta_sec=ambulance_eta_sec)
    outcomes: dict[str, dict[str, Any]] = {}
    runs: list[dict[str, Any]] = []
    for d in drafts:
        out = dict(base.outcomes[d.coa_id])
        sur_run = next(r for r in base.sim_runs if r["coa_id"] == d.coa_id)
        lanes = max(1, net.lanes)
        lb = resolve_lanes(d.effects.lanes_blocked, lanes)
        cas: CascadeOutcome = run_cascade(
            net,
            lanes_blocked=lb,
            capacity_factor=d.effects.capacity_factor,
            active_min=d.effects.active_min,
            advisory=d.effects.advisory,
            closure=d.closure,
            diversion=d.diversion,
            emergency_lane=d.effects.emergency_lane,
            dispatch_108=d.dispatch_108,
            signal_priority=d.signal_priority,
            ambulance_eta_sec=ambulance_eta_sec,
            seed=seed,
            index=d.index,
            live_108_segments=live_108_segments,
        )
        if d.closure or d.diversion:
            tw = await run_twin(request, net.route, d, seed=seed, horizon_min=horizon_min, now=now)
            mean, p90 = float(tw["mean"]), float(tw["p90"])
            out["total_disruption_vehicle_hours"] = {
                "mean": round(mean, 1),
                "p90": round(p90, 1),
                "p90_mean_ratio": round(p90 / mean, 3) if mean > 1 else None,
                "replications": int(tw["replications"]),
            }
            disruption_method = (
                f"seeded corridor twin (unchanged, {tw['replications']} replications, full_closure on segments "
                f"{list(net.route)}), each closure pass projected to the COA's {int(d.effects.active_min)}-min "
                "closure by the point-queue law"
            )
            runs.append(_run_row(d.coa_id, "twin", seed, tw["metrics"]))
        else:
            reps = base.outcomes[d.coa_id]["total_disruption_vehicle_hours"]["replications"]
            disruption_method = f"DSS surrogate ({reps} replications, seeded): {_why_surrogate(d, lanes)}"
            runs.append(sur_run)
        out["cascade"] = cas.cascade_doc()
        delay = cas.ambulance_delay_sec
        out["emergency_impact"] = {"ambulance_delay_sec": delay, "green_corridor_ok": delay <= 0}
        out["method"] = (
            f"SIMULATED · disruption: {disruption_method}; cascade: DSS-layer spillover over the segment "
            f"neighbours + pgRouting KSP reassignment ({cas.metrics['replications']} replications, seeded)"
        )[:500]
        runs.append(_run_row(d.coa_id, "cascade", seed, {**cas.metrics,
                                                        "spillover_vh": {"mean": round(cas.spillover_mean, 3),
                                                                         "p90": round(cas.spillover_p90, 3)},
                                                        "ambulance_delay_sec": delay}))
        outcomes[d.coa_id] = out
    return WargameResult(outcomes, runs, "twin+cascade", notes=list(net.notes),
                         closures_excluded=tuple(net.closures_excluded),
                         closures_on_alternatives=tuple(net.closures_on_alternatives))
