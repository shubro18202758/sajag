"""The nowcast engine: per-segment rain series, the tide, pump availability and susceptibility → the bucket
model → risk class, depth band, lead time and labelled drivers; plus the proposals.

Driver labels: rain LIVE (Open-Meteo) or UNAVAILABLE; tide MODELLED (approximate; Apollo Bunder, Mumbai
harbour); susceptibility MODELLED; pumps EMULATED (BMC pumping-station stand-in).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

from hydro import ffews as ffews_mod
from hydro import proposals as prop
from hydro.ffews import EmulatedFfews, FfewsAdapter, station_for
from hydro.model import CLASS_BANDS, CLASS_NAMES, PARAMS, simulate
from hydro.network import Network
from hydro.rain import RainClient, RainNowcast, idw
from hydro.tide import LABEL as TIDE_LABEL, TideModel

__all__ = ["Hydro", "load_susceptibility", "DEFAULT_S"]

_DATA = Path(__file__).with_name("data")
DEFAULT_S = 0.4


def load_susceptibility() -> dict[str, Any]:
    return json.loads((_DATA / "susceptibility.json").read_text(encoding="utf-8"))


def _junction_mr(net: Network, jid: int) -> str:
    j = net.junctions.get(jid)
    return j.name_mr if j and j.name_mr else net.junction_name(jid)


def _landmark_hi() -> dict[str, str]:
    lms = json.loads((_DATA / "mumbai_landmarks.json").read_text(encoding="utf-8"))["landmarks"]
    return {lm["id"]: lm["hi"] for lm in lms if lm.get("hi")}


_HI = _landmark_hi()


def _junction_hi(net: Network, jid: int) -> str:
    """Hindi name where the junction is a canonical landmark; else its Marathi name (the same Devanagari script,
    so a Hindi reader and the Hindi voice read it, where a Latin name would break the sentence); else English."""
    j = net.junctions.get(jid)
    if not j:
        return net.junction_name(jid)
    return _HI.get(j.key) or j.name_mr or net.junction_name(jid)


class Hydro:
    def __init__(self, network: Network, rain: RainClient, *, ffews: FfewsAdapter | None = None,
                 tide: TideModel | None = None, step_min: int = 15, horizon_min: int = 120) -> None:
        self.net = network
        self.rain = rain
        self.ffews = ffews or EmulatedFfews()
        self.tide = tide or TideModel()
        self.step = step_min
        self.horizon = horizon_min
        sus = load_susceptibility()
        self.sus = sus["segments"]
        self.sus_meta = {k: sus[k] for k in ("label", "built_at", "inputs", "weights")}

    # ── shared core (nowcast and replay) ───────────────────────────────────
    def seg_static(self, sid: int) -> dict[str, Any]:
        row = self.sus.get(str(sid))
        seg = self.net.segments[sid]
        lat, lon = seg.midpoint
        st, dist = station_for(lat, lon)
        if row is None:
            row = {"score": DEFAULT_S, "elevated": False, "note": "no susceptibility row: default score"}
        return {"seg": seg, "lat": lat, "lon": lon, "sus": row, "station": st, "station_m": dist}

    def run_segments(self, times: list[datetime], rain_for: dict[int, np.ndarray], availability: dict[str, float],
                     w0: dict[int, float] | None = None) -> dict[int, Any]:
        # the outfalls' loss of gravity discharge over each step, 0..1 (graded; 1 = gates shut)
        gates = np.array([self.tide.outfall_restriction(t - timedelta(minutes=self.step / 2)) for t in times])
        out = {}
        for sid in sorted(self.net.segments):
            st = self.seg_static(sid)
            a = availability.get(st["station"].id, 1.0) if st["station"] else 1.0
            run = simulate(rain_for[sid], gates, a, float(st["sus"]["score"]), bool(st["sus"].get("elevated")),
                           self.step, (w0 or {}).get(sid, 0.0))
            out[sid] = (st, a, run)
        return {"gates": gates, "runs": out}

    # ── live nowcast ──────────────────────────────────────────────────────
    async def nowcast(self, force: bool = False, now: datetime | None = None) -> dict[str, Any]:
        nc = await self.rain.nowcast(force=force)
        now = (now or datetime.now(UTC)).astimezone(UTC)
        n_future = self.horizon // self.step
        if nc.points:
            times = list(nc.points[0].times)
        else:  # no rain feed: a dry grid around now, labelled UNAVAILABLE
            base = now.replace(second=0, microsecond=0) - timedelta(minutes=now.minute % self.step)
            times = [base + timedelta(minutes=self.step * (i - 12)) for i in range(12 + n_future + 1)]
        now_idx = max(0, max((i for i, t in enumerate(times) if t <= now), default=0))
        city_now = float(np.mean([p.mm_h[now_idx] for p in nc.points])) if nc.points else 0.0
        states = self.ffews.states(now, city_now)
        availability = {s.station.id: s.availability for s in states}
        rain_for = {}
        for sid, seg in self.net.segments.items():
            lat, lon = seg.midpoint
            rain_for[sid] = idw(nc.points, lat, lon) if nc.points else np.zeros(len(times))
        core = self.run_segments(times, rain_for, availability)
        end_idx = min(len(times) - 1, now_idx + n_future)
        rain_label = nc.label if nc.points else "UNAVAILABLE"
        results = []
        for sid in sorted(self.net.segments):
            st, a, run = core["runs"][sid]
            r = self._result(sid, st, a, run, times, now_idx, end_idx, rain_for[sid], core["gates"], rain_label,
                             states, now)
            results.append(r)
        flagged = {r["segment_id"] for r in results if r["risk_class"] >= 2}
        labels = ["MODELLED", rain_label if rain_label != "UNAVAILABLE" else "RAIN-UNAVAILABLE", "EMULATED"]
        proposals = self._proposals(results, flagged, now, labels)
        counts = {str(c): sum(1 for r in results if r["risk_class"] == c) for c in range(4)}
        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "now": now.isoformat(),
            "horizon_min": self.horizon,
            "step_min": self.step,
            "labels": {"rain": rain_label, "tide": TIDE_LABEL, "susceptibility": "MODELLED", "pumps": "EMULATED",
                       "risk": "MODELLED"},
            "rain_feed": {"source": nc.source, "stale": nc.stale, "error": nc.error, "notes": nc.notes,
                          "fetched_at": nc.fetched_at.isoformat(), "city_now_mm_h": round(city_now, 2),
                          **self.rain.status()},
            "counts_by_class": counts,
            "flagged": sorted(flagged),
            "segments": results,
            "proposals": proposals,
            "model": {"kind": "conceptual ponding (bucket) model", "params": PARAMS,
                      "classes": [{"class": i, "name": CLASS_NAMES[i], "depth_band": CLASS_BANDS[i]}
                                  for i in range(4)]},
            "network": {"source": self.net.source, "attribution": self.net.attribution},
        }

    def _result(self, sid: int, st: dict, a: float, run: Any, times: list[datetime], now_idx: int, end_idx: int,
                rain: np.ndarray, gates: np.ndarray, rain_label: str, states: list,
                t_now: datetime | None = None) -> dict[str, Any]:
        seg = st["seg"]
        cls = run.classes
        window = cls[now_idx:end_idx + 1]
        peak = int(window.max()) if window.size else 0
        first = int(np.argmax(window >= peak)) if window.size else 0
        lead = first * self.step
        deep = np.nonzero(window >= 2)[0]
        lead_deep = int(deep[0]) * self.step if deep.size else None
        peak_i = now_idx + int(np.argmax(run.depth_cm[now_idx:end_idx + 1])) if window.size else now_idx
        dt_h = self.step / 60.0
        past1 = float(np.sum(rain[max(0, now_idx - 3):now_idx + 1]) * dt_h)
        past3 = float(np.sum(rain[max(0, now_idx - 11):now_idx + 1]) * dt_h)
        next1 = float(np.sum(rain[now_idx + 1:now_idx + 5]) * dt_h)
        next2 = float(np.sum(rain[now_idx + 1:now_idx + 9]) * dt_h)
        t_now = t_now or times[now_idx]
        hw = next((e for e in self.tide.extremes(t_now, 14) if e.kind == "high"), None)
        sus = st["sus"]
        station = st["station"]
        pst = next((s for s in states if station and s.station.id == station.id), None)
        return {
            "segment_id": sid,
            "road_name": seg.road_name,
            "place": self.net.junction_name(seg.to_junction),
            "place_mr": _junction_mr(self.net, seg.to_junction),
            "place_hi": _junction_hi(self.net, seg.to_junction),
            "lat": round(st["lat"], 5), "lon": round(st["lon"], 5),
            "risk_class": peak,
            "risk_name": CLASS_NAMES[peak],
            "risk_class_now": int(cls[now_idx]),
            "expected_depth_band": CLASS_BANDS[peak],
            "modelled_peak_depth_cm": round(float(run.depth_cm[peak_i]), 1),
            "lead_time_min": lead,
            "lead_time_deep_min": lead_deep,
            "peak_at": times[peak_i].isoformat(),
            "elevated": bool(sus.get("elevated", False)),
            "drivers": {
                "rain": {"label": rain_label, "past_1h_mm": round(past1, 1), "past_3h_mm": round(past3, 1),
                         "next_1h_mm": round(next1, 1), "next_2h_mm": round(next2, 1),
                         "peak_next_2h_mm_h": round(float(rain[now_idx + 1:end_idx + 1].max(initial=0.0)), 1),
                         "source": "Open-Meteo (IDW of the 3 nearest fixed points)"},
                "tide": {"label": TIDE_LABEL, "station": self.tide.station_name,
                         "level_m": round(self.tide.level(t_now), 2),
                         "gate_closed_now": bool(self.tide.gate_closed(t_now)),
                         "outfall_restriction_now": round(self.tide.outfall_restriction(t_now), 2),
                         "gate_closed_minutes_in_horizon": int((gates[now_idx + 1:end_idx + 1] >= 1.0).sum()
                                                               * self.step),
                         "outfalls_impeded_minutes_in_horizon": int((gates[now_idx + 1:end_idx + 1] > 0).sum()
                                                                    * self.step),
                         "gate_close_level_m": self.tide.gate_level,
                         "impeded_from_m": self.tide.impeded_from,
                         "next_high_water": {"at": hw.at.isoformat(), "level_m": hw.level_m} if hw else None},
                "susceptibility": {"label": "MODELLED", "score": sus.get("score"),
                                   "ground_m": sus.get("ground_p10_m"),
                                   "relative_elevation_m": sus.get("relative_elevation_m"),
                                   "dist_drain_m": sus.get("dist_drain_m"),
                                   "nearest_hotspot": sus.get("nearest_hotspot"),
                                   "dist_hotspot_m": sus.get("dist_hotspot_m"), "elevated": sus.get("elevated"),
                                   "note": sus.get("note")},
                "pumps": {"label": ffews_mod.LABEL,
                          "station": station.name if station else None,
                          "station_id": station.id if station else None,
                          "distance_m": round(st["station_m"]) if station else None,
                          "availability": round(a, 2),
                          "pumps_available": pst.pumps_available if pst else None,
                          "pumps_total": pst.pumps_total if pst else None,
                          "note": "EMULATED until the BMC's pumping-station telemetry (IFLOWS-Mumbai) is "
                                  "connected"},
            },
        }

    def _proposals(self, results: list[dict], flagged: set[int], at: datetime, labels: list[str]) -> list[dict]:
        out: list[dict] = []
        hot = sorted((r for r in results if r["segment_id"] in flagged),
                     key=lambda r: (-r["risk_class"], r["lead_time_min"]))
        for r in hot:
            out.append(prop.reroute(self.net, r, flagged, at, labels))
            out.append(prop.ambulance_window(self.net, r, flagged, at, labels))
            out.append(prop.live_wire(r, at, labels))
        pumps = prop.pump_request(hot, at, labels)
        if pumps:
            out.append(pumps)
        adv = prop.advisory_draft(results, at, self.horizon, labels)
        if adv:
            out.append(adv)
        return out

    def tide_view(self, hours: float = 24.0, now: datetime | None = None) -> dict[str, Any]:
        now = (now or datetime.now(UTC)).astimezone(UTC)
        start = now.replace(second=0, microsecond=0) - timedelta(minutes=now.minute % self.step)
        series = self.tide.series(start, hours, self.step)
        level = self.tide.level(now)
        gl = self.tide.gate_level
        return {
            "label": TIDE_LABEL,
            "station": self.tide.station_name,
            "now": {"t": now.isoformat(), "level_m": round(level, 2), "gate_closed": level >= gl,
                    "outfall_restriction": round(self.tide.outfall_restriction(now), 2),
                    "rising": self.tide.level(now + timedelta(minutes=10)) > level},
            "gate_close_level_m": gl,
            "impeded_from_m": self.tide.impeded_from,
            "series": [{"t": t.isoformat(), "level_m": round(v, 2), "gate_closed": v >= gl,
                        "outfall_restriction": round(self.tide.outfall_restriction(t), 2)} for t, v in series],
            "extremes": [{"kind": e.kind, "at": e.at.isoformat(), "level_m": e.level_m}
                         for e in self.tide.extremes(start, hours)],
            "datum": self.tide.datum + "; levels are approximate",
            "sources": self.tide.sources,
        }


def rain_view(nc: RainNowcast, status: dict) -> dict[str, Any]:
    times, city = nc.city_mean()
    return {
        "label": nc.label, "source": nc.source, "fetched_at": nc.fetched_at.isoformat(), "stale": nc.stale,
        "error": nc.error, "notes": nc.notes, "step_min": 15, **status,
        "city": {"series": [{"t": t.isoformat(), "mm_h": round(float(v), 2)} for t, v in zip(times, city)]},
        "points": [{"id": p.id, "lat": p.lat, "lon": p.lon,
                    "series": [{"t": t.isoformat(), "mm_h": round(float(v), 2)} for t, v in zip(p.times, p.mm_h)]}
                   for p in nc.points],
    }
