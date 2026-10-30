"""The forecast engine: histories → model → per-segment quantile forecasts, crossings and proposals; plus the
rolling-origin backtest of the model against the seasonal-naive baseline (and the contender).

Forecasts are computed for the longest horizon (120 min, 8 steps) and served truncated to the horizon
asked for. Results are cached for ``cache_ttl_sec``; ``POST /forecast/refresh`` recomputes.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np
import structlog

from forecast.bpr import speed_from_vc
from forecast.config import Settings
from forecast.covariates import HydroClient, gate_series
from forecast.memroom import summarize
from forecast.models import (
    Chronos2Forecaster,
    Forecaster,
    QuantileForecast,
    SeasonalNaive,
    SeriesInput,
    TimesFMForecaster,
    gpu_stats,
)
from forecast.network import Network
from forecast.oracle import OracleClient, assemble_history, events_covariate
from forecast.proposals import crossing_proposal
from forecast.synthetic import History, SyntheticCity, align

logger = structlog.get_logger(__name__)

__all__ = ["Engine", "build_inputs", "crossing_of", "score"]

MAX_HORIZON_MIN = 120
COV_KEYS = ("rain_mm_h", "gate_closed", "event")


def build_inputs(h: History, origin: int, horizon: int, context: int, future: History | None = None
                 ) -> SeriesInput:
    """Context up to and including step ``origin`` of ``h``; future covariates from ``future`` (or from h
    itself after the origin, as in the backtest)."""
    lo = max(0, origin + 1 - context)
    past = {k: v[lo:origin + 1] for k, v in h.covariates().items()}
    src = future.covariates() if future is not None else {k: v[origin + 1:origin + 1 + horizon]
                                                          for k, v in h.covariates().items()}
    fut = {k: np.asarray(src[k][:horizon], dtype=float) for k in COV_KEYS}
    return SeriesInput(target=h.vc[lo:origin + 1], past_cov=past, future_cov=fut)


def crossing_of(now_vc: float, q: QuantileForecast, threshold: float) -> int | None:
    """Index of the first step whose p50 reaches the threshold, when the segment is below it now."""
    if now_vc >= threshold:
        return None
    hit = np.nonzero(q.p50 >= threshold)[0]
    return int(hit[0]) if hit.size else None


def score(actual: np.ndarray, fcs: list[QuantileForecast], free_flow: np.ndarray, step_min: int,
          threshold: float, now_vc: np.ndarray) -> dict[str, Any]:
    """MAE / MAPE / interval coverage per horizon and overall, plus crossing-alert skill."""
    p10 = np.stack([f.p10 for f in fcs])
    p50 = np.stack([f.p50 for f in fcs])
    p90 = np.stack([f.p90 for f in fcs])
    err = np.abs(p50 - actual)
    ape = err / np.maximum(np.abs(actual), 0.05)
    cover = (actual >= p10) & (actual <= p90)
    sp_a = speed_from_vc(actual, 1.0) * free_flow[:, None]
    sp_f = speed_from_vc(p50, 1.0) * free_flow[:, None]
    by_h = {}
    for h in range(actual.shape[1]):
        by_h[str((h + 1) * step_min)] = {
            "mae_vc": round(float(err[:, h].mean()), 4),
            "mape_pct": round(float(100 * ape[:, h].mean()), 2),
            "coverage_p10_p90": round(float(cover[:, h].mean()), 3),
        }
    act_cross = np.array([(nv < threshold) and bool((a >= threshold).any()) for nv, a in zip(now_vc, actual)])
    fc_cross = np.array([(nv < threshold) and bool((f >= threshold).any()) for nv, f in zip(now_vc, p50)])
    tp = int((act_cross & fc_cross).sum())
    fp = int((~act_cross & fc_cross).sum())
    fn = int((act_cross & ~fc_cross).sum())
    return {
        "mae_vc": round(float(err.mean()), 4),
        "mape_pct": round(float(100 * ape.mean()), 2),
        "mae_speed_kmh": round(float(np.abs(sp_f - sp_a).mean()), 2),
        "coverage_p10_p90": round(float(cover.mean()), 3),
        "mean_interval_width_vc": round(float((p90 - p10).mean()), 4),
        "by_horizon_min": by_h,
        "crossing_alerts": {
            "actual": int(act_cross.sum()), "forecast": int(fc_cross.sum()), "hits": tp,
            "false_alarms": fp, "misses": fn,
            "precision": round(tp / (tp + fp), 3) if tp + fp else None,
            "recall": round(tp / (tp + fn), 3) if tp + fn else None,
        },
    }


@dataclass
class _Cache:
    at: float = 0.0
    body: dict[str, Any] | None = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class Engine:
    def __init__(self, settings: Settings, network: Network, *, oracle: OracleClient | None = None,
                 hydro: HydroClient | None = None, model: Forecaster | None = None,
                 contender: Forecaster | None = None) -> None:
        self.s = settings
        self.net = network
        self.oracle = oracle
        self.hydro = hydro
        self.sim = SyntheticCity(network, seed=settings.synthetic_seed, step_min=settings.step_min)
        self.naive = SeasonalNaive(steps_per_day=24 * 60 // settings.step_min)
        if model is None:
            if settings.model == "chronos2":
                model = Chronos2Forecaster(settings.chronos_model_id, settings.device, settings.dtype,
                                           settings.idle_unload_sec)
            elif settings.model == "timesfm":
                model = TimesFMForecaster(settings.timesfm_model_id, settings.idle_unload_sec)
            else:
                model = self.naive
        self.model = model
        if contender is None and settings.contender == "timesfm" and settings.model != "timesfm":
            contender = TimesFMForecaster(settings.timesfm_model_id, settings.idle_unload_sec)
        self.contender = contender
        self._fc = _Cache()
        self._bt = _Cache()
        self.last_error: str | None = None

    # ── slots (lazy GPU models) ───────────────────────────────────────────
    def slots(self) -> list:
        return [m.slot for m in (self.model, self.contender) if m is not None and hasattr(m, "slot")]

    def reap_idle(self) -> list[str]:
        return [s.name for s in self.slots() if s.maybe_unload()]

    def release_idle(self, min_idle_s: float) -> dict[str, Any]:
        """POST /admin/release: free every slot no prediction holds and unused for ``min_idle_s``."""
        items = [r for r in (s.release_if_idle(min_idle_s) for s in self.slots()) if r is not None]
        return summarize("forecast", items)

    # ── histories ─────────────────────────────────────────────────────────
    @property
    def steps(self) -> int:
        return MAX_HORIZON_MIN // self.s.step_min

    @property
    def context(self) -> int:
        return self.s.context_days * 24 * 60 // self.s.step_min

    async def _oracle_histories(self, sids: list[int], end: datetime) -> tuple[dict[int, History], dict[int, str], dict]:
        got: dict[int, History] = {}
        reasons: dict[int, str] = {}
        info: dict[str, Any] = {"used": False}
        if self.oracle is None or self.s.data_source == "synthetic":
            return got, reasons, info
        health = await self.oracle.health()
        info.update(health)
        if not health.get("reachable"):
            for sid in sids:
                reasons[sid] = "oracle not reachable"
            return got, reasons, info
        try:
            served = {int(x.get("segmentId")) for x in await self.oracle.segments(self.s.city_bbox)
                      if x.get("segmentId") is not None}
        except Exception as exc:  # noqa: BLE001
            served = set()
            info["segments_error"] = type(exc).__name__
        info["city_segments_served"] = len(served)
        eligible = [sid for sid in sids if sid in served]
        for sid in sids:
            if sid not in served:
                reasons[sid] = ("oracle serves no segment with this id inside the city bbox "
                                "(its store is not seeded with this city's network)")
        if not eligible:
            return got, reasons, info
        info["used"] = True
        sem = asyncio.Semaphore(8)

        async def one(sid: int) -> None:
            async with sem:
                try:
                    hourly = await self.oracle.hourly(sid, self.s.context_days * 24)
                    raw = await self.oracle.raw(sid)
                except Exception as exc:  # noqa: BLE001
                    reasons[sid] = f"oracle request failed ({type(exc).__name__})"
                    return
            seg = self.net.segments[sid]
            oh = assemble_history(sid, hourly, raw, end=end, days=self.s.context_days,
                                  free_flow_kmh=seg.speed_limit_kmh, step_min=self.s.step_min,
                                  min_steps=self.s.min_oracle_steps)
            if oh.history is None:
                reasons[sid] = oh.reason or "no history"
            else:
                got[sid] = oh.history

        await asyncio.gather(*(one(sid) for sid in eligible))
        events: list[dict] = []
        if got:
            try:
                events = await self.oracle.active_events()
            except Exception:  # noqa: BLE001
                events = []
        for sid, h in got.items():
            h.event = events_covariate(events, sid, h.start, h.n, self.s.step_min)
            h.gate_closed = gate_series(h.start, h.n, self.s.step_min)
        info["active_events"] = len(events)
        return got, reasons, info

    # ── forecasts ─────────────────────────────────────────────────────────
    async def forecasts(self, *, force: bool = False, now: datetime | None = None) -> dict[str, Any]:
        async with self._fc.lock:
            fresh = self._fc.body is not None and time.monotonic() - self._fc.at < self.s.cache_ttl_sec
            if fresh and not force and now is None:
                return self._fc.body  # type: ignore[return-value]
            body = await self._compute(now)
            self._fc.body, self._fc.at = body, time.monotonic()
            return body

    async def _compute(self, now: datetime | None) -> dict[str, Any]:
        step = self.s.step_min
        origin_t = align(now or datetime.now(UTC), step)
        if now is None:
            origin_t -= timedelta(minutes=step)  # the last complete step
        sids = sorted(self.net.segments)
        start = origin_t - timedelta(days=self.s.context_days)
        oracle_h, reasons, oracle_info = await self._oracle_histories(sids, origin_t)

        hist: dict[int, History] = {}
        future: dict[int, History] = {}
        skipped: dict[int, str] = {}
        need_sim = [sid for sid in sids if sid not in oracle_h]
        if self.s.data_source == "oracle":
            skipped = {sid: reasons.get(sid, "no oracle history") for sid in need_sim}
            need_sim = []
        sims = self.sim.histories(need_sim, start, origin_t + timedelta(minutes=step * self.steps)) if need_sim else {}
        for sid, h in sims.items():
            hist[sid] = h.slice(0, h.n - self.steps)
            future[sid] = h.slice(h.n - self.steps, h.n)
        rain_info: dict[str, Any] | None = None
        if oracle_h:
            fut_start = origin_t + timedelta(minutes=step)
            rain, rain_info = (await self.hydro.rain(fut_start, self.steps, step) if self.hydro
                               else (np.zeros(self.steps), {"label": "UNAVAILABLE", "source": "no hydro client"}))
            gates = gate_series(fut_start, self.steps, step)
            for sid, h in oracle_h.items():
                hist[sid] = h
                f = History(sid, fut_start, step, np.zeros(self.steps), np.zeros(self.steps), rain, gates,
                            np.full(self.steps, h.event[-1] if h.n else 0.0), h.free_flow_kmh, h.label, h.source)
                future[sid] = f

        order = [sid for sid in sids if sid in hist]
        inputs = [build_inputs(hist[sid], hist[sid].n - 1, self.steps, self.context, future[sid]) for sid in order]
        model_name, model_note = self.model.name, None
        t0 = time.monotonic()
        try:
            qs = await asyncio.to_thread(self.model.predict, inputs, self.steps) if inputs else []
            self.last_error = None
        except Exception as exc:  # noqa: BLE001 — a model that cannot load must not take the service down
            self.last_error = f"{type(exc).__name__}: {exc}"[:300]
            logger.warning("forecast.model_failed", error=self.last_error)
            qs = self.naive.predict(inputs, self.steps)
            model_name, model_note = self.naive.name, f"model unavailable, baseline served ({self.last_error})"
        infer_sec = round(time.monotonic() - t0, 2)
        base = self.naive.predict(inputs, self.steps)

        segs: list[dict[str, Any]] = []
        for sid, q, b in zip(order, qs, base):
            segs.append(self._segment_out(sid, hist[sid], future[sid], q, b, origin_t, model_name, rain_info))
        hot = {s["segment_id"] for s in segs
               if s["above_threshold_now"] or s["crossing"] is not None
               or any(st["vc"]["p50"] >= self.s.vc_threshold for st in s["steps"])}
        proposals = []
        for s in segs:
            if s["crossing"] is not None:
                labels = [s["data_label"], "MODELLED"]
                proposals.append(crossing_proposal(self.net, s, hot, origin_t, self.s.vc_threshold,
                                                   MAX_HORIZON_MIN, labels, model_name))
                s["proposal_id"] = proposals[-1]["proposal_id"]
        # most pressing first: the highest forecast median at the crossing, then the soonest
        proposals.sort(key=lambda p: (-p["situation"]["vc_p50"], p["situation"]["in_min"]))
        labels = sorted({s["data_label"] for s in segs})
        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "origin": origin_t.isoformat(),
            "step_min": step,
            "max_horizon_min": MAX_HORIZON_MIN,
            "threshold_vc": self.s.vc_threshold,
            "model": model_name,
            "model_note": model_note,
            "inference_sec": infer_sec,
            "data_labels": labels,
            "data_note": self._data_note(labels),
            "oracle": oracle_info,
            "segments": segs,
            "skipped": [{"segment_id": k, "reason": v} for k, v in sorted(skipped.items())],
            "fallback_reasons": {str(k): v for k, v in sorted(reasons.items()) if k in sims},
            "proposals": proposals,
            "network": {"source": self.net.source, "attribution": self.net.attribution},
        }

    @staticmethod
    def _data_note(labels: list[str]) -> str:
        if labels == ["SIMULATED"]:
            return ("Forecast on simulated traffic: the history is the platform's SIMULATED Mumbai history "
                    "(or the oracle's simulated feed). Covariates come from the same simulated world.")
        if labels == ["LIVE"]:
            return "Forecast on recorded traffic from the oracle; rain covariate LIVE, tide MODELLED."
        return "Mixed: each segment carries its own data label."

    def _segment_out(self, sid: int, h: History, fut: History, q: QuantileForecast, b: QuantileForecast,
                     origin_t: datetime, model_name: str, rain_info: dict | None) -> dict[str, Any]:
        seg = self.net.segments[sid]
        step = self.s.step_min
        ff = h.free_flow_kmh
        steps = []
        for i in range(self.steps):
            vc = {"p10": round(float(max(q.p10[i], 0.0)), 3), "p50": round(float(max(q.p50[i], 0.0)), 3),
                  "p90": round(float(max(q.p90[i], 0.0)), 3)}
            sp = speed_from_vc([vc["p90"], vc["p50"], vc["p10"]], ff)
            steps.append({
                "t": (origin_t + timedelta(minutes=step * (i + 1))).isoformat(),
                "lead_min": step * (i + 1),
                "vc": vc,
                "speed_kmh": {"p10": round(float(sp[0]), 1), "p50": round(float(sp[1]), 1),
                              "p90": round(float(sp[2]), 1)},
                "baseline_vc_p50": round(float(b.p50[i]), 3),
            })
        now_vc = float(h.vc[-1])
        ci = crossing_of(now_vc, q, self.s.vc_threshold)
        crossing = None
        if ci is not None:
            st = steps[ci]
            crossing = {"threshold": self.s.vc_threshold, "at": st["t"], "in_min": st["lead_min"],
                        "vc_p10": st["vc"]["p10"], "vc_p50": st["vc"]["p50"], "vc_p90": st["vc"]["p90"],
                        "baseline_vc_p50": st["baseline_vc_p50"]}
        sim = h.label == "SIMULATED" and h.source.startswith("synthetic")
        cov_label = "SIMULATED" if sim else None
        rain_next2h = float(np.sum(fut.rain_mm_h) * step / 60.0)
        return {
            "segment_id": sid,
            "road_name": seg.road_name,
            "place": self.net.junction_name(seg.to_junction),
            "from_junction": seg.from_junction,
            "to_junction": seg.to_junction,
            "data_label": h.label,
            "history_source": h.source,
            "history_steps": int(min(h.n, self.context)),
            "notes": h.notes,
            "now": {"t": h.end.isoformat(), "vc": round(now_vc, 3), "speed_kmh": round(float(h.speed[-1]), 1)},
            "steps": steps,
            "crossing": crossing,
            "above_threshold_now": now_vc >= self.s.vc_threshold,
            "covariates": {
                "rain": {"label": cov_label or (rain_info or {}).get("label", "UNAVAILABLE"),
                         "next_2h_mm": round(rain_next2h, 1),
                         "source": "simulated world" if sim else (rain_info or {}).get("source")},
                "gate_closed": {"label": "SIMULATED" if sim else "MODELLED",
                                "next_2h_steps_closed": int(np.sum(fut.gate_closed)),
                                "source": "Apollo Bunder tide model (MODELLED, approximate)"},
                "event": {"label": cov_label or "LIVE",
                          "active_next_2h": bool(np.any(fut.event > 0)),
                          "source": "simulated calendar (Ganeshotsav, visarjan, Wankhede egress, marathon)" if sim
                          else "oracle active corridor events"},
            },
            "model": model_name,
        }

    # ── backtest ──────────────────────────────────────────────────────────
    async def backtest(self, *, force: bool = False, end: datetime | None = None) -> dict[str, Any]:
        async with self._bt.lock:
            if self._bt.body is not None and not force and end is None and time.monotonic() - self._bt.at < 3600:
                return self._bt.body
            body = await asyncio.to_thread(self._backtest_sync, end)
            self._bt.body, self._bt.at = body, time.monotonic()
            return body

    def _backtest_sync(self, end: datetime | None) -> dict[str, Any]:
        step = self.s.step_min
        end_t = align(end or datetime.now(UTC), step) - timedelta(minutes=step)
        days, stride_h = self.s.backtest_days, self.s.backtest_stride_hours
        start = end_t - timedelta(days=self.s.context_days + days)
        sids = sorted(self.net.segments)
        hists = self.sim.histories(sids, start, end_t)
        n = next(iter(hists.values())).n
        per_day = 24 * 60 // step
        origins = [n - 1 - self.steps - k * stride_h * 60 // step for k in range(days * 24 // stride_h)]
        origins = sorted(o for o in origins if o - self.context + 1 >= 0 or o >= 2 * per_day)
        inputs, actual, ff, now_vc = [], [], [], []
        for o in origins:
            for sid in sids:
                h = hists[sid]
                inputs.append(build_inputs(h, o, self.steps, self.context))
                actual.append(h.vc[o + 1:o + 1 + self.steps])
                ff.append(h.free_flow_kmh)
                now_vc.append(h.vc[o])
        actual_a, ff_a, now_a = np.stack(actual), np.array(ff), np.array(now_vc)
        out: dict[str, Any] = {
            "generated_at": datetime.now(UTC).isoformat(),
            "data_label": "SIMULATED",
            "data_note": (f"Backtest on the SIMULATED Mumbai history (seed {self.s.synthetic_seed}), not on "
                          "recorded traffic. Future covariates (rain, gate closure, scheduled events) are the "
                          "realised simulated values — a perfect-nowcast assumption; incidents are unannounced."),
            "window": {"from": hists[sids[0]].time_at(origins[0]).isoformat(),
                       "to": hists[sids[0]].time_at(origins[-1]).isoformat(),
                       "origins": len(origins), "stride_hours": stride_h, "segments": len(sids),
                       "series": len(inputs), "horizon_min": MAX_HORIZON_MIN,
                       "context_days": self.s.context_days},
            "threshold_vc": self.s.vc_threshold,
            "models": {},
        }
        univariate = [SeriesInput(target=i.target) for i in inputs]
        runs: list[tuple[str, Forecaster, list[SeriesInput]]] = [(self.naive.name, self.naive, inputs)]
        if self.model is not self.naive:
            runs.insert(0, (self.model.name, self.model, inputs))
            if isinstance(self.model, Chronos2Forecaster):
                # ablation: the same model without its covariates (rain, gate closure, events)
                runs.insert(1, (f"{self.model.name} (no covariates)", self.model, univariate))
        if self.contender is not None:
            runs.append((self.contender.name, self.contender, univariate))
        for name, m, inp in runs:
            t0 = time.monotonic()
            try:
                fcs = m.predict(inp, self.steps)
            except Exception as exc:  # noqa: BLE001
                out["models"][name] = {"error": f"{type(exc).__name__}: {exc}"[:300]}
                continue
            res = score(actual_a, fcs, ff_a, step, self.s.vc_threshold, now_a)
            res["seconds"] = round(time.monotonic() - t0, 2)
            res["licence"] = getattr(m, "licence", None)
            res["covariates"] = bool(inp and inp[0].past_cov) and not isinstance(m, SeasonalNaive)
            if m is self.contender and hasattr(m, "slot"):
                m.slot.unload()  # the contender is only for the backtest: free it now
            if hasattr(m, "slot"):
                res["gpu"] = m.slot.status()
            out["models"][name] = res
        base = out["models"].get(self.naive.name, {})
        for name, r in out["models"].items():
            if name != self.naive.name and "mae_vc" in r and "mae_vc" in base:
                r["mae_skill_vs_baseline"] = round(1.0 - r["mae_vc"] / base["mae_vc"], 3)
        out["gpu"] = gpu_stats()
        return out
