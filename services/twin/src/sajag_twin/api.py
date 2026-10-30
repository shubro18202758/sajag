"""HTTP surface of the twin (FastAPI).

    GET  /health                      service, network and dependency status
    GET  /twin/network                which network, how many cells, junction control
    POST /twin/simulate               a plan in; metrics and queue time series out
    POST /twin/propose                a junction or corridor in; ranked proposals out
    GET  /twin/baselines/{junction}   Webster and max-pressure, evaluated in the twin

Every result is MODELLED. Nothing here changes a signal: a proposal is a
document for a named officer to approve or reject through the platform's
own signal writer; if no one decides, the current plan holds.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from sajag_twin import __version__
from sajag_twin import params as P
from sajag_twin.config import Settings
from sajag_twin.demand import Forecast, parse_start
from sajag_twin.metrics import Focus, compare, series_for
from sajag_twin.network import NetworkError, Program
from sajag_twin.oracle_client import OracleClient
from sajag_twin.proposals import corridor_path, run_proposals
from sajag_twin.rationale import Explainer
from sajag_twin.signals import Plan, Window
from sajag_twin.twin import Twin, fixed_window, mp_window

log = logging.getLogger("sajag_twin.api")

JunctionRef = int | str


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class PhaseIn(BaseModel):
    green_sec: int = Field(ge=0, le=P.MAX_CYCLE_S)
    movements: list[str] = Field(min_length=1, max_length=4)


class ProgramIn(BaseModel):
    cycle_sec: int = Field(ge=P.MIN_CYCLE_S, le=P.MAX_CYCLE_S)
    offset_sec: int = Field(default=0, ge=0, le=P.MAX_CYCLE_S)
    phases: list[PhaseIn] = Field(min_length=1, max_length=6)

    def to_program(self) -> Program:
        return Program(
            self.cycle_sec,
            self.offset_sec % self.cycle_sec,
            tuple((p.green_sec, tuple(p.movements)) for p in self.phases),
            "request plan",
        )


class WindowIn(BaseModel):
    junction: JunctionRef
    from_min: float = Field(default=0.0, ge=0.0, le=180.0)
    to_min: float = Field(gt=0.0, le=180.0)
    control: Literal["fixed", "max_pressure"] = "fixed"
    program: ProgramIn | None = None


class PlanIn(BaseModel):
    name: str = Field(default="request plan", max_length=80)
    windows: list[WindowIn] = Field(default_factory=list, max_length=40)


class ForecastIn(BaseModel):
    vc: float = Field(gt=0.0, le=1.6)
    in_min: float = Field(default=30.0, ge=0.0, le=180.0)
    junction: JunctionRef | None = None
    segment_ids: list[int] = Field(default_factory=list, max_length=40)
    source: str = Field(default="forecast", max_length=60)


class DemandIn(BaseModel):
    mode: Literal["auto", "simulated", "live"] = "auto"
    scale: float = Field(default=1.0, gt=0.0, le=2.0)
    forecasts: list[ForecastIn] = Field(default_factory=list, max_length=10)


class SimulateIn(BaseModel):
    start: str | None = Field(default=None, description="HH:MM (IST, today) or ISO datetime; default now")
    horizon_min: float = Field(default=30.0, ge=5.0, le=120.0)
    demand: DemandIn = Field(default_factory=DemandIn)
    plan: PlanIn = Field(default_factory=PlanIn)
    focus_junctions: list[JunctionRef] = Field(default_factory=list, max_length=10)
    compare_do_nothing: bool = True
    series: bool = True


class CorridorIn(BaseModel):
    segment_ids: list[int] = Field(default_factory=list, max_length=40)
    junctions: list[JunctionRef] = Field(default_factory=list, max_length=40)


class ProposeIn(BaseModel):
    junction_ids: list[JunctionRef] = Field(default_factory=list, max_length=4)
    corridor: CorridorIn | None = None
    horizon_min: float = Field(default=45.0, ge=30.0, le=60.0)
    start: str | None = None
    demand_mode: Literal["auto", "simulated", "live"] = "auto"
    forecast: list[ForecastIn] | ForecastIn | None = None
    cross_street_tolerance_pct: float = Field(default=25.0, ge=0.0, le=200.0)
    max_candidates: int = Field(default=24, ge=1, le=40)
    explain: bool = True
    series: bool = True

    def forecasts(self) -> list[ForecastIn]:
        if self.forecast is None:
            return []
        return self.forecast if isinstance(self.forecast, list) else [self.forecast]


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------


def create_app(settings: Settings | None = None, *, twin: Twin | None = None, explainer: Explainer | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    oracle = OracleClient(settings.oracle_url)
    tw = twin or Twin.from_path(settings.network_path, oracle)
    ex = explainer or Explainer(settings.llm_url, enabled=settings.llm_enabled, model=settings.llm_model)
    app = FastAPI(title="Sajag signal-timing twin", version=__version__)
    app.state.twin = tw
    app.state.explainer = ex
    app.state.settings = settings

    def jref(ref: JunctionRef) -> int:
        try:
            return tw.net.resolve_junction(ref)
        except NetworkError as exc:
            raise HTTPException(422, str(exc)) from exc

    def start_of(v: str | None):
        try:
            return parse_start(v)
        except (ValueError, TypeError) as exc:
            raise HTTPException(422, f"start: {exc}") from exc

    def forecasts_of(items: list[ForecastIn]) -> list[Forecast]:
        out = []
        for f in items:
            out.append(Forecast(vc=f.vc, in_min=f.in_min, junction_id=jref(f.junction) if f.junction is not None else None,
                                segment_ids=tuple(f.segment_ids), source=f.source))
        return out

    def labels(dem) -> dict:
        return {"result": "MODELLED", "demand": dem.label,
                "note": "A traffic model (cell-transmission twin), not measured traffic."}

    @app.get("/health")
    def health() -> dict:
        return {
            "status": "ok",
            "service": "twin",
            "version": __version__,
            "network": {k: v for k, v in tw.describe().items() if k in ("city", "schema", "junctions", "directed_links", "cells")},
            "oracle": {"configured": oracle.enabled},
            "llm": {"enabled": ex.enabled},
        }

    @app.get("/twin/network")
    def network() -> dict:
        d = tw.describe()
        d["junction_list"] = [j.to_dict() for _, j in sorted(tw.net.junctions.items())]
        d["assumptions"] = P.assumptions_doc()
        d["labels"] = {"programs": "MODELLED (osm_assumed templates; twin-assumed where the network has none)"}
        return d

    @app.post("/twin/simulate")
    def simulate_ep(req: SimulateIn) -> dict:
        t0 = time.perf_counter()
        start = start_of(req.start)
        windows: list[Window] = []
        for w in req.plan.windows:
            jid = jref(w.junction)
            if w.to_min <= w.from_min:
                raise HTTPException(422, "a window must end after it starts")
            if w.control == "fixed":
                if w.program is None:
                    raise HTTPException(422, "a fixed-time window needs a program")
                prog = w.program.to_program()
                try:
                    prog.validate()
                except NetworkError as exc:
                    raise HTTPException(422, str(exc)) from exc
                windows.append(Window(jid, w.from_min * 60.0, w.to_min * 60.0, "fixed", prog))
            else:
                windows.append(Window(jid, w.from_min * 60.0, w.to_min * 60.0, "max_pressure", None))
        plan = Plan(req.plan.name, windows, "request", "Plan from the request.")
        focus_ids = [jref(j) for j in req.focus_junctions] or sorted({w.junction_id for w in windows})
        dem = tw.build_demand(start, req.horizon_min, mode=req.demand.mode, forecasts=forecasts_of(req.demand.forecasts), scale=req.demand.scale)
        sc = tw.scenario(dem, req.horizon_min)
        plans = [plan] + ([Plan("do nothing")] if req.compare_do_nothing else [])
        try:
            res = tw.run(sc, plans)
        except NetworkError as exc:
            raise HTTPException(422, str(exc)) from exc
        focus = Focus(focus_ids)
        mets = tw.metrics(res, focus)
        out: dict[str, Any] = {
            "network": {k: v for k, v in tw.describe().items() if k in ("city", "junctions", "directed_links", "cells", "dt_s")},
            "demand": dem.to_dict(),
            "plan": plan.to_dict(),
            "focus_junctions": focus_ids,
            "horizon_min": req.horizon_min,
            "metrics": mets[0],
            "labels": labels(dem),
        }
        if req.compare_do_nothing:
            out["do_nothing"] = mets[1]
            out["change"] = compare(mets[0], mets[1])
        if req.series:
            out["series"] = series_for(tw.cp, res, 0, focus)
            if req.compare_do_nothing:
                out["series_do_nothing"] = series_for(tw.cp, res, 1, focus)
        out["timing"] = {
            "warmup_s": round(sc.warm_elapsed_s, 3),
            "run_s": round(res.elapsed_s, 3),
            "candidates": res.K,
            "total_s": round(time.perf_counter() - t0, 3),
        }
        return out

    @app.post("/twin/propose")
    def propose_ep(req: ProposeIn) -> dict:
        t0 = time.perf_counter()
        start = start_of(req.start)
        jids = [jref(j) for j in req.junction_ids]
        for jid in jids:
            if not tw.net.junctions[jid].signalised:
                raise HTTPException(422, f"junction {jid} has no signal in the twin ({tw.net.junctions[jid].control})")
        corridor = None
        if req.corridor is not None:
            try:
                corridor = corridor_path(tw.net, req.corridor.segment_ids or None, [jref(j) for j in req.corridor.junctions] or None)
            except NetworkError as exc:
                raise HTTPException(422, str(exc)) from exc
        dem = tw.build_demand(start, req.horizon_min, mode=req.demand_mode, forecasts=forecasts_of(req.forecasts()))
        sc = tw.scenario(dem, req.horizon_min)
        auto = False
        if not jids and corridor is None:
            jids = [_most_stressed(tw, sc)]
            auto = True
        out = run_proposals(
            tw, sc, junction_ids=jids, corridor=corridor, horizon_min=req.horizon_min,
            cross_tol_pct=req.cross_street_tolerance_pct, max_candidates=req.max_candidates, with_series=req.series,
        )
        out["focus"]["auto_selected"] = auto
        out["demand"] = dem.to_dict()
        out["labels"] = labels(dem)
        if out["proposal"] is not None:
            t_llm = time.perf_counter()
            out["proposal"]["rationale"] = ex.explain(out["proposal"], use_llm=req.explain)
            out["proposal"]["rationale"]["elapsed_s"] = round(time.perf_counter() - t_llm, 2)
        out["timing"] = {"warmup_s": round(sc.warm_elapsed_s, 3), "total_s": round(time.perf_counter() - t0, 3)}
        return out

    @app.get("/twin/baselines/{junction_id}")
    def baselines_ep(
        junction_id: str,
        start: str | None = Query(default=None),
        horizon_min: float = Query(default=30.0, ge=10.0, le=90.0),
        demand_mode: Literal["auto", "simulated", "live"] = Query(default="auto"),
    ) -> dict:
        jid = jref(junction_id)
        j = tw.net.junctions[jid]
        if not j.signalised:
            raise HTTPException(422, f"junction {jid} has no signal in the twin ({j.control})")
        dem = tw.build_demand(start_of(start), horizon_min, mode=demand_mode)
        sc = tw.scenario(dem, horizon_min)
        wb = tw.webster_for(dem, jid)
        plans = [
            Plan("current program"),
            Plan("Webster", [fixed_window(jid, wb.program, horizon_min)], "webster"),
            Plan("max-pressure", [mp_window(jid, horizon_min)], "max_pressure"),
        ]
        res = tw.run(sc, plans)
        focus = Focus([jid])
        mets = tw.metrics(res, focus)
        mp_hist = next(iter(res.mp_splits.values()), [])
        return {
            "junction": j.to_dict(tw.net.links),
            "demand": dem.to_dict(),
            "horizon_min": horizon_min,
            "current": {"program": j.program.to_dict(), "metrics": mets[0]},  # type: ignore[union-attr]
            "webster": {**wb.to_dict(), "metrics": mets[1], "change_vs_current": compare(mets[1], mets[0])},
            "max_pressure": {
                "form": "cyclic max-pressure: cycle, phase order and offset kept; split follows cycle-average pressure, "
                f"at most {P.MP_MAX_STEP_S} s change per phase per cycle, minimum green {P.MIN_GREEN_S} s",
                "greens_per_cycle": mp_hist[:40],
                "metrics": mets[2],
                "change_vs_current": compare(mets[2], mets[0]),
            },
            "labels": labels(dem),
            "timing": {"warmup_s": round(sc.warm_elapsed_s, 3), "run_s": round(res.elapsed_s, 3)},
        }

    return app


def _most_stressed(tw: Twin, sc) -> int:
    """The signalised junction with the most do-nothing delay on its approaches."""
    res = tw.run(sc, [Plan("do nothing")])
    best, best_d = None, -1.0
    for jid in tw.net.signalised_ids:
        j = tw.net.junctions[jid]
        d = float(res.link_delay_vs[0, j.in_links].sum())
        d += float(sum(res.vx_delay_vs[0, x] for x in range(tw.cp.X) if int(tw.cp.vx_junction[x]) == jid))
        if d > best_d:
            best, best_d = jid, d
    if best is None:
        raise HTTPException(422, "the network has no signalised junction")
    return best


def main() -> None:
    import uvicorn

    s = Settings.from_env()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    uvicorn.run(create_app(s), host=s.host, port=s.port, log_level="info")


__all__ = ["create_app", "main"]
